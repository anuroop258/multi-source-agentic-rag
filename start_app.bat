@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)
if not exist .env (
  echo .env not found. Copy .env.example to .env and add GROQ_API_KEY.
  pause
  exit /b 1
)
if not exist frontend\dist\index.html (
  echo Frontend build not found. Run: cd frontend ^&^& npm install ^&^& npm run build
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python run.py
