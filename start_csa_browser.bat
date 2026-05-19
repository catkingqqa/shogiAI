@echo off
setlocal

REM Go to this project folder so src and web can be found.
cd /d "%~dp0"

REM Prefer the Python installed on this computer. Fallback to python if PATH is set.
set "PYTHON_EXE=C:\Users\20050\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo Starting CSA browser...
echo AI settings:
echo   policy model: out\policy_model.pt
echo   value weight: 0
echo   policy order ply: 2
echo.
echo If the browser does not open automatically, visit:
echo http://127.0.0.1:8000
echo.
echo Keep this window open while presenting.
echo Press Ctrl+C here when you want to stop the server.
echo.

REM Ask for the MySQL password only if it is not already set.
if "%MYSQL_PASSWORD%"=="" (
  set /p MYSQL_PASSWORD=MySQL password:
)

REM Open the browser shortly after the server starts.
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 1; Start-Process 'http://127.0.0.1:8000'"

REM Start the Python API server and use MySQL as the game source.
"%PYTHON_EXE%" src\csa_browser_api.py --host 127.0.0.1 --port 8000 --source mysql --db-host 140.135.65.53 --db-port 3306 --db-user 11211213 --db-name DB11211213 --policy-model out\policy_model.pt --value-weight 0 --policy-order-ply 2

echo.
echo Server stopped.
pause
