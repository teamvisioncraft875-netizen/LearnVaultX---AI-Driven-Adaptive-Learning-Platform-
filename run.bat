@echo off
echo ================================
echo   LearnVaultX - Starting Server
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Check if requirements are installed
echo Checking dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting LearnVaultX application...
echo.
echo Access the app at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.

python wsgi.py

pause
