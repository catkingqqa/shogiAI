@echo off
setlocal

REM Go to this project folder so src and web can be found.
cd /d "%~dp0"

REM Prefer the Python installed on this computer. Stop early if it cannot be found.
set "PYTHON_EXE="
if exist "C:\Users\20050\AppData\Local\Programs\Python\Python313\python.exe" (
  set "PYTHON_EXE=C:\Users\20050\AppData\Local\Programs\Python\Python313\python.exe"
)
if "%PYTHON_EXE%"=="" if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
)
if "%PYTHON_EXE%"=="" (
  echo Python was not found. Please install Python 3.13 or fix PYTHON_EXE in this bat file.
  pause
  exit /b 1
)

echo Starting CSA browser...
echo AI settings:
echo   policy model: out\policy_model.pt
echo   value weight: 0
echo   policy order ply: 2
echo   opening book: first 30 plies, min count 2
echo   python: %PYTHON_EXE%
echo.
echo If the browser does not open automatically, visit:
echo http://127.0.0.1:8000
echo.
echo Keep this window open while presenting.
echo Press Ctrl+C here when you want to stop the server.
echo.

REM If an old server is still using port 8000, this copy cannot load new code.
set "PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:"127.0.0.1:8000 .*LISTENING"') do set "PORT_PID=%%P"
if not "%PORT_PID%"=="" (
  echo Port 8000 is already used by PID %PORT_PID%.
  echo Close the old server window first, or run:
  echo taskkill /PID %PORT_PID% /F
  echo.
  pause
  exit /b 1
)

REM Ask for the MySQL password only if it is not already set.
if "%MYSQL_PASSWORD%"=="" (
  set /p MYSQL_PASSWORD=MySQL password:
)

REM Model modules can take a few seconds to load. Open the browser after the API is ready.
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$url='http://127.0.0.1:8000/api/model-match/models'; for ($i=0; $i -lt 30; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 $url | Out-Null; break } catch { Start-Sleep -Seconds 1 } }; Start-Process 'http://127.0.0.1:8000'"

REM Start the Python API server and use MySQL as the game source.
"%PYTHON_EXE%" src\csa_browser_api.py --host 127.0.0.1 --port 8000 --source mysql --db-host 140.135.65.53 --db-port 3306 --db-user 11211213 --db-password "%MYSQL_PASSWORD%" --db-name DB11211213 --policy-model out\policy_model.pt --value-weight 0 --policy-order-ply 2 --opening-book-ply 30 --opening-book-min-count 2

echo.
echo Server stopped.
pause
