
# BetterKnob Volume Mixer

[![latest release](https://img.shields.io/github/v/release/cnajm/betterknob)](https://github.com/cnajm/betterknob/releases/latest)

BetterKnob is a lightweight program that enables your keyboard's knob to control audio levels on a per-application basis, rather than only system-wide.

Works very well with keyboards that have a knob/rotary encoder like the Keychron Q and V series. Works with media buttons.

Example uses:
- Adjust your music's volume relative to another program's volume, without tabbing out
- Raise the volume of a voice call without needing to change windows
- Mute a single application without needing to fiddle with your OS's volume mixer
- Finely adjust your volume levels with dynamic step sizes that get more precise the closer you get to 0%

## Features

- Lightweight overlay shows you the current application's volume (after changing it, then goes away)
- Hotkey: Cycle between all currently playing audio sources
- Hotkey: Switch to and control the currently focused application's audio
- Hotkey: Switch to and control the system/global audio level
- Set a default application to revert audio controls to when idle
- Smart volume controls allow the same keypress/knob turn to perform fine adjustments when approaching lower values (logarithmic scaling, configurable)
- Rebindable hotkeys
- Single, portable binary. No installer
- Tiny resource footprint
- No network calls or telemetry
- Anti-cheat safe

## Usage

### Precompiled Binary

Download the [latest release](https://github.com/cnajm/betterknob/releases/latest) and extract it. Run `BetterKnob.exe`.

Check `config.ini` for configurable settings

To change the hotkeys in the config file, the included `HotkeyFinder.exe` tool can help you figure out what values to use in your config

### Running from source

```
python -m venv .venv
source .venv/Scripts/activate
pip install -r src/requirements.txt
python src/keyb.py
```

## How it works

BetterKnob hooks into volume up/down key events (which by default adjust the global volume) and adds more functionality to them.

It strives to be simple, invisible, and is smart enough to adjust its normal behavior when an action would do nothing (such as changing the volume of a process with no audio).

If you do not have a keyboard with a knob, you can use media buttons (fn+f11/f12, conventionally) or bind volume up/down to a modifier key like alt + scrollwheel in your mouse's software or with AutoHotKey.

## Limitations

- Windows 7+ only, for now
- When used in an application with elevated privileges (e.g Task Manager), betterknob won't be able to handle any keypresses. Run the mixer with admin rights if you need it to work in these cases
- Does not write to disk other than to your %TEMP% folder, and only once on launch ([PyInstaller does](https://pyinstaller.org/en/stable/operating-mode.html#how-the-one-file-program-works), not betterknob) 

## Build

### Development

```python
python -m venv .venv
source .venv/Scripts/activate
pip install -r src/requirements.txt -r src/requirements-dev.txt
```

### Binary Executable

If you want to compress the binary, you also need [UPX](https://upx.github.io/) in your path
```
./build-win.bat
```
then check the `dist` folder