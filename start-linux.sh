#!/bin/sh
APP_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P) || exit 1
exec /bin/sh "$APP_DIR/start-unix.sh" "$@"
