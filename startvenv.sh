#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate

echo "VENV: $VIRTUAL_ENV"
which python
python -V

