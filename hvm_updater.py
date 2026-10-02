"""Safe, scheduled updater for HVM panel application files."""

import io
import json
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import requests


LOGGER = logging.getLogger("AGVM_panel")
DEFAULT_REPOSITORY = "diablo0098/vmpanel"
DEFAULT_BRANCH = "main"
CHECK_INTERVAL_SECONDS = 30 * 60
MAX_ARCHIVE_BYTES = 40 * 1024 * 1024
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_FILE_BYTES = 30 * 1024 * 1024
CORE_FILES = {"main.py", "AGVM-5.1.py", "api.py", "node.py", "hvm_updater.py"}


def _project_files(relative_path):
    if relative_path in CORE_FILES or relative_path == "requirements.txt":
        return True
    return (
        relative_path.startswith("templates/")
        and relative_path.endswith(".html")
    )


def _download_archive(owner, repository, branch):
    api_url = f"https://api.github.com/repos/{owner}/{repository}/commits/{quote(branch, safe='')}"
    response = requests.get(
        api_url,
        headers={"Accept": "application/vnd.github+json"},
        timeout=(5, 20),
    )
    response.raise_for_status()
    commit_sha = response.json().get("sha")
    if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("GitHub returned an invalid commit SHA")

    archive_url = f"https://codeload.github.com/{owner}/{repository}/zip/{commit_sha}"
    with requests.get(archive_url, stream=True, timeout=(5, 30)) as response:
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_ARCHIVE_BYTES:
            raise ValueError("Update archive exceeds the size limit")

        archive = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if chunk:
                archive.extend(chunk)
                if len(archive) > MAX_ARCHIVE_BYTES:
                    raise ValueError("Update archive exceeds the size limit")
    return commit_sha, bytes(archive)


def _read_update_files(archive_bytes):
    files = {}
    total_size = 0
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = archive.infolist()
        if len(members) > 2000:
            raise ValueError("Update archive contains too many files")

        for member in members:
            if member.is_dir():
                continue
            zip_path = PurePosixPath(member.filename)
            if zip_path.is_absolute() or ".." in zip_path.parts or "\\" in member.filename:
                raise ValueError("Update archive contains an unsafe file path")
            if len(zip_path.parts) < 2:
                continue

            relative_path = PurePosixPath(*zip_path.parts[1:]).as_posix()
            if not _project_files(relative_path):
                continue

            file_mode = member.external_attr >> 16
            if stat.S_ISLNK(file_mode):
                raise ValueError("Update archive contains a symbolic link")
            if member.file_size > MAX_FILE_BYTES:
                raise ValueError(f"Update file is too large: {relative_path}")
            total_size += member.file_size
            if total_size > MAX_TOTAL_FILE_BYTES:
                raise ValueError("Update files exceed the total size limit")
            if relative_path in files:
                raise ValueError(f"Update archive contains duplicate path: {relative_path}")
            files[relative_path] = archive.read(member)

    required_files = CORE_FILES | {"templates/base.html"}
    missing_files = required_files - files.keys()
    if missing_files:
        raise ValueError(
            "Update archive is missing required files: " + ", ".join(sorted(missing_files))
        )
    return files


def _read_state(state_path):
    try:
        with state_path.open("r", encoding="utf-8") as state_file:
            state = json.load(state_file)
        if isinstance(state, dict):
            commit = state.get("commit")
            if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit):
                return state
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError, TypeError):
        LOGGER.warning("Could not read HVM update state; checking the installed files.")
    return {}


def _write_atomic(destination, content, mode=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".hvm-update-", dir=str(destination.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        if mode is not None:
            os.chmod(temporary_path, mode)
        os.replace(temporary_path, destination)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _atomic_update(project_root, commit_sha, files, state_path):
    changed_files = {}
    for relative_path, remote_content in files.items():
        destination = project_root.joinpath(*PurePosixPath(relative_path).parts)
        try:
            current_content = destination.read_bytes()
        except FileNotFoundError:
            current_content = None
        if current_content != remote_content:
            changed_files[relative_path] = (destination, current_content, remote_content)

    if not changed_files:
        state = json.dumps(
            {"commit": commit_sha, "checked_at": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ).encode("utf-8")
        _write_atomic(state_path, state)
        return False

    try:
        previous_state = state_path.read_bytes()
    except FileNotFoundError:
        previous_state = None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = project_root / "backups" / "auto-updates" / timestamp
    for relative_path, (destination, current_content, _) in changed_files.items():
        if current_content is not None:
            backup_path = backup_root.joinpath(*PurePosixPath(relative_path).parts)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup_path)

    applied = []
    try:
        for relative_path, (destination, current_content, remote_content) in changed_files.items():
            existing_mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else None
            _write_atomic(destination, remote_content, existing_mode)
            applied.append((relative_path, destination, current_content, existing_mode))

        state = json.dumps(
            {"commit": commit_sha, "checked_at": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ).encode("utf-8")
        _write_atomic(state_path, state)
    except Exception:
        for relative_path, destination, current_content, existing_mode in reversed(applied):
            try:
                if current_content is None:
                    destination.unlink(missing_ok=True)
                else:
                    _write_atomic(destination, current_content, existing_mode)
            except OSError:
                LOGGER.exception("Failed to restore %s after an update error", relative_path)
        raise

    LOGGER.warning(
        "HVM update %s installed (%d application files). Backup: %s",
        commit_sha,
        len(changed_files),
        backup_root,
    )
    return applied, previous_state


def _rollback_update(applied, previous_state, state_path):
    for relative_path, destination, current_content, existing_mode in reversed(applied):
        try:
            if current_content is None:
                destination.unlink(missing_ok=True)
            else:
                _write_atomic(destination, current_content, existing_mode)
        except OSError:
            LOGGER.exception("Failed to restore %s after restart failure", relative_path)
    try:
        if previous_state is None:
            state_path.unlink(missing_ok=True)
        else:
            _write_atomic(state_path, previous_state)
    except OSError:
        LOGGER.exception("Failed to restore HVM update state after restart failure")


def _check_and_install(project_root, owner, repository, branch):
    commit_sha, archive_bytes = _download_archive(owner, repository, branch)
    state_path = project_root / ".hvm-update-state.json"
    installed_state = _read_state(state_path)
    if installed_state.get("commit") == commit_sha:
        return False

    files = _read_update_files(archive_bytes)
    remote_requirements = files.pop("requirements.txt", None)
    if remote_requirements is not None:
        local_requirements = project_root / "requirements.txt"
        if local_requirements.exists() and local_requirements.read_bytes() != remote_requirements:
            raise RuntimeError(
                "The update changes requirements.txt; install and review dependencies "
                "manually before enabling this release."
            )
    update = _atomic_update(project_root, commit_sha, files, state_path)
    if update:
        applied, previous_state = update
        LOGGER.warning("Restarting HVM to load update %s", commit_sha)
        try:
            os.execv(sys.executable, [sys.executable, *sys.argv])
        except OSError:
            _rollback_update(applied, previous_state, state_path)
            raise
    LOGGER.info("HVM update check complete; installed revision is %s", commit_sha)
    return False


def _update_loop(project_root, owner, repository, branch, interval):
    time.sleep(min(60, interval))
    while True:
        try:
            _check_and_install(project_root, owner, repository, branch)
        except Exception:
            LOGGER.exception(
                "HVM automatic update check failed for %s/%s@%s",
                owner,
                repository,
                branch,
            )
        time.sleep(interval)


def start_auto_updater():
    enabled = os.getenv("HVM_AUTO_UPDATE", "1").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        LOGGER.info("HVM automatic updates are disabled by HVM_AUTO_UPDATE")
        return

    repository = os.getenv("HVM_UPDATE_REPO", DEFAULT_REPOSITORY).strip()
    branch = os.getenv("HVM_UPDATE_BRANCH", DEFAULT_BRANCH).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("HVM_UPDATE_REPO must be in owner/repository format")
    if not branch or len(branch) > 200 or branch.startswith("-"):
        raise ValueError("HVM_UPDATE_BRANCH is invalid")
    try:
        interval = int(os.getenv("HVM_UPDATE_INTERVAL", str(CHECK_INTERVAL_SECONDS)))
    except ValueError as exc:
        raise ValueError("HVM_UPDATE_INTERVAL must be an integer number of seconds") from exc
    if interval < 300:
        raise ValueError("HVM_UPDATE_INTERVAL must be at least 300 seconds")

    owner, repo_name = repository.split("/", 1)
    project_root = Path(__file__).resolve().parent
    thread = threading.Thread(
        target=_update_loop,
        args=(project_root, owner, repo_name, branch, interval),
        name="hvm-auto-updater",
        daemon=True,
    )
    thread.start()
    LOGGER.info(
        "HVM automatic updater enabled for %s@%s (check interval: %s seconds)",
        repository,
        branch,
        interval,
    )
