@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher was not found. Install Python 3.11 and enable the py launcher.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Creating Python 3.11 virtual environment...
  py -3.11 -m venv .venv
  if errorlevel 1 goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements.txt
if errorlevel 1 goto :error
if not exist .env copy .env.example .env
echo.
echo Setup complete. Edit .env and add GROQ_API_KEY.
echo Then double-click start_app.bat.
pause
exit /b 0
:error
echo Setup failed. Review the error above and check Python 3.11 and internet connectivity.
pause
exit /b 1
