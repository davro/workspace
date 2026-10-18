#!/usr/bin/env bash
#
# ide.sh - launcher and environment manager for Workspace.
#
# Usage:
#   ./ide.sh [run] [args...]     Start the IDE. Sets the environment up on first
#                                run and whenever a dependency file changes.
#   ./ide.sh install             Force a full install (system, pip, plugin installers).
#   ./ide.sh update              Upgrade Python packages to the newest allowed versions.
#   ./ide.sh add <pkg>...        Install packages and record them in requirements.txt.
#   ./ide.sh add --plugin <Name> <pkg>...   Same, into that plugin's requirements.txt.
#   ./ide.sh build [patch|minor|major|X.Y.Z]
#                                Release: bump VERSION, tag, and write dist/workspace-<version>.tar.gz
#                                containing a requirements.lock of exact package versions.
#   ./ide.sh help                Show this help.
#
# Where dependencies live:
#   requirements.txt                      core Python deps        (pip, inside the venv)
#   packages-apt.txt                      core system packages    (apt, outside the venv)
#   requirements.lock                     exact versions; only exists inside release tarballs
#                                         (made by `build`, preferred over requirements.txt when present)
#   ide/plugins/<Name>/requirements.txt   plugin Python deps      (pip, inside the venv)
#   ide/plugins/<Name>/install.sh         plugin system tools     (idempotent, outside the venv)
#
# Environment variables:
#   VENV_DIR           Virtual environment location (default: ./workspace-env)
#   IDE_SKIP_INSTALL=1 Skip the dependency check on `run` (handy when offline)

set -euo pipefail
shopt -s nullglob

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/workspace-env}"
PLUGINS_DIR="$ROOT_DIR/ide/plugins"
REQUIREMENTS_FILE="$ROOT_DIR/requirements.txt"
APT_FILE="$ROOT_DIR/packages-apt.txt"
LOCK_FILE="$ROOT_DIR/requirements.lock"
STAMP_FILE="$VENV_DIR/.deps.sha256"

info() { echo "[+] $*"; }
warn() { echo "[!] $*" >&2; }
die()  { warn "$*"; exit 1; }

# ----------------------------------------------------------------------------
# Virtual environment
# ----------------------------------------------------------------------------
ensure_venv() {
    if [ ! -x "$VENV_DIR/bin/python3" ]; then
        info "Creating virtual environment at $VENV_DIR"
        python3 -m venv "$VENV_DIR" \
            || die "Could not create the venv. On Debian/Ubuntu try: sudo apt install python3-venv"
    fi
    set +u   # some activate scripts reference unset variables
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    set -u
}

# ----------------------------------------------------------------------------
# Dependency installation
# ----------------------------------------------------------------------------

# System packages from packages-apt.txt. Only missing ones are installed, so a
# normal launch never asks for sudo.
install_system_packages() {
    if [ ! -f "$APT_FILE" ]; then
        info "No packages-apt.txt, skipping system packages"
        return 0
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        warn "apt-get not found; install the packages in $APT_FILE with your package manager"
        return 0
    fi

    local missing=() line pkg
    while IFS= read -r line || [ -n "$line" ]; do
        pkg="${line%%#*}"
        pkg="${pkg//[[:space:]]/}"
        [ -n "$pkg" ] || continue
        dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
    done < "$APT_FILE"

    if [ "${#missing[@]}" -eq 0 ]; then
        info "System packages OK"
        return 0
    fi

    info "Installing system packages: ${missing[*]}"
    local sudo_cmd=()
    [ "$(id -u)" -eq 0 ] || sudo_cmd=(sudo)
    ${sudo_cmd[@]+"${sudo_cmd[@]}"} apt-get install -y "${missing[@]}"
}

# Core and per-plugin Python packages, installed into the venv.
# Usage: install_python_packages [--upgrade]
install_python_packages() {
    local flags=("$@")

    info "Installing Python packages"
    python3 -m pip install --upgrade pip

    # A release tarball ships requirements.lock (exact versions, plugins included).
    if [ -f "$LOCK_FILE" ]; then
        info "Installing exact versions from requirements.lock"
        python3 -m pip install -r "$LOCK_FILE"
        return 0
    fi

    python3 -m pip install ${flags[@]+"${flags[@]}"} -r "$REQUIREMENTS_FILE"

    local req
    for req in "$PLUGINS_DIR"/*/requirements.txt; do
        info "Python packages for plugin: $(basename "$(dirname "$req")")"
        python3 -m pip install ${flags[@]+"${flags[@]}"} -r "$req"
    done
}

# Plugins can depend on system binaries (k3d, terraform, kubectl, ffmpeg, ...)
# that pip cannot install. Convention: a plugin that needs one ships
# ide/plugins/<PluginName>/install.sh. It must be idempotent (check
# `command -v` before installing anything) and is run outside the venv, since
# it installs system tools rather than Python packages.
install_plugin_dependencies() {
    info "Checking plugin dependencies"

    if [ ! -d "$PLUGINS_DIR" ]; then
        warn "No plugins directory found at $PLUGINS_DIR, skipping"
        return 0
    fi

    local found=0 script name
    for script in "$PLUGINS_DIR"/*/install.sh; do
        found=1
        name="$(basename "$(dirname "$script")")"
        info "Running plugin installer: $name"
        # Subshell: leave the venv so the installer sees the system PATH.
        if ( if type deactivate >/dev/null 2>&1; then deactivate; fi; bash "$script" ); then
            info "$name dependencies OK"
        else
            warn "$name installer exited non-zero - continuing"
        fi
    done

    if [ "$found" -eq 0 ]; then
        info "No plugin install.sh scripts found"
    fi
}

# ----------------------------------------------------------------------------
# Change detection: reinstall only when a dependency file has changed.
# ----------------------------------------------------------------------------
deps_hash() {
    local files
    mapfile -t files < <(
        cd "$ROOT_DIR"
        ls requirements.txt requirements.lock packages-apt.txt \
           ide/plugins/*/requirements.txt ide/plugins/*/install.sh 2>/dev/null | sort
    )
    [ "${#files[@]}" -gt 0 ] || { echo "none"; return 0; }
    (cd "$ROOT_DIR" && sha256sum "${files[@]}") | sha256sum | cut -d' ' -f1
}

needs_install() {
    [ ! -f "$STAMP_FILE" ] || [ "$(cat "$STAMP_FILE")" != "$(deps_hash)" ]
}

full_install() {
    [ -f "$REQUIREMENTS_FILE" ] || die "Missing $REQUIREMENTS_FILE"
    install_system_packages
    install_python_packages
    install_plugin_dependencies
    deps_hash > "$STAMP_FILE"
    info "Environment ready"
}

# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
cmd_run() {
    ensure_venv
    if [ "${IDE_SKIP_INSTALL:-0}" != "1" ] && needs_install; then
        full_install
    fi
    exec python3 "$ROOT_DIR/ide.py" "$@"
}

cmd_install() {
    ensure_venv
    full_install
}

cmd_update() {
    ensure_venv
    info "Updating packages"
    install_python_packages --upgrade
    deps_hash > "$STAMP_FILE"
}

# Install package(s) and record them, without freezing the whole environment.
# "requests"        -> installs it, appends "requests>=<installed version>"
# "requests>=2,<3"  -> installs it, appends the spec exactly as typed
cmd_add() {
    local target="$REQUIREMENTS_FILE"
    if [ "${1:-}" = "--plugin" ]; then
        [ -n "${2:-}" ] || die "Usage: ./ide.sh add --plugin <PluginName> <package>..."
        [ -d "$PLUGINS_DIR/$2" ] || die "No such plugin: $PLUGINS_DIR/$2"
        target="$PLUGINS_DIR/$2/requirements.txt"
        shift 2
    fi
    [ "$#" -gt 0 ] || die "Usage: ./ide.sh add [--plugin <PluginName>] <package>..."

    ensure_venv
    local spec name version rel="${target#"$ROOT_DIR"/}"
    for spec in "$@"; do
        name="${spec%%[<>=!~\[ ;]*}"
        python3 -m pip install "$spec"   # a failure stops here, before anything is recorded
        if grep -qiE "^${name}([<>=!~[ ;]|$)" "$target" 2>/dev/null; then
            info "$name is already listed in $rel"
            continue
        fi
        if [ "$spec" = "$name" ]; then
            version="$(python3 -c 'import sys; from importlib.metadata import version; print(version(sys.argv[1]))' "$name")"
            spec="$name>=$version"
        fi
        # Make sure the previous line ends with a newline before appending.
        if [ -s "$target" ] && [ -n "$(tail -c1 "$target")" ]; then echo >> "$target"; fi
        echo "$spec" >> "$target"
        info "Added $spec to $rel"
    done
}

# Exact versions of everything the IDE and its plugins need, resolved in a
# throwaway venv so dev tools (pytest, build, ...) never leak into the release.
# Usage: freeze_requirements <output-file>
freeze_requirements() {
    local tmp req args=(-r "$REQUIREMENTS_FILE")
    for req in "$PLUGINS_DIR"/*/requirements.txt; do
	echo "Plugin: $req"
        args+=(-r "$req")
    done
    tmp="$(mktemp -d)"
    info "Resolving dependencies in a clean environment"
    python3 -m venv "$tmp/venv"
    "$tmp/venv/bin/python" -m pip install -q "${args[@]}"
    {
        echo "# Generated by ./ide.sh build - exact versions of everything installed. Do not edit."
        "$tmp/venv/bin/python" -m pip freeze
    } > "$1"
    rm -rf "$tmp"
}

# Rewrites VERSION in ide/__init__.py and prints the new version.
# Usage: bump_version patch|minor|major|X.Y.Z
bump_version() {
    python3 - "$ROOT_DIR/ide/__init__.py" "$1" <<'PY'
import re, sys
path, part = sys.argv[1:3]
text = open(path, encoding="utf-8").read()
m = re.search(r'^VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"', text, re.M)
if not m:
    sys.exit('VERSION = "X.Y.Z" not found in ' + path)
major, minor, patch = map(int, m.groups())
if part == "patch":
    patch += 1
elif part == "minor":
    minor, patch = minor + 1, 0
elif part == "major":
    major, minor, patch = major + 1, 0, 0
else:
    major, minor, patch = map(int, part.split("."))
new = f"{major}.{minor}.{patch}"
open(path, "w", encoding="utf-8").write(text[:m.start()] + f'VERSION = "{new}"' + text[m.end():])
print(new)
PY
}

# Release: test, freeze, bump, commit, tag, package. Nothing is pushed.
cmd_build() {
    local part="${1:-patch}" lock new stage
    case "$part" in
        patch|minor|major|[0-9]*.[0-9]*.[0-9]*) ;;
        *) die "Usage: ./ide.sh build [patch|minor|major|X.Y.Z]" ;;
    esac

    #command -v git >/dev/null 2>&1 || die "git is required to build"
    #git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "Not a git repository"
    #[ -z "$(git -C "$ROOT_DIR" status --porcelain --untracked-files=no)" ] \
    #    || die "You have uncommitted changes - commit or stash them first"

    ensure_venv
    if python3 -c "import pytest" >/dev/null 2>&1; then
        info "Running tests"
        (cd "$ROOT_DIR" && python3 -m pytest -q) || die "Tests failed - not building"
    else
        warn "pytest not installed, skipping tests"
    fi

    lock="$(mktemp)"
    freeze_requirements "$lock"

    new="$(bump_version "$part")"

    #if git -C "$ROOT_DIR" rev-parse -q --verify "refs/tags/v$new" >/dev/null; then
    #    git -C "$ROOT_DIR" checkout -- ide/__init__.py
    #    die "Tag v$new already exists"
    #fi
    #git -C "$ROOT_DIR" add ide/__init__.py
    #git -C "$ROOT_DIR" commit -q -m "Release v$new"
    #git -C "$ROOT_DIR" tag -a "v$new" -m "Release v$new"

    # Package exactly what was tagged, plus the lock file.
    #stage="$(mktemp -d)"
    #mkdir -p "$ROOT_DIR/dist"
    #git -C "$ROOT_DIR" archive --prefix="workspace-$new/" "v$new" | tar -x -C "$stage"
    #cp "$lock" "$stage/workspace-$new/requirements.lock"
    #tar -czf "$ROOT_DIR/dist/workspace-$new.tar.gz" -C "$stage" "workspace-$new"
    #rm -rf "$stage" "$lock"

    #info "Built dist/workspace-$new.tar.gz (committed and tagged v$new; push with: git push --follow-tags)"
}

usage() {
    sed -n '3,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

main() {
    local cmd="run"
    if [ "$#" -gt 0 ]; then
        cmd="$1"
        shift
    fi
    case "$cmd" in
        run)              cmd_run "$@" ;;
        install)          cmd_install ;;
        update)           cmd_update ;;
        add)              cmd_add "$@" ;;
        build)            cmd_build "$@" ;;
        help|-h|--help)   usage ;;
        -*)               cmd_run "$cmd" "$@" ;;   # ./ide.sh --some-flag -> IDE args
        *)                warn "Unknown command: $cmd"; usage; exit 2 ;;
    esac
}

main "$@"
