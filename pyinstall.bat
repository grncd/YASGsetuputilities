@echo off
setlocal enabledelayedexpansion

echo [0%%] Starting Python setup process...
echo [5%%] Checking for Python installation...

:: Check if Python is valid (not just a Microsoft Store alias)
for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PYTHON_EXE=%%i"
)

if defined PYTHON_EXE (
    for /f "delims=" %%v in ('%PYTHON_EXE% --version 2^>nul') do (
        echo [10%%] Python is already installed.
        echo %%v
        goto :create_venv
    )
)

echo [15%%] Python not found or is a Microsoft Store alias. Downloading Python 3.13.5...

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

:: Install Python silently
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1

echo [50%%] Waiting for installation to complete...
:: Wait until python.exe exists in the expected location
set "PYTHON_BASE=%LocalAppData%\Programs\Python\Python313"
set "PYTHON_EXE=%PYTHON_BASE%\python.exe"
set "MAX_WAIT=30"
set /a COUNT=0

:wait_loop
if exist "%PYTHON_EXE%" (
    goto :verify_python
)
timeout /t 1 >nul
set /a COUNT+=1
if !COUNT! geq !MAX_WAIT! (
    echo [ERROR] Python installer timeout after !MAX_WAIT! seconds.
    exit /b 1
)
goto :wait_loop

:verify_python
echo [70%%] Python installed at: %PYTHON_EXE%
echo [75%%] Cleaning up installer...
del "%PYTHON_INSTALLER%"

echo [80%%] Adding Python to current PATH...
set "PATH=%PYTHON_BASE%;%PYTHON_BASE%\Scripts;%PATH%"

echo [85%%] Verifying Python...
"%PYTHON_EXE%" --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not functioning correctly.
    exit /b 1
)

echo [90%%] Python installation completed successfully.
"%PYTHON_EXE%" --version

:create_venv
echo.
echo [91%%] Creating virtual environment...

:: Get the parent directory of the batch file
set "BATCH_DIR=%~dp0"
set "PARENT_DIR=%BATCH_DIR%..\"

:: Move to parent directory and create venv
cd /d "%PARENT_DIR%"
"%PYTHON_EXE%" -m venv venv

if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    exit /b 1
)

echo [95%%] Virtual environment created successfully at: %PARENT_DIR%venv

echo [96%%] Activating virtual environment...
call "%PARENT_DIR%venv\Scripts\activate.bat"

echo [97%%] Installing required packages...
pip install selenium
pip install pywin32
pip install pyperclip

echo [100%%] Setup completed successfully!
echo Virtual environment is now active and ready to use.
