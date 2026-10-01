#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

editor_python=""
for candidate in .venv/bin/python .venv/Scripts/python.exe ../.venv/bin/python ../.venv/Scripts/python.exe; do
    if [[ -f "$candidate" && -x "$candidate" ]]; then
        editor_python="$candidate"
        break
    fi
done

if [[ -z "$editor_python" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        bootstrap_python=python3
    elif command -v python >/dev/null 2>&1; then
        bootstrap_python=python
    else
        echo 'Python was not found. Install Python 3 and try again.' >&2
        exit 1
    fi
    "$bootstrap_python" -m venv .venv
    if [[ -x .venv/bin/python ]]; then
        editor_python=.venv/bin/python
    else
        editor_python=.venv/Scripts/python.exe
    fi
fi

if ! "$editor_python" -c 'import pymupdf' >/dev/null 2>&1; then
    echo 'Installing required packages...'
    "$editor_python" -m pip install -r requirements.txt
fi

echo 'Open http://127.0.0.1:8000 in your browser.'
echo 'Keep this terminal open. Press Ctrl+C to stop the app.'
exec "$editor_python" pdf_editor.py
