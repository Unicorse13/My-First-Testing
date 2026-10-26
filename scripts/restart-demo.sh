#!/usr/bin/env bash
# Set an explicit HTTPS browser origin and restart only this demo's owned process.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."
.venv/bin/python - "${1:-}" <<'PY'
import os
import signal
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
origin = sys.argv[1].rstrip('/')
url = urlsplit(origin)
if url.scheme != 'https' or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
    raise SystemExit('Supply the HTTPS application address from your browser, without a path.')
pid_file = Path('data/server.pid')
if pid_file.exists():
    pid = int(pid_file.read_text())
    proc = Path(f'/proc/{pid}/cmdline')
    if proc.exists():
        if b'backend.main:app' not in proc.read_bytes():
            raise SystemExit('Recorded process is not the demo server; left untouched.')
        os.kill(pid, signal.SIGTERM)
        for _ in range(100):
            stat = Path(f'/proc/{pid}/stat')
            if not stat.exists() or stat.read_text().split()[2] == 'Z':
                break
            time.sleep(.1)
        else:
            raise SystemExit('Server did not stop; no other process was started.')
Path('data').mkdir(exist_ok=True)
Path('data/public-origin.txt').write_text(origin+'\n')
PY
bash scripts/start-demo.sh
