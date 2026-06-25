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

install_torch() {
  # Detect GPU compute capability AND CUDA driver version, then pick the
  # correct PyTorch wheel.  Driver version alone is not enough — Pascal GPUs
  # (sm_61, GTX 10xx) need cu118 even with a CUDA 12.x driver, because
  # PyTorch cu121/cu124/cu128 wheels dropped sm_61 support.
  #
  # Compute capability → minimum PyTorch CUDA wheel:
  #   sm_61 (Pascal:  GTX 10xx, 1080 Ti)  → MUST use cu118
  #   sm_70 (Volta:   V100)                → cu118 or newer
  #   sm_75 (Turing:  RTX 20xx, GTX 16xx) → cu121 or newer
  #   sm_80 (Ampere:  RTX 30xx, A100)     → cu121 or newer
  #   sm_86 (Ampere:  RTX 30xx hi)        → cu121 or newer
  #   sm_89 (Ada:     RTX 40xx)           → cu124 or newer
  #   sm_90 (Hopper:  H100)               → cu128 or newer
  #   sm_100 (Blackwell: RTX 50xx)        → cu128

  local index_url=""

  if ! command -v nvidia-smi &>/dev/null; then
    echo "[!] nvidia-smi not found — installing CPU-only torch"
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    _torch_sanity
    return
  fi

  # Get compute capability via nvidia-smi (major * 10 + minor, e.g. 61 for sm_61)
  local cc_major cc_minor cc
  cc_major=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null \
             | head -1 | cut -d. -f1 | tr -d ' ')
  cc_minor=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null \
             | head -1 | cut -d. -f2 | tr -d ' ')
  cc=$(( cc_major * 10 + cc_minor ))   # e.g. 61 for sm_6.1

  # Also get driver CUDA version for display
  local cuda_full
  cuda_full=$(nvidia-smi 2>/dev/null | grep -oP "CUDA Version: \K[0-9]+\.[0-9]+" | head -1)

  echo "[+] GPU compute capability: sm_${cc_major}.${cc_minor}  (cc=${cc})"
  echo "[+] Driver CUDA version: ${cuda_full:-unknown}"

  if   [ "$cc" -le 62 ]; then
    # Pascal and older (sm_60, sm_61, sm_62) — cu118 is the last wheel with sm_61
    echo "[+] Pascal GPU detected — using cu118 (last wheel supporting sm_61)"
    index_url="https://download.pytorch.org/whl/cu118"
  elif [ "$cc" -le 72 ]; then
    # Volta (sm_70, sm_72)
    echo "[+] Volta GPU detected — using cu118"
    index_url="https://download.pytorch.org/whl/cu118"
  elif [ "$cc" -le 75 ]; then
    # Turing (sm_75: RTX 20xx, GTX 16xx)
    echo "[+] Turing GPU detected — using cu121"
    index_url="https://download.pytorch.org/whl/cu121"
  elif [ "$cc" -le 86 ]; then
    # Ampere (sm_80, sm_86: RTX 30xx, A100, A30)
    echo "[+] Ampere GPU detected — using cu124"
    index_url="https://download.pytorch.org/whl/cu124"
  elif [ "$cc" -le 89 ]; then
    # Ada Lovelace (sm_89: RTX 40xx)
    echo "[+] Ada Lovelace GPU detected — using cu124"
    index_url="https://download.pytorch.org/whl/cu124"
  else
    # Hopper / Blackwell (sm_90+: H100, RTX 50xx)
    echo "[+] Hopper/Blackwell GPU detected — using cu128"
    index_url="https://download.pytorch.org/whl/cu128"
  fi

  echo "[+] Installing torch from: $index_url"
  pip install torch --index-url "$index_url" --force-reinstall
  _torch_sanity
}

_torch_sanity() {
  # Quick sanity check — print GPU name and confirm CUDA is usable
  python3 - <<'EOF'
import torch
cuda_ok = torch.cuda.is_available()
print(f"[+] torch {torch.__version__}  |  CUDA available: {cuda_ok}")
if cuda_ok:
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        print(f"    GPU {i}: {p.name}  {p.total_memory/1024**3:.1f} GB  compute {p.major}.{p.minor}")
else:
    print("    No CUDA GPU visible — transcription will run on CPU")
EOF
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
  install_torch
else
  activate_venv
fi

# Manual actions
echo "[+] Action $ACTION"
case "$ACTION" in
  install)
    install_packages
    install_torch
    ;;
  update)
    update_packages
    install_torch
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