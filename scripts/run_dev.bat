@echo off
cd /d E:\GrokFarmBox
netstat -ano | findstr ":8848.*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo GrokFarmBox already running, opening UI...
start "" http://127.0.0.1:8848
  exit /b
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
python main.py
pause
