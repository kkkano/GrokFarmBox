@echo off
cd /d E:\GrokFarmBox
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
python main.py
pause
