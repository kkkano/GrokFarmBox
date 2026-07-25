@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ============================================
echo   GrokFarmBox 打包 (PyInstaller)
echo ============================================

if not exist .venv (
  echo [1/4] 创建 venv...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
echo [2/4] 安装依赖...
python -m pip install -U pip >nul
pip install -r requirements.txt
pip install pyinstaller

echo [3/4] 清理旧产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/4] 开始打包...
pyinstaller --noconfirm --clean ^
  --name GrokFarmBox ^
  --windowed ^
  --onedir ^
  --add-data "docs;docs" ^
  --hidden-import customtkinter ^
  --hidden-import curl_cffi ^
  --collect-all customtkinter ^
  main.py

if errorlevel 1 (
  echo.
  echo 打包失败。
  exit /b 1
)

echo.
echo 完成: dist\GrokFarmBox\GrokFarmBox.exe
echo 首次运行会在 exe 同目录生成 data\
echo.
pause
