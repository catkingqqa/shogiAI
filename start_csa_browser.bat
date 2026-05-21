@echo off
setlocal

REM 功能：啟動腳本總覽：切到專案目錄、準備 Python、詢問 MySQL 密碼、開瀏覽器並啟動 API server。

REM 功能：切換到專案根目錄，確保 src 與 web 路徑都能被正確找到。
cd /d "%~dp0"

REM 功能：優先使用指定的本機 Python，若不存在則改用 PATH 中的 python。
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

REM 功能：如果環境變數尚未提供 MySQL 密碼，就在啟動前詢問使用者。
if "%MYSQL_PASSWORD%"=="" (
  set /p MYSQL_PASSWORD=MySQL password:
)

REM 功能：伺服器啟動後延遲一秒自動開啟瀏覽器。
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 1; Start-Process 'http://127.0.0.1:8000'"

REM 功能：啟動 Python API 伺服器，並指定 MySQL 作為棋譜資料來源。
"%PYTHON_EXE%" src\csa_browser_api.py --host 127.0.0.1 --port 8000 --source mysql --db-host 140.135.65.53 --db-port 3306 --db-user 11211213 --db-name DB11211213 --policy-model out\policy_model.pt --value-weight 0 --policy-order-ply 2

echo.
echo Server stopped.
pause
