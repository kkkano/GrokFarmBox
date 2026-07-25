@echo off
cd /d E:\GrokFarmBox

REM 单实例锁：8848 已在跑就直接打开 UI，不再重复启动
netstat -ano | findstr ":8848.*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo GrokFarmBox already running. Opening UI...
  start "" http://127.0.0.1:8848
  exit /b
)

if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
python main.py
pause
