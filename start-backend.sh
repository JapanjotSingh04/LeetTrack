#!/usr/bin/env bash
# Sets up (first run only) and starts the FastAPI backend on http://localhost:8000
set -e
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo "No .env found — copying .env.example. Edit backend/.env with your MySQL password before continuing."
  cp .env.example .env
fi

echo "Starting FastAPI on http://localhost:8000 ..."
uvicorn main:app --reload
