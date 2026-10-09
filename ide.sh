#!/usr/bin/env bash
set -e

# ----------------------------
# Configuration
# ----------------------------
FILENAME="ide.py"
ACTION="$1"
WORKSPACE_ENV="workspace-env"
PLUGINS_DIR="ide/plugins"

# PyQt6-Multimedia
REQUIREMENTS=(
  PyQt6
  PyQt6-WebEngine
  markdown
  requests
  tree-sitter
  tree-sitter-python
  Send2Trash
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
# torch is installed separately via install_torch() to get the correct
# CUDA build. Do NOT add it back to REQUIREMENTS — pip install from PyPI
# gives the CPU-only build and silently breaks GPU transcription.

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

install_plugin_dependencies() {
  # Plugins can depend on system binaries (k3d, terraform, kubectl, ...)
  # that pip has no way to install. Convention: a plugin that needs one
  # ships ide/plugins/<PluginName>/install.sh, which is expected to be
  # idempotent (check `command -v` before installing anything) and is
  # run as-is, outside the venv, since it's installing system tools
  # rather than Python packages.
  echo "[+] Checking plugin dependencies"

  if [ ! -d "$PLUGINS_DIR" ]; then
    echo "[!] No plugins directory found at $PLUGINS_DIR, skipping"
    return
  fi

  local found=0
  for install_script in "$PLUGINS_DIR"/*/install.sh; do
    [ -e "$install_script" ] || continue
    found=1
    local plugin_name
    plugin_name=$(basename "$(dirname "$install_script")")
    echo "[+] Running plugin installer: $plugin_name"
    if bash "$install_script"; then
      echo "[+] $plugin_name dependencies OK"
    else
      echo "[!] $plugin_name installer exited non-zero — continuing"
    fi
  done

  if [ "$found" -eq 0 ]; then
    echo "[+] No plugin install.sh scripts found"
  fi
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
  install_plugin_dependencies
else
  activate_venv
fi

# Manual actions
echo "[+] Action $ACTION"
case "$ACTION" in
  install)
    install_packages
    install_plugin_dependencies
    ;;
  update)
    update_packages
    install_plugin_dependencies
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
