#!/bin/sh
# SCRiTCH launcher (v0.7.4+). This is the file Steam starts. The app folder is packed below this
# script (tar.gz). The first start of a new version unpacks it into app/ next to this file (the
# previous app/ is kept as app.old/); every other start runs app/itch-deck straight away.
# packaging/build.sh fills in VERSION and OFFSET (fixed width, so the header length never changes).
V="@@VERSION@@"
OFFSET=@@OFFSET@@
self=$(readlink -f "$0")
here=$(dirname "$self")
app="$here/app"
if [ "$(cat "$app/VERSION" 2>/dev/null)" != "$V" ] || [ ! -x "$app/itch-deck" ]; then
  logs="${XDG_STATE_HOME:-$HOME/.local/state}/itch-deck/logs"
  mkdir -p "$logs"
  new="$here/app.new"
  rm -rf "$new" && mkdir -p "$new"
  if tail -c +"$OFFSET" "$self" | tar -xzf - -C "$new" 2>>"$logs/launcher.log" \
      && [ -x "$new/itch-deck" ] && printf '%s\n' "$V" > "$new/VERSION"; then
    rm -rf "$here/app.old"
    [ -d "$app" ] && mv "$app" "$here/app.old"
    mv "$new" "$app"
    echo "$(date '+%F %T') unpacked v$V into $app" >> "$logs/launcher.log"
  else
    rm -rf "$new"
    echo "$(date '+%F %T') couldn't unpack v$V (disk full?), starting the app already there" >> "$logs/launcher.log"
    [ -x "$app/itch-deck" ] || exit 1
  fi
fi
SCRITCH_LAUNCHER="$self" exec "$app/itch-deck" "$@"
exit 1
