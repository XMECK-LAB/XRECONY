@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 xrecony_launcher.py
) else (
  python xrecony_launcher.py
)
if errorlevel 1 (
  echo.
  echo XRECONY V4.5 could not start. Install Python 3.11 or newer and enable Add Python to PATH.
  pause
)
