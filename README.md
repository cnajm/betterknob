
# BetterKnob Volume Mixer

[![latest release](https://img.shields.io/github/v/release/cnajm/betterknob)](https://github.com/cnajm/betterknob/releases/latest)

A simple program that lets you use media buttons or a physical knob to control audio volume on a per-application basis rather than system-wide.

Works very well with keyboards that have a knob/rotary dial like the Keychron Q and V series.

Example uses:
- Raise the sound of a voice call without having to change windows
- Adjust your music's volume relative to a another program's volume without tabbing out
- Mute a single application without needing to open your computer's volume mixer
- Finely adjust your volume with dynamic step sizes that get more precise the closer you get to 0%

## Features

- Lightweight overlay shows you the current application's volume (after changing it, then goes away)
- Hotkey: Cycle between all currently playing audio sources
- Hotkey: Switch to and control the currently focused application's audio
- Hotkey: Switch to and control the system/global audio level
- Set a default application to revert audio controls to when idle
- Smart volume controls allows the same keypress/knob turn to perform fine-tuned adjustments when approaching lower values (logarithmic scaling, configurable)
- Rebindable hotkeys
- Single, portable binary. No installer
- Anti-cheat safe

## Usage

Download the [latest release](https://github.com/cnajm/betterknob/releases/latest) and extract it. Then run the BetterKnob binary.

If you would like to change the hotkeys in the config file, run the included `HotkeyFinder.exe` tool to figure out what values to use in your config

## How it works

BetterKnob intercepts volume up/down keycodes (which by default adjust the global volume) and adds more functionality to them.

If you do not have a keyboard with a knob, you can use media buttons (fn+f11/f12, conventionally) or bind volume up/down to a modifier key like alt + scrollwheel in your mouse's software or in AutoHotKey

## Considerations

- When used in an application with elevated privileges (e.g Task Manager) the volume mixer won't be able to handle any keypresses. Run the mixer with admin rights if you need it to work in such cases
- Check config.ini for configurable settings
- Reserves around 25 MB of RAM
- Does not write to disk other than to your %TEMP% folder, and only once on initial launch ([PyInstaller does](https://pyinstaller.org/en/stable/operating-mode.html#how-the-one-file-program-works), not betterknob) 
- No network calls or telemetry
- Windows 7+ only, for now

## Build

### Development

```python
python -m venv .venv
source .venv/Scripts/activate
pip install -r src/requirements.txt
```

### Binary Executable

If you want to compress the binary, you also need [UPX](https://upx.github.io/) in your path
```
./build-win.bat
```
then check the `dist` folder