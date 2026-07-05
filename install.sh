#!/usr/bin/env bash
#
# Hidamari (fork) one-shot installer for Ubuntu / Debian-based systems.
#
#   chmod +x install.sh
#   ./install.sh
#
# Installs all system dependencies, builds with meson and installs into
# /usr/local. Afterwards "Hidamari" shows up in your application menu with an
# icon (no terminal needed) and the `hidamari` command is available.
#
# No Python virtualenv is required: the runtime dependencies are installed as
# regular system packages.
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v apt >/dev/null 2>&1; then
    echo "This installer targets Ubuntu/Debian (apt). For other distros see docs/development.md."
    exit 1
fi

echo "==> [1/3] Installing system dependencies (sudo password may be asked)..."
sudo apt update
sudo apt install -y \
    meson gettext desktop-file-utils \
    python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 gir1.2-webkit2-4.1 \
    gir1.2-appindicator3-0.1 gir1.2-gnomedesktop-4.0 \
    dconf-cli libappindicator3-1 libgnome-desktop-4-2t64 libwebkit2gtk-4.1-0 \
    libwnck-3-0 mesa-utils vdpauinfo xdg-user-dirs \
    vlc python3-vlc python3-pil python3-pydbus python3-requests \
    python3-setproctitle yt-dlp

echo "==> [2/3] Building..."
if [ ! -d build ]; then
    meson setup build
fi
# Compile as the current user first, then only copy files with sudo. This
# avoids the "Permission denied" that happens when meson re-runs the build as
# root and glib-compile-resources cannot write to root's TMPDIR.
meson compile -C build

echo "==> [3/3] Installing into /usr/local (sudo)..."
sudo meson install -C build --no-rebuild

echo
echo "Done! Launch 'Hidamari' from your application menu, or run: hidamari"
echo "To remove it later: ./uninstall.sh"
