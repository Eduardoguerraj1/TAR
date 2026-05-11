#!/usr/bin/env bash
set -euxo pipefail

echo "=== Render build diagnostic ==="
pwd
python --version
git rev-parse HEAD || true
ls -la
echo "--- requirements.txt ---"
cat requirements.txt
echo "--- requirements-render.txt ---"
cat requirements-render.txt || true
if grep -R "scipy" -n requirements*.txt pyproject.toml setup.py setup.cfg 2>/dev/null; then
  echo "SciPy must not be installed during Render build."
  exit 2
fi
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -r requirements.txt
