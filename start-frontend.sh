#!/usr/bin/env bash
# Installs (first run only) and starts the React dev server on http://localhost:5173
set -e
cd "$(dirname "$0")/frontend"

if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

echo "Starting Vite dev server on http://localhost:5173 ..."
npm run dev
