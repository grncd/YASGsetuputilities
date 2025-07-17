@echo off
setlocal enabledelayedexpansion

echo [0%%] Starting Python setup process...
echo [5%%] Checking for Python installation...

:: Check if Python is already installed
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo [10%%] Python is already installed.
    python --version
    goto :create_venv
)

echo [15%%] Python not found. Downloading Python 3.13.5...

:: Set the download URL and filename
set "PYTHON_URL=https://www.python.org/ftp/python/3.13.5/python-3.13.5-amd64.exe"
set "PYTHON_INSTALLER=python-3.13.5-amd64.exe"

:: Download Python installer using PowerShell
echo [20%%] Downloading Python installer...
powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'"

if not exist "%PYTHON_INSTALLER%" (
    echo [ERROR] Failed to download Python installer.
    exit /b 1
)

echo [40%%] Download completed successfully.
echo [45%%] Installing Python silently...

:: Install Python silently with options
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1

echo [50%%] Installation in progress...
:: Wait for installation to complete
timeout /t 10 /nobreak >nul

echo [70%%] Installation completed, cleaning up...
:: Clean up installer
del "%PYTHON_INSTALLER%"

echo [75%%] Refreshing environment variables...
:: Refresh environment variables
call refreshenv >nul 2>&1

echo [80%%] Verifying Python installation...
:: Check if installation was successful
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python installation failed or Python is not in PATH.
    echo Please restart your command prompt and try again.
    exit /b 1
)

echo [85%%] Python installation completed successfully.
python --version

:create_venv
echo.
echo [90%%] Creating virtual environment...

:: Get the parent directory of the batch file
set "BATCH_DIR=%~dp0"
set "PARENT_DIR=%BATCH_DIR%..\"

:: Create virtual environment in parent directory
cd /d "%PARENT_DIR%"
python -m venv venv

if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    exit /b 1
)

echo [95%%] Virtual environment created successfully at: %PARENT_DIR%venv

echo [96%%] Activating virtual environment...
:: Activate the virtual environment
call "%PARENT_DIR%venv\Scripts\activate.bat"

echo [97%%] Installing required packages...
echo Installing selenium...
pip install selenium

echo Installing pywin32...
pip install pywin32

echo Installing pyperclip...
pip install pyperclip

echo [99%%] Package installation completed.

echo.
echo [100%%] Setup completed!
echo Virtual environment is now active and packages are installed.