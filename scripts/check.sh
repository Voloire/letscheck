#!/usr/bin/env bash
# Local replica of the GitHub CI "test" job plus the container image, meant for the
# Linux dev box (WSL codex-dev). Offline, no credentials, no cloud calls.
#
#   bash scripts/check.sh              # tests, browser suite, image build, container smoke test
#   bash scripts/check.sh --no-docker  # tests and browser suite only
#
# Prerequisites: the repo venv in .venv with requirements.txt and requirements-dev.txt,
# Chromium for Playwright (python -m playwright install chromium, then install-deps),
# node on PATH, and a working docker engine unless --no-docker is given.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=".venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"
WITH_DOCKER=1
[[ "${1:-}" == "--no-docker" ]] && WITH_DOCKER=0

echo "== compileall and JavaScript syntax"
"$PYTHON" -m compileall -q astrochecker tests run.py
node --check astrochecker/static/app.js

echo "== pytest (includes the Playwright suite)"
"$PYTHON" -m pytest -q

if command -v terraform >/dev/null; then
  echo "== terraform fmt, validate and tests (infra/gcp)"
  terraform fmt -check -recursive infra
  terraform -chdir=infra/gcp init -backend=false -input=false >/dev/null
  terraform -chdir=infra/gcp validate >/dev/null
  terraform -chdir=infra/gcp test
else
  echo "== terraform not found: infra/gcp checks skipped"
fi

if [[ "$WITH_DOCKER" == "0" ]]; then
  echo "== docker skipped (--no-docker)"
  exit 0
fi

command -v docker >/dev/null || { echo "docker not found: install Docker Engine or use --no-docker" >&2; exit 1; }

IMAGE="astrochecker:check"
NAME="astrochecker-check-$$"
PORT=18080
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "== docker build $IMAGE"
docker build -q -t "$IMAGE" . >/dev/null

echo "== container smoke test on 127.0.0.1:$PORT"
docker run -d --rm --name "$NAME" -p "127.0.0.1:$PORT:8080" \
  -e ASTROCHECKER_PUBLIC_HOST=localhost "$IMAGE" >/dev/null
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null -H "Host: localhost" "http://127.0.0.1:$PORT/api/status" 2>/dev/null; then
    break
  fi
  sleep 1
done
status_ok=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: localhost" "http://127.0.0.1:$PORT/api/status")
catalog_ready=$(curl -s -H "Host: localhost" "http://127.0.0.1:$PORT/api/status" | "$PYTHON" -c 'import json,sys; print(str(json.load(sys.stdin).get("ready")).lower())')
status_wrong_host=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: 127.0.0.1" "http://127.0.0.1:$PORT/api/status")
status_bad_origin=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: localhost" -H "Origin: http://localhost" \
  -H "Content-Type: application/json" -d '{}' "http://127.0.0.1:$PORT/api/site")
echo "   public host -> $status_ok (catalog ready: $catalog_ready), wrong host -> $status_wrong_host, http origin -> $status_bad_origin"
if [[ "$status_ok" != "200" || "$catalog_ready" != "true" || "$status_wrong_host" != "403" || "$status_bad_origin" != "403" ]]; then
  echo "container smoke test failed" >&2
  docker logs "$NAME" >&2 || true
  exit 1
fi
echo "== all checks passed"
