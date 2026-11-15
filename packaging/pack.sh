#!/bin/sh
# pack.sh APP_DIR VERSION OUT: the launcher with APP_DIR (tar.gz) appended = the release file.
set -eu
here=$(dirname "$0")
head=$(sed "s/@@VERSION@@/$2/" "$here/launcher.sh")
# OFFSET = header bytes + 1 (tail -c +N is 1-based); fixed width, so filling it in keeps the length
len=$(printf '%s\n' "$head" | sed "s/@@OFFSET@@/0000000000/" | wc -c)
printf '%s\n' "$head" | sed "s/@@OFFSET@@/$(printf '%010d' $((len + 1)))/" > "$3"
tar -czf - -C "$1" . >> "$3"
chmod 755 "$3"
