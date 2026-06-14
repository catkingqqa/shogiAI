@echo off
setlocal

REM Go to this project folder so src and web can be found.
cd /d "%~dp0"

REM Default to the shared MySQL database.
REM Run "start_csa_browser.bat local" to use local CSA files instead.
set "DATA_SOURCE=mysql"
if /I "%~1"=="local" set "DATA_SOURCE=csa"

REM Prefer the Python installed on this computer. Stop early if it cannot be found.
set "PYTHON_EXE="

REM First try Python Launcher, Python 3.13
for /f "delims=" %%P in ('py -3.13 -c "import sys; print(sys.executable)" 2^>nul') do (
  set "PYTHON_EXE=%%P"
)

REM If Python 3.13 is not installed, try any Python 3 version
if "%PYTHON_EXE%"=="" (
  for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
    set "PYTHON_EXE=%%P"
  )
)

REM If py launcher is not available, try common install paths
if "%PYTHON_EXE%"=="" if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python313\python.exe"
)

if "%PYTHON_EXE%"=="" if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
)

if "%PYTHON_EXE%"=="" if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
)

if "%PYTHON_EXE%"=="" (
  echo Python was not found.
  echo Please install Python 3, or fix PYTHON_EXE in this bat file.
  echo.
  echo Try running:
  echo   py -0p
  echo   where python
  pause
  exit /b 1
)
echo Starting CSA browser...
echo   data source: %DATA_SOURCE%
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

REM Check dependencies required by the API and selected data source.
"%PYTHON_EXE%" -c "import cshogi, torch" >nul 2>nul
if errorlevel 1 (
  echo Missing Python dependencies.
  echo Please run:
  echo   "%PYTHON_EXE%" -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

if /I "%DATA_SOURCE%"=="mysql" (
  "%PYTHON_EXE%" -c "import pymysql, cryptography" >nul 2>nul
  if errorlevel 1 (
    echo Missing MySQL Python dependencies.
    echo Please run:
    echo   "%PYTHON_EXE%" -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
  )
)

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

REM Ask for the MySQL password only when MySQL mode is explicitly selected.
if /I "%DATA_SOURCE%"=="mysql" (
  if "%MYSQL_PASSWORD%"=="" (
    set /p MYSQL_PASSWORD=MySQL password:
  )
)

REM Model modules can take a few seconds to load. Open the browser after the API is ready.
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$url='http://127.0.0.1:8000/api/model-match/models'; for ($i=0; $i -lt 30; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 $url | Out-Null; break } catch { Start-Sleep -Seconds 1 } }; Start-Process 'http://127.0.0.1:8000'"

REM Start the Python API server with the selected game source.
if /I "%DATA_SOURCE%"=="mysql" (
  "%PYTHON_EXE%" src\csa_browser_api.py --host 127.0.0.1 --port 8000 --source mysql --db-host 140.135.65.53 --db-port 3306 --db-user 11211213 --db-password "%MYSQL_PASSWORD%" --db-name DB11211213 --policy-model out\policy_model.pt --value-weight 0 --policy-order-ply 2 --opening-book-ply 30 --opening-book-min-count 2
) else (
  "%PYTHON_EXE%" src\csa_browser_api.py --host 127.0.0.1 --port 8000 --source csa --policy-model out\policy_model.pt --value-weight 0 --policy-order-ply 2
)

echo.
echo Server stopped.
pause
