@echo off
REM Sets up (first run only) and starts the FastAPI backend on http://localhost:8000
cd /d "%~dp0backend"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

if not exist ".env" (
    echo No .env found - copying .env.example. Edit backend\.env with your MySQL password before continuing.
    copy .env.example .env
)

echo Starting FastAPI on http://localhost:8000 ...
uvicorn main:app --reload
