#!/usr/bin/env bash
# Speech2AI2Text Linux Installation & Setup Script

set -euo pipefail

# ANSI color codes for pretty output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0;5m' # No Color
BOLD='\033[1m'
CLEAR='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}${BOLD}====================================================${CLEAR}"
echo -e "${BLUE}${BOLD}        Speech2AI2Text Linux - Installation             ${CLEAR}"
echo -e "${BLUE}${BOLD}====================================================${CLEAR}"

# 1. Check Python version
echo -e "\n${BLUE}[1/4] Verificerer Python...${CLEAR}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Fejl: Python 3 blev ikke fundet på dit system.${CLEAR}"
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "✓ Fundet Python $PYTHON_VERSION"

# 2. Check System Dependencies (xclip, xdotool, python3-tk, libportaudio2)
echo -e "\n${BLUE}[2/4] Undersøger systemafhængigheder...${CLEAR}"
MISSING_SYS_DEPS=()

if ! command -v xclip &> /dev/null; then
    MISSING_SYS_DEPS+=("xclip")
fi

if ! command -v xdotool &> /dev/null; then
    MISSING_SYS_DEPS+=("xdotool")
fi

# Check for python3-tk (tkinter)
if ! python3 -c "import tkinter" &> /dev/null; then
    MISSING_SYS_DEPS+=("python3-tk")
fi

# Check for python3-venv (ensurepip)
if ! python3 -c "import ensurepip" &> /dev/null; then
    MISSING_SYS_DEPS+=("python3-venv")
fi

# Check for libportaudio2 (via dpkg on debian/ubuntu/mint)
if command -v dpkg &> /dev/null; then
    if ! dpkg -s libportaudio2 &>/dev/null; then
        MISSING_SYS_DEPS+=("libportaudio2")
    fi
fi

if [ ${#MISSING_SYS_DEPS[@]} -ne 0 ]; then
    echo -e "${YELLOW}Følgende systempakker mangler:${CLEAR}"
    for dep in "${MISSING_SYS_DEPS[@]}"; do
        echo -e "  - $dep"
    done
    
    echo -e "\nVil du have, at installatøren installerer dem for dig nu? (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo -e "${BLUE}Installerer systemafhængigheder... (kræver sudo-adgang)${CLEAR}"
        sudo apt-get update
        sudo apt-get install -y "${MISSING_SYS_DEPS[@]}"
    else
        echo -e "${RED}Afbrudt. Installer venligst pakkerne manuelt og kør installationsfilen igen:${CLEAR}"
        echo -e "${BOLD}sudo apt-get install -y ${MISSING_SYS_DEPS[*]}${CLEAR}"
        exit 1
    fi
else
    echo -e "✓ Alle systemafhængigheder (xclip, xdotool, tkinter, portaudio) er til stede."
fi

# 3. Create Virtual Environment
echo -e "\n${BLUE}[3/5] Opretter virtuelt Python-miljø (.venv)...${CLEAR}"
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/pip" ]; then
    rm -rf .venv
    python3 -m venv .venv
    echo -e "✓ .venv oprettet."
else
    echo -e "✓ .venv findes allerede."
fi

# 4. Install requirements
echo -e "\n${BLUE}[4/5] Installerer Python-biblioteker...${CLEAR}"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
echo -e "✓ Python biblioteker installeret."

# 5. Create Desktop Launchers and Auto-start
echo -e "\n${BLUE}[5/5] Opretter system-genveje og autostart...${CLEAR}"

LAUNCHERS_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
ICON_PATH="${SCRIPT_DIR}/speech2ai2text_icon.png"

mkdir -p "$LAUNCHERS_DIR"
mkdir -p "$AUTOSTART_DIR"

# 5.1 Speech2AI Start Launcher (System Tray)
cat <<EOF > "${LAUNCHERS_DIR}/speech2ai.desktop"
[Desktop Entry]
Name=Speech2AI Start
Comment=Start baggrundsprogrammet for AI diktering (systembakke)
Exec=${SCRIPT_DIR}/.venv/bin/python ${SCRIPT_DIR}/tray.py
Icon=${ICON_PATH}
Terminal=false
Type=Application
Categories=Utility;AudioVideo;
StartupNotify=false
EOF
chmod +x "${LAUNCHERS_DIR}/speech2ai.desktop"

# 5.2 Speech2AI Settings Launcher
cat <<EOF > "${LAUNCHERS_DIR}/speech2ai-settings.desktop"
[Desktop Entry]
Name=Speech2AI Indstillinger
Comment=Konfigurer AI diktering, API-nøgler og ordbog
Exec=${SCRIPT_DIR}/.venv/bin/python ${SCRIPT_DIR}/settings_gui.py
Icon=${ICON_PATH}
Terminal=false
Type=Application
Categories=Settings;Utility;
StartupNotify=true
EOF
chmod +x "${LAUNCHERS_DIR}/speech2ai-settings.desktop"

# 5.3 Copy System Tray Launcher to Autostart
cp "${LAUNCHERS_DIR}/speech2ai.desktop" "${AUTOSTART_DIR}/speech2ai.desktop"
chmod +x "${AUTOSTART_DIR}/speech2ai.desktop"

# 5.4 Ensure trigger.py has execution permissions
chmod +x "${SCRIPT_DIR}/trigger.py"

echo -e "✓ Desktop-genveje og autostart oprettet succesfuldt!"

# Final Instructions
echo -e "\n${GREEN}${BOLD}====================================================${CLEAR}"
echo -e "${GREEN}${BOLD}         speech2ai er nu installeret!               ${CLEAR}"
echo -e "${GREEN}${BOLD}====================================================${CLEAR}"
echo -e "\nVi har oprettet genveje i din startmenu:\n"
echo -e "  - ${BOLD}Speech2AI Start${CLEAR} (starter ikonet ved uret)"
echo -e "  - ${BOLD}Speech2AI Indstillinger${CLEAR} (åbner konfigurationen)\n"
echo -e "Programmet starter nu automatisk ved login via autostart.\n"
echo -e "Husk at køre ${GREEN}Speech2AI Indstillinger${CLEAR} for at indtaste dine API-nøgler før brug!"

