#!/usr/bin/env bash
# Run the full test suite. Requires .venv (see README / docs/setup.md).
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    echo "error: .venv missing. Set it up with:"
    echo "  python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi
.venv/bin/python -m unittest discover -s tests -v
