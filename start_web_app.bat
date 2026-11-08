@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Local virtual environment was not found.
    echo Expected: .venv\Scripts\python.exe
    echo.
    echo Create it first:
    echo python -m venv .venv
    echo .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting docsync web app...
echo URL: http://127.0.0.1:8010/
echo.

".venv\Scripts\python.exe" -m uvicorn web_app.app:app --host 127.0.0.1 --port 8010 --reload

pause
