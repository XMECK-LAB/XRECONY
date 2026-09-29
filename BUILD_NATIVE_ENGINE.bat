@echo off
setlocal
cd /d "%~dp0"
where cargo >nul 2>nul
if errorlevel 1 (
  echo Rust Cargo was not found.
  echo Install stable Rust from https://rustup.rs and run this file again.
  pause
  exit /b 1
)
cargo build --manifest-path native\xrecony-native\Cargo.toml --release
if errorlevel 1 (
  echo Native helper build failed.
  pause
  exit /b 1
)
if not exist native\bin mkdir native\bin
copy /y native\xrecony-native\target\release\xrecony-native.exe native\bin\xrecony-native.exe >nul
echo Native helper built at native\bin\xrecony-native.exe
echo Integration and performance claims still require RUN_TESTS.bat and Windows benchmark validation.
pause
