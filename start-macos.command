#!/bin/sh
APP_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P) || exit 1
/bin/sh "$APP_DIR/start-unix.sh" "$@"
STATUS=$?
if [ "$STATUS" -ne 0 ] && [ -t 0 ]; then
    printf '\nStart fehlgeschlagen. Eingabetaste zum Schliessen druecken...'
    read -r _answer
fi
exit "$STATUS"
