#!/usr/bin/env bash
set -e
PORT=${PORT:-7860}

echo "==> Building frontend..."
cd frontend
npm install --silent
npm run build   # writes to ../backend/static

echo "==> Starting backend on port $PORT..."
cd ../backend
uvicorn main:app --host 0.0.0.0 --port "$PORT"
