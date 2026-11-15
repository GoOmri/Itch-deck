#!/bin/sh
# SCRiTCH launcher (v0.7.4+). This is the file Steam starts. The app folder is packed below this
# script (tar.gz). The first start of a new version unpacks it into app/ next to this file (the
# previous app/ is kept as app.old/); every other start runs app/scritch straight away.
# packaging/build.sh fills in VERSION and OFFSET (fixed width, so the header length never changes).
V="@@VERSION@@"
OFFSET=@@OFFSET@@
self=$(readlink -f "$0")
here=$(dirname "$self")
app="$here/app"
if [ "$(cat "$app/VERSION" 2>/dev/null)" != "$V" ] || [ ! -x "$app/scritch" ]; then
  # v0.8.2 renamed the folders itch-deck -> scritch; the app moves them at its first start, which
  # is AFTER this. Write into the old folder while it's still there, so the move isn't blocked.
  state="${XDG_STATE_HOME:-$HOME/.local/state}"
  logs="$state/scritch/logs"
  [ ! -e "$state/scritch" ] && [ -d "$state/itch-deck" ] && logs="$state/itch-deck/logs"
  mkdir -p "$logs"
  new="$here/app.new"
  rm -rf "$new" && mkdir -p "$new"
  if tail -c +"$OFFSET" "$self" | tar -xzf - -C "$new" 2>>"$logs/launcher.log" \
      && [ -x "$new/scritch" ] && printf '%s\n' "$V" > "$new/VERSION"; then
    rm -rf "$here/app.old"
    [ -d "$app" ] && mv "$app" "$here/app.old"
    mv "$new" "$app"
    echo "$(date '+%F %T') unpacked v$V into $app" >> "$logs/launcher.log"
  else
    rm -rf "$new"
    echo "$(date '+%F %T') couldn't unpack v$V (disk full?), starting the app already there" >> "$logs/launcher.log"
    [ -x "$app/scritch" ] || exit 1
  fi
fi
SCRITCH_LAUNCHER="$self" exec "$app/scritch" "$@"
exit 1
