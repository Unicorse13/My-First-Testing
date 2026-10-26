#!/usr/bin/env bash
# Reproducible setup for the synthetic browser demonstration. No external services.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
python3 -m venv .venv
.venv/bin/python -m pip install --cache-dir "${TMPDIR:-/tmp}/permitsnj-pip" -r requirements-dev.txt
(
  cd frontend
  npm ci --cache "${TMPDIR:-/tmp}/permitsnj-npm"
  npm run build
)
DEMO_MODE=true DATABASE_PATH="$project_root/data/permitsnj.sqlite3" .venv/bin/python -c 'from backend.db import initialize; initialize()'
echo 'PermitsNJ is installed. The application starts automatically after Codespaces setup.'
