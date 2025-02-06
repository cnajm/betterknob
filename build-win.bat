@echo off
set NAME=knobVolumeMixer
set ICON=icon.ico
set HOTKEY_ICON=hotkey_icon.ico
set MAIN=src/keyb.py
set HOTKEY_MAIN=src/hotkey_finder.py
set BUILD_MODE=--onefile


if "%1" == "--help" (
    echo run "%~nx0" for normal Build
    echo run "%~nx0 --hotkeytool" to build the hotkey finder tool
    goto end
)
if "%1" == "--hotkeytool" (
    echo Building hotkey finder executable...
    goto run_hotkeytool
)
if not "%1" == "" (
    echo Invalid argument run "%~nx0 --help" for help
    goto end
)
:run
echo Building executable...
set COMMAND=PyInstaller --name "%NAME%" --icon "%ICON%" --console %BUILD_MODE% "%MAIN%" -y --upx-dir=.
goto build

:run_hotkeytool
echo Building hotkey finder executable...
set COMMAND=PyInstaller --name "hotkeyfinder" --icon "%HOTKEY_ICON%" --console %BUILD_MODE% "%HOTKEY_MAIN%" -y --upx-dir=.
goto build

:build
call .venv\Scripts\activate.bat
%COMMAND%
deactivate
:end
