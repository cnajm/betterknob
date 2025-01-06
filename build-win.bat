@echo off
set NAME=knobVolumeMixer
set ICON=icon.ico
set MAIN=keyb.py
set BUILD_MODE=--onefile


if "%1" == "--help" (
    echo run "%~nx0" for normal Build
    echo run "%~nx0 --portable" for Build packaged into one file
    goto end
)
if "%1" == "--portable" (
    echo Building portable executable...
    set BUILD_MODE=--onefile
    goto run
)
if not "%1" == "" (
    echo Invalid argument run "%~nx0 --help" for help
    goto end
)
:run
echo Building executable...
set COMMAND=PyInstaller --name "%NAME%" --icon "%ICON%" --console %BUILD_MODE% "%MAIN%" -y --upx-dir=.
call .venv\Scripts\activate.bat
%COMMAND%
deactivate
:end
