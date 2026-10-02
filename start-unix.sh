#!/bin/sh
set -eu

APP_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
SYSTEM=$(uname -s)
case "$SYSTEM" in
    Linux)
        VENV_DIR="$APP_DIR/.venv-linux"
        REQUIREMENTS="$APP_DIR/requirements.txt"
        ;;
    Darwin)
        VENV_DIR="$APP_DIR/.venv-macos"
        REQUIREMENTS="$APP_DIR/requirements-macos.txt"
        ;;
    *)
        printf 'Dieses Startskript unterstuetzt Linux und macOS, nicht %s.\n' "$SYSTEM" >&2
        exit 1
        ;;
esac

PYTHON_BIN=${DICOM_PYTHON:-python3}
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf 'Python wurde nicht gefunden. Bitte Python 3.11 bis 3.13 installieren.\n' >&2
    exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] <= (3, 13)))'; then
    printf 'Bitte Python 3.11, 3.12 oder 3.13 verwenden.\n' >&2
    exit 1
fi

VENV_PY="$VENV_DIR/bin/python"
if [ ! -x "$VENV_PY" ]; then
    printf 'Erstelle lokale Python-Umgebung...\n'
    if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        printf 'Python-venv fehlt oder konnte nicht erstellt werden.\n' >&2
        exit 1
    fi
fi

printf 'Pruefe und installiere benoetigte Pakete...\n'
"$VENV_PY" -m pip install --disable-pip-version-check -r "$REQUIREMENTS"
if ! "$VENV_PY" -c 'import tkinter'; then
    printf 'Tkinter fehlt. Installiere die Tk-Unterstuetzung fuer deine Python-Version.\n' >&2
    exit 1
fi

if [ "${1:-}" = '--check' ]; then
    printf 'Alle Pakete und Tkinter sind bereit.\n'
    exit 0
fi

printf 'Starte DICOM Reader...\n'
exec "$VENV_PY" "$APP_DIR/app.py" "$@"
