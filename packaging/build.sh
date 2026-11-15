#!/bin/sh
# Build the release file: PyInstaller folder build, packed behind packaging/launcher.sh.
#   sh packaging/build.sh            -> release/itch-deck (what CI publishes)
set -eu
cd "$(dirname "$0")/.."
V=$(grep -oP 'VERSION = "\K[^"]+' itch_deck/app.py)
pyinstaller -y --onedir --name itch-deck --add-data itch_deck/assets:itch_deck/assets run.py
mkdir -p release
sh packaging/pack.sh dist/itch-deck "$V" release/itch-deck
echo "release/itch-deck v$V: $(du -h release/itch-deck | cut -f1)"
