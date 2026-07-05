#!/usr/bin/env bash
#
# Remove a Hidamari install done via install.sh / meson (from /usr/local).
#
#   chmod +x uninstall.sh
#   ./uninstall.sh
#
# Does NOT remove the system dependencies installed by install.sh, nor your
# personal config in ~/.config/hidamari.
set -euo pipefail

echo "==> Stopping Hidamari..."
pkill -f hidamari || true

echo "==> Removing installed files (sudo)..."
sudo rm -rf /usr/local/share/hidamari
sudo rm -f /usr/local/bin/hidamari
sudo rm -f /usr/local/share/appdata/io.github.jeffshee.Hidamari.appdata.xml
sudo rm -f /usr/local/share/applications/io.github.jeffshee.Hidamari.desktop
sudo rm -f /usr/local/share/glib-2.0/schemas/io.github.jeffshee.Hidamari.gschema.xml
sudo rm -f /usr/local/share/icons/hicolor/scalable/apps/io.github.jeffshee.Hidamari.svg

echo "==> Refreshing caches..."
sudo update-desktop-database -q /usr/local/share/applications 2>/dev/null || true
sudo glib-compile-schemas /usr/local/share/glib-2.0/schemas 2>/dev/null || true

echo "Done. Hidamari has been removed from /usr/local."
