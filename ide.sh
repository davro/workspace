#!/usr/bin/env bash
set -e

# ----------------------------
# Configuration
# ----------------------------
FILENAME="ide.py"
ACTION="$1"
WORKSPACE_ENV="workspace-env"

# PyQt6-Multimedia
REQUIREMENTS=(
  PyQt6
  PyQt6-WebEngine
  markdown
  requests
  tree-sitter
  tree-sitter-python
  web3
  bip_utils
  cryptography
  argon2
  argon2-cffi
  argon2-cffi-bindings
  psycopg
  yt-dlp
  faster-whisper
)

# ----------------------------
# Functions
# ----------------------------
create_venv() {
  echo "[+] Creating virtual environment: $WORKSPACE_ENV"
  python3 -m venv "$WORKSPACE_ENV"
}

activate_venv() {
  source "$WORKSPACE_ENV/bin/activate"
}

install_packages() {

  echo "[+] Installing system packages"
  sudo apt install yt-dlp
  sudo apt install ffmpeg

  echo "[+] Installing packages"
  pip install --upgrade pip
  pip install "${REQUIREMENTS[@]}"
}

update_packages() {
  echo "[+] Updating packages"
  pip install --upgrade pip
  pip install --upgrade "${REQUIREMENTS[@]}"
}

banner() {
  echo "################################################################################"
  echo "#"
  echo "# Workspace ($FILENAME)"
  echo "# Python venv: $WORKSPACE_ENV"
  echo "# David Stevens <mail.davro@gmail.com>"
  echo "#"
  echo "################################################################################"
}

# ----------------------------
# Logic
# ----------------------------
banner

# Auto-install if venv missing
if [ ! -d "$WORKSPACE_ENV" ]; then
  echo "[!] Virtual environment not found"
  create_venv
  activate_venv
  install_packages
else
  activate_venv
fi

# Manual actions
echo "[+] Action $ACTION"
case "$ACTION" in
  install)
    install_packages
    ;;
  update)
    update_packages
    ;;
  "" )
    # No action
    ;;
  *)
    echo "[!] Unknown action: $ACTION"
    echo "Usage: $0 [file.py] [install|update]"
    exit 1
    ;;
esac

# ----------------------------
# Run application
# ----------------------------
echo "[+] Running $FILENAME"
python "$FILENAME"

# deactivate
