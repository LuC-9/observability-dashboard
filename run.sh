#!/usr/bin/env bash
# Local "production-style" run: build SPA, then start FastAPI serving /api + static.
# Used both as a Cloud Run-compatible entrypoint and for local docker-less smoke tests.
set -e
PORT=${PORT:-7860}

echo "==> Building frontend..."
cd "$(dirname "$0")/frontend"
if command -v yarn >/dev/null 2>&1; then
  yarn install --frozen-lockfile --silent
  yarn build
else
  npm install --silent
  npm run build
fi

echo "==> Starting backend on port ${PORT}..."
cd ../backend
exec uvicorn server:app --host 0.0.0.0 --port "${PORT}"
