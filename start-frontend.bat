@echo off
REM Installs (first run only) and starts the React dev server on http://localhost:5173
cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo Installing frontend dependencies...
    npm install
)

echo Starting Vite dev server on http://localhost:5173 ...
npm run dev
