#!/bin/sh
# Build the release file: PyInstaller folder build, packed behind packaging/launcher.sh.
#   sh packaging/build.sh            -> release/scritch (what CI publishes, also as release/itch-deck for v0.8.1 and older)
set -eu
cd "$(dirname "$0")/.."
V=$(grep -oP 'VERSION = "\K[^"]+' itch_deck/app.py)
# gogdl (vendored, GPL-3) is imported only in the hidden --gogdl mode, so name it explicitly
pyinstaller -y --onedir --name scritch --add-data itch_deck/assets:itch_deck/assets \
  --add-data packaging/steam-art:steam-art \
  --paths itch_deck/vendor --collect-submodules gogdl --hidden-import gogdl_xdelta3 \
  --hidden-import requests run.py
mkdir -p release
sh packaging/pack.sh dist/scritch "$V" release/scritch
cp release/scritch release/itch-deck     # same file under the old name: older updaters look for it
echo "release/scritch v$V: $(du -h release/scritch | cut -f1)"
