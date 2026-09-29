@echo off
setlocal
cd /d "%~dp0"
echo XRECONY Surface Studio 1.2 isolated Windows EXE builder
echo No pywebview, pythonnet, NuGet, or .NET bridge is used.
set "PY="
py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3.13 -c "import sys" >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3.14 -c "import sys" >nul 2>nul && set "PY=py -3.14"
if not defined PY goto :runtime
if exist ".build-venv" rmdir /s /q ".build-venv"
%PY% -m venv .build-venv
if errorlevel 1 goto :fail
set "BUILDPY=%CD%\.build-venv\Scripts\python.exe"
"%BUILDPY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%BUILDPY%" -m pip install "pyinstaller>=6.10,<7"
if errorlevel 1 goto :fail
"%BUILDPY%" -m PyInstaller --noconfirm --clean --windowed --name XRECONY_SURFACE_STUDIO_1_2 --add-data "xrecony\web;xrecony\web" --collect-all xrecony xrecony_launcher.py
if errorlevel 1 goto :fail
if not exist "dist\XRECONY_SURFACE_STUDIO_1_2\XRECONY_SURFACE_STUDIO_1_2.exe" goto :fail
echo.
echo BUILD VERIFIED
echo Open: dist\XRECONY_SURFACE_STUDIO_1_2\XRECONY_SURFACE_STUDIO_1_2.exe
pause
exit /b 0
:runtime
echo.
echo A supported build runtime was not found.
echo Run INSTALL_WINDOWS_BUILD_RUNTIME.bat once, then run this builder again.
echo Your existing Python 3.15 is left unchanged.
pause
exit /b 2
:fail
echo Build failed. Review the output above.
pause
exit /b 1
