#!/usr/bin/env bash
# Codespaces lifecycle entry point. The forwarded port stays private by default.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
if [[ ! -x .venv/bin/python || ! -f frontend/dist/index.html ]]; then
  echo 'Run scripts/setup-demo.sh before starting the demo.' >&2
  exit 1
fi
export DEMO_MODE=true
export DATABASE_PATH="$project_root/data/permitsnj.sqlite3"
export ALLOWED_HOSTS=localhost,127.0.0.1
export APP_ORIGIN=''
export SESSION_SECURE=false
if [[ -n "${CODESPACE_NAME:-}" ]]; then
  forwarding_domain="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  demo_hostname="${CODESPACE_NAME}-8000.${forwarding_domain}"
  export ALLOWED_HOSTS="localhost,127.0.0.1,${demo_hostname}"
  export APP_ORIGIN="https://${demo_hostname}"
  export SESSION_SECURE=true
fi
# An explicit browser address survives restarts and proxy/domain variations.
if [[ -f data/public-origin.txt ]]; then
  APP_ORIGIN="$(cat data/public-origin.txt)"
  export APP_ORIGIN
  demo_hostname="$(.venv/bin/python -c 'import os; from urllib.parse import urlsplit; print(urlsplit(os.environ["APP_ORIGIN"]).netloc)')"
  export ALLOWED_HOSTS="localhost,127.0.0.1,${demo_hostname}"
  export SESSION_SECURE=true
fi
# Reuse only a verified PermitsNJ demo; fail if another service occupies port 8000.
port_state="$(.venv/bin/python - <<'PY'
import json
import socket
from urllib.request import Request, urlopen
try:
    import os
    from urllib.parse import urlsplit
    expected_host = urlsplit(os.environ.get('APP_ORIGIN', '')).netloc or '127.0.0.1:8000'
    with urlopen(Request('http://127.0.0.1:8000/api/health', headers={'Host': expected_host}), timeout=2) as response:
        health = json.load(response)
    with urlopen('http://127.0.0.1:8000/', timeout=2) as response:
        page = response.read().decode()
    print('ready' if health == {'status': 'ok', 'demo': True} and 'PermitsNJ' in page else 'occupied')
except (OSError, ValueError):
    with socket.socket() as sock:
        sock.settimeout(1)
        print('occupied' if sock.connect_ex(('127.0.0.1', 8000)) == 0 else 'free')
PY
)"
if [[ "$port_state" == ready ]]; then
  echo 'PermitsNJ is already running on port 8000.'
  exit 0
fi
if [[ "$port_state" != free ]]; then
  echo 'Port 8000 is occupied by another service. It was left untouched.' >&2
  exit 1
fi
mkdir -p data
nohup .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > data/server.log 2>&1 < /dev/null &
demo_pid=$!
printf '%s\n' "$demo_pid" > data/server.pid
if ! .venv/bin/python - <<'PY'
import json
import time
from urllib.request import Request, urlopen
for attempt in range(100):
    try:
        with urlopen('http://127.0.0.1:8000/api/health', timeout=1) as response:
            if json.load(response) == {'status': 'ok', 'demo': True}:
                print('PermitsNJ is ready. Open port 8000 in the Codespaces Ports panel if it did not open automatically.')
                break
    except (OSError, ValueError):
        pass
    time.sleep(.1)
else:
    raise SystemExit('PermitsNJ did not become ready. Inspect data/server.log.')
PY
then
  exit 1
fi
