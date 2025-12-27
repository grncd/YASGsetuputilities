#!/bin/bash

# Function to show popup
show_popup() {
    local title="$1"
    local message="$2"
    
    if command -v zenity &> /dev/null; then
        zenity --error --title="$title" --text="$message"
    elif command -v kdialog &> /dev/null; then
        kdialog --error "$message" --title "$title"
    elif command -v xmessage &> /dev/null; then
        xmessage -center -title "$title" "$message"
    else
        echo "!!! [$title] $message !!!"
    fi
}

echo "[0%] Starting Linux setup process..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    msg="Python 3 is not installed.\nPlease install it using your package manager.\nExample: sudo apt install python3"
    echo -e "[ERROR] $msg"
    show_popup "Missing Dependency: Python 3" "$msg"
    exit 1
fi

echo "[10%] Python 3 found."

# Create venv
# On some distros (Ubuntu/Debian), python3-venv is a separate package.
if ! python3 -m venv venv; then
    msg="Failed to create virtual environment.\nYou usually need to install 'python3-venv'.\nExample: sudo apt install python3-venv"
    echo -e "[ERROR] $msg"
    show_popup "Missing Dependency: python3-venv" "$msg"
    exit 1
fi

echo "[50%] Virtual environment created at $(pwd)/venv"

# Activate source
source venv/bin/activate

echo "[75%] Installing dependencies..."
pip install --upgrade pip
pip install selenium
# pip install pywin32 # Not needed on Linux
pip install pyperclip
pip install undetected-chromedriver
pip install setuptools==68.0.0

echo "[90%] Checking for Google Chrome..."
if command -v google-chrome &> /dev/null || command -v google-chrome-stable &> /dev/null || command -v chromium &> /dev/null || command -v chromium-browser &> /dev/null; then
    echo "Google Chrome/Chromium detected."
else
    msg="Google Chrome not found in PATH.\nPlease install Google Chrome for Spotify authentication."
    echo -e "[WARNING] $msg"
    # This is just a warning, maybe show info popup?
    if command -v zenity &> /dev/null; then
        zenity --warning --title="Chrome Not Found" --text="$msg"
    elif command -v kdialog &> /dev/null; then
        kdialog --msgbox "$msg" --title "Chrome Not Found"
    fi
fi

echo "[100%] Setup completed successfully!"
