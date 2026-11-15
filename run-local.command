#!/bin/bash
# Launch SkyBlink on this Mac: backend + built frontend on one local port.
# Double-click in Finder, or run:  bash run-local.command
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

env_ok() { .venv-local/bin/python -m pip --version >/dev/null 2>&1; }

# Build the environment with one interpreter. Some Python installs ship a
# broken ensurepip, so fall back to a pip-less venv plus PyPA's get-pip.
make_env() {
  rm -rf .venv-local
  "$1" -m venv .venv-local >/dev/null 2>&1 && env_ok && return 0
  rm -rf .venv-local
  "$1" -m venv --without-pip .venv-local >/dev/null 2>&1 || return 1
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o .venv-local/get-pip.py \
    && .venv-local/bin/python .venv-local/get-pip.py --quiet >/dev/null 2>&1 \
    && env_ok
}

if ! env_ok; then
  for candidate in python3.12 python3.11 python3.13 python3; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || continue
    echo "[skyblink] creating Python environment with $candidate ..."
    if make_env "$candidate"; then break; fi
    echo "[skyblink] $candidate could not build an environment; trying the next option."
  done
fi
if ! env_ok && command -v uv >/dev/null 2>&1; then
  echo "[skyblink] creating Python 3.12 environment with uv ..."
  rm -rf .venv-local
  uv venv --seed --python 3.12 .venv-local
fi
if ! env_ok; then
  echo
  echo "SkyBlink needs a working Python 3.11 or newer, and none could be set up."
  echo "Install one (for example: brew install python@3.12) and run this again."
  read -r -p "Press Return to close."
  exit 1
fi

echo "[skyblink] installing backend packages (first run takes a few minutes) ..."
.venv-local/bin/python -m pip install --quiet --upgrade pip
.venv-local/bin/python -m pip install --quiet -r backend/requirements.txt || {
  echo "Package install failed; see the messages above."
  read -r -p "Press Return to close."
  exit 1
}

PORT=""
for candidate in 8000 8010 8020 8030; do
  if ! lsof -nP -iTCP:"$candidate" -sTCP:LISTEN >/dev/null 2>&1; then PORT="$candidate"; break; fi
done
PORT="${PORT:-8040}"
URL="http://localhost:$PORT/#intro"

(
  for _ in $(seq 1 90); do
    if curl -fsS "http://127.0.0.1:$PORT/api/v1/health" >/dev/null 2>&1; then
      open "$URL"
      exit 0
    fi
    sleep 1
  done
) &

echo
echo "[skyblink] starting on $URL  (Ctrl+C here to stop)"
echo
HOST=127.0.0.1 PORT="$PORT" exec .venv-local/bin/python scripts/serve.py
