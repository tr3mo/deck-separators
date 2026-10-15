#!/usr/bin/env bash
# Build dist/deck_separators.ankiaddon from the add-on folder.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/deck_separators.ankiaddon
cd deck_separators
zip -r -X -q ../dist/deck_separators.ankiaddon . \
    -x "meta.json" -x "__pycache__/*" -x "*.pyc" -x ".DS_Store"
cd ..
unzip -l dist/deck_separators.ankiaddon
