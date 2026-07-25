@echo off
setlocal

cd /d "%~dp0.."
if errorlevel 1 (
  set "FAILED_STEP=Open the project directory"
  goto :failed
)

echo ============================================
echo   GrokFarmBox EXE Builder
echo ============================================
echo Project: %CD%
echo.

if not exist "requirements.txt" (
  set "FAILED_STEP=Find requirements.txt"
  goto :failed
)
if not exist "main.py" (
  set "FAILED_STEP=Find main.py"
  goto :failed
)

set "VENV_PYTHON=.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" goto :create_venv
echo [1/4] Using existing virtual environment...
goto :install_dependencies

:create_venv
echo [1/4] Creating virtual environment...
where py >nul 2>&1
if errorlevel 1 goto :create_with_python
py -3 -m venv .venv
if errorlevel 1 (
  set "FAILED_STEP=Create the virtual environment with py"
  goto :failed
)
goto :verify_venv

:create_with_python
where python >nul 2>&1
if errorlevel 1 (
  set "FAILED_STEP=Find Python 3.10 or newer"
  goto :failed
)
python -m venv .venv
if errorlevel 1 (
  set "FAILED_STEP=Create the virtual environment with python"
  goto :failed
)

:verify_venv
if not exist "%VENV_PYTHON%" (
  set "FAILED_STEP=Verify the virtual environment"
  goto :failed
)

:install_dependencies
echo [2/4] Installing dependencies...
"%VENV_PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  set "FAILED_STEP=Install dependencies"
  goto :failed
)

echo [3/4] Removing old build output...
if exist "build" rmdir /s /q "build"
if exist "build" (
  set "FAILED_STEP=Remove the build directory"
  goto :failed
)
if exist "dist" rmdir /s /q "dist"
if exist "dist" (
  set "FAILED_STEP=Remove the dist directory"
  goto :failed
)

echo [4/4] Building GrokFarmBox.exe...
"%VENV_PYTHON%" -m PyInstaller --noconfirm --clean ^
  --name GrokFarmBox ^
  --windowed ^
  --onedir ^
  --add-data "app\web;app\web" ^
  --add-data "docs;docs" ^
  --collect-all flask ^
  --hidden-import curl_cffi ^
  main.py
if errorlevel 1 (
  set "FAILED_STEP=Build the executable"
  goto :failed
)

if not exist "dist\GrokFarmBox\GrokFarmBox.exe" (
  set "FAILED_STEP=Verify the executable"
  goto :failed
)

echo.
echo Build completed successfully.
echo Output: %CD%\dist\GrokFarmBox\GrokFarmBox.exe
echo Runtime data will be created beside the executable.
echo.
pause
exit /b 0

:failed
echo.
echo [ERROR] %FAILED_STEP% failed.
echo Review the messages above, then press any key to close.
echo.
pause
exit /b 1
