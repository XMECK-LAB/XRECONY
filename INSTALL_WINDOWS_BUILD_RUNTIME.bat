@echo off
setlocal
echo XRECONY build runtime installer
echo This installs Python 3.12 side-by-side. It does not remove Python 3.15.
where winget >nul 2>nul
if errorlevel 1 goto :nowinget
winget install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :fail
echo.
echo Python 3.12 installation completed.
echo Close this window, then run BUILD_WINDOWS_EXE.bat.
pause
exit /b 0
:nowinget
echo Windows Package Manager is unavailable.
echo Install Python 3.12 x64 from python.org, then run BUILD_WINDOWS_EXE.bat.
pause
exit /b 2
:fail
echo Python 3.12 installation failed. Review the message above.
pause
exit /b 1
