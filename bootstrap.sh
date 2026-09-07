#!/usr/bin/env bash
# Bootstrap a fresh Raspberry Pi OS installation into a runnable GonKenLab Agent.
# Intended for use from a terminal with internet access.

set -Eeuo pipefail

REPO_URL="${GONKEN_REPO_URL:-https://github.com/mukulu/gonkenlabagent.git}"
BRANCH="${GONKEN_BRANCH:-main}"
INSTALL_DIR="${GONKEN_INSTALL_DIR:-$HOME/gonkenlabagent}"

fail() {
  echo "[ERROR] $*" >&2
  exit 1
}

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  command -v sudo >/dev/null 2>&1 || fail "sudo is required on Raspberry Pi OS."
  SUDO="sudo"
fi

command -v apt-get >/dev/null 2>&1 || \
  fail "This bootstrap script expects Raspberry Pi OS/Debian with apt-get."

missing_packages=()
command -v git >/dev/null 2>&1 || missing_packages+=(git)
command -v curl >/dev/null 2>&1 || missing_packages+=(curl)
command -v ca-certificates >/dev/null 2>&1 || true

if [ "${#missing_packages[@]}" -gt 0 ] || [ ! -f /etc/ssl/certs/ca-certificates.crt ]; then
  echo "[INFO] Installing bootstrap requirements …"
  $SUDO apt-get update
  $SUDO apt-get install -y git curl ca-certificates
fi

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "[INFO] Existing GonKenLab Agent checkout found at $INSTALL_DIR"

  if ! git -C "$INSTALL_DIR" diff --quiet \
      || ! git -C "$INSTALL_DIR" diff --cached --quiet; then
    fail "The existing checkout has uncommitted changes. Commit or stash them before bootstrapping."
  fi

  origin_url="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
  case "$origin_url" in
    *mukulu/gonkenlabagent*) ;;
    *) fail "Existing checkout has an unexpected origin: ${origin_url:-none}" ;;
  esac

  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" switch "$BRANCH" 2>/dev/null \
    || git -C "$INSTALL_DIR" switch -c "$BRANCH" --track "origin/$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
elif [ -e "$INSTALL_DIR" ] && [ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null || true)" ]; then
  fail "$INSTALL_DIR already exists and is not an empty GonKenLab Agent checkout."
else
  echo "[INFO] Cloning GonKenLab Agent into $INSTALL_DIR …"
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$INSTALL_DIR"
fi

chmod +x "$INSTALL_DIR/setup.sh"

echo "[INFO] Starting full GonKenLab Agent setup …"
exec "$INSTALL_DIR/setup.sh"
