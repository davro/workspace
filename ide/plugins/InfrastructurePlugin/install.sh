#!/usr/bin/env bash
# ide/plugins/InfrastructurePlugin/install.sh
#
# System-level dependencies for the Infrastructure plugin: k3d, kubectl,
# terraform, and Docker. Run automatically by ide.sh via
# install_plugin_dependencies() on `./ide.sh install` / `./ide.sh update`,
# or run directly with `bash install.sh`.
#
# Every install_* function checks `command -v` first, so re-running this
# is always safe and never reinstalls something that's already there.
# Assumes a Debian/Ubuntu host (apt, matching the rest of ide.sh) — on
# anything else, skip this script and install the tools manually.
#
# NOTE on Docker group membership: adding your user to the `docker` group
# only takes effect in a new login session. If `docker info` still fails
# with "permission denied" right after this script runs, log out and back
# in (or run `newgrp docker`) rather than assuming the install failed.

set -e

install_k3d() {
  if command -v k3d &>/dev/null; then
    echo "[Infrastructure Plugin] k3d already installed ($(k3d version | head -1))"
    return
  fi
  echo "[Infrastructure Plugin] Installing k3d..."
  curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
}

install_kubectl() {
  if command -v kubectl &>/dev/null; then
    echo "[Infrastructure Plugin] kubectl already installed ($(kubectl version --client --short 2>/dev/null || echo present))"
    return
  fi
  echo "[Infrastructure Plugin] Installing kubectl..."
  local version
  version=$(curl -sL https://dl.k8s.io/release/stable.txt)
  curl -sLO "https://dl.k8s.io/release/${version}/bin/linux/amd64/kubectl"
  chmod +x kubectl
  sudo mv kubectl /usr/local/bin/kubectl
}

install_terraform() {
  if command -v terraform &>/dev/null; then
    echo "[Infrastructure Plugin] terraform already installed ($(terraform -version | head -1))"
    return
  fi
  echo "[Infrastructure Plugin] Installing terraform via HashiCorp apt repo..."
  sudo apt-get update
  sudo apt-get install -y gnupg software-properties-common curl
  wget -O- https://apt.releases.hashicorp.com/gpg | \
    sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    sudo tee /etc/apt/sources.list.d/hashicorp.list
  sudo apt-get update
  sudo apt-get install -y terraform
}

install_helm() {
  if command -v helm &>/dev/null; then
    echo "[Infrastructure Plugin] helm already installed ($(helm version --short 2>/dev/null || echo present))"
    return
  fi
  echo "[Infrastructure Plugin] Installing helm via the official get-helm-3 script..."
  curl -s https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
}

install_docker() {
  if command -v docker &>/dev/null; then
    echo "[Infrastructure Plugin] docker already installed ($(docker --version))"
  else
    echo "[Infrastructure Plugin] Installing docker (docker.io via apt)..."
    sudo apt-get update
    sudo apt-get install -y docker.io
    sudo systemctl enable --now docker
  fi

  # Add the invoking user to the docker group so `docker`/k3d commands
  # don't need sudo. This only takes effect in a NEW login session - it
  # will NOT apply to the shell currently running this script.
  if ! groups "$USER" | grep -qw docker; then
    sudo usermod -aG docker "$USER"
    echo "[Infrastructure Plugin] Added $USER to the docker group."
    echo "    This needs a new session to take effect - log out and back in,"
    echo "    or run 'newgrp docker' in any terminal you use afterwards."
  fi
}

check_container_runtime() {
  # Podman is a valid alternative to Docker for k3d - if the user already
  # has that instead, don't force Docker on top of it.
  if command -v podman &>/dev/null && ! command -v docker &>/dev/null; then
    echo "[Infrastructure Plugin] podman found — k3d is ready to use"
    return
  fi
  install_docker
}

echo "[Infrastructure Plugin] Checking dependencies..."
install_k3d
install_kubectl
install_terraform
install_helm
check_container_runtime
echo "[Infrastructure Plugin] Dependency check complete."