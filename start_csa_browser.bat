@echo off
setlocal
cd /d "%~dp0"

echo Starting CSA browser...
echo.
echo If the browser does not open automatically, visit:
echo http://127.0.0.1:8000
echo.
echo Keep this window open while presenting.
echo Press Ctrl+C here when you want to stop the server.
echo.

start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 1; Start-Process 'http://127.0.0.1:8000'"

python src\csa_browser_api.py --host 127.0.0.1 --port 8000

echo.
echo Server stopped.
pause
