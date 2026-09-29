@echo off
setlocal
cd /d "%~dp0"
set "XRECONY_DESKTOP_SHELL=browser"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 xrecony_launcher.py
) else (
  python xrecony_launcher.py
)
