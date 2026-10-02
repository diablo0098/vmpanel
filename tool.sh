#!/bin/bash
clear

# ==========================
# COLORS
# ==========================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# ==========================
# EPIC BANNER
# ==========================
echo -e "${RED}â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—${NC}"
echo -e "${RED}â•‘${NC}           ${PURPLE}âš¡ AYUSHTHEWARRIOR INSTALLER âš¡${NC}            ${RED}â•‘${NC}"
echo -e "${RED}â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£${NC}"
echo -e "${RED}â•‘${NC}          ${CYAN}Only for Warriors â€¢ Built Different${NC}          ${RED}â•‘${NC}"
echo -e "${RED}â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•${NC}"
echo ""

# OS Detection (same as before)
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo -e "${RED}âŒ Cannot detect OS.${NC}"
    exit 1
fi

if [[ "$OS" != "ubuntu" && "$OS" != "debian" ]]; then
    echo -e "${RED}âŒ Unsupported OS: $OS${NC}"
    exit 1
fi

echo -e "${GREEN}âœ… OS Detected: ${WHITE}$OS${NC}\n"
sleep 1

# ==========================
# MAIN MENU LOOP
# ==========================
while true; do
    clear
    echo -e "${RED}â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—${NC}"
    echo -e "${RED}â•‘${NC}           ${PURPLE}âš¡ AYUSHTHEWARRIOR INSTALLER âš¡${NC}            ${RED}â•‘${NC}"
    echo -e "${RED}â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•${NC}"
    echo ""
    echo -e "   ${CYAN}1.${NC} ${WHITE}AGVM Panel Installer${NC}"
    echo -e "   ${CYAN}2.${NC} ${WHITE}AGVM 5.1 Installer${NC}"
    echo -e "   ${CYAN}3.${NC} ${WHITE}LXC / LXD Installer${NC}"
    echo -e "   ${CYAN}4.${NC} ${WHITE}Cloudflare Tunnel Setup${NC}"
    echo -e "   ${RED}0.${NC} ${WHITE}Exit${NC}"
    echo ""
    
    # â†â†â† This is the new cleaner prompt you wanted
    echo -ne "${YELLOW}âžœ${NC} ${WHITE}Enter your choice [0-4]: ${NC}"
    read -r choice

    case $choice in
        1)
            echo -e "\n${GREEN}ðŸš€ Launching AGVM Panel...${NC}\n"
            bash <(curl -fsSL https://raw.githubusercontent.com/OfficialCodesHub/loll/refs/heads/main/lol)
            ;;
        2)
            echo -e "\n${GREEN}âš™ï¸ Installing AGVM 5.1...${NC}\n"
            apt update -y && apt install git -y
            git clone https://github.com/hui12345u7/32350-0i005i90i9
            cd 32350-0i005i90i9 || exit 1
            apt install python3-pip -y
            mkdir -p ~/.config/pip
            echo -e "[global]\nbreak-system-packages = true" > ~/.config/pip/pip.conf
            pip install -r requirements.txt
            # (service file and python run part remains same)
            cat <<EOF > /etc/systemd/system/AGVM.service
[Unit]
Description=AGVM Panel (Discord Bot)
After=network.target
[Service]
User=root
WorkingDirectory=/root/AGVM
ExecStart=/usr/bin/python3 /root/AGVM/AGVM.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
[Install]
WantedBy=multi-user.target
EOF
            python3 AGVM-5.1.py
            ;;
        3)
            echo -e "\n${GREEN}ðŸŒ Installing LXC/LXD...${NC}\n"
            bash <(curl -fsSL https://raw.githubusercontent.com/OfficialCodesHub/One-click-Cmds/refs/heads/main/lxd%20installer)
            ;;
        4)
            echo -e "\n${CYAN}â˜ï¸ Setting up Cloudflare...${NC}\n"
            sudo mkdir -p --mode=0755 /usr/share/keyrings
            curl -fsSL https://pkg.cloudflare.com/cloudflare-public-v2.gpg | sudo tee /usr/share/keyrings/cloudflare-public-v2.gpg >/dev/null
            echo 'deb [signed-by=/usr/share/keyrings/cloudflare-public-v2.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
            sudo apt-get update && sudo apt-get install cloudflared -y
            read -p "${YELLOW}Enter Cloudflare Tunnel Token: ${NC}" token
            [ -n "$token" ] && cloudflared service install "$token"
            ;;
        0)
            echo -e "\n${PURPLE}ðŸ‘‘ Thank you, Warrior! Stay Legendary âš¡${NC}\n"
            exit 0
            ;;
        *)
            echo -e "\n${RED}âŒ Invalid choice! Try again.${NC}"
            sleep 1.2
            ;;
    esac

    echo ""
    read -p "${CYAN}Press Enter to continue...${NC}"
done

