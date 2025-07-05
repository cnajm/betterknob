
# BetterKnob Volume Mixer

[![latest release](https://img.shields.io/github/v/release/cnajm/betterknob)](https://github.com/cnajm/betterknob/releases/latest)

BetterKnob is a lightweight volume mixer used with rotary encoders or media keys.

I created it because I needed a tool to control multiple applications' audio levels without moving my hands off my keyboard or interrupting what I was doing.

To use it, launch it and change your volume. It is smart enough to figure out which application you want to target and has hotkeys to target specific applications, among others.

Works well with keyboards that have a knob/rotary encoder like the Keychron Q and V series. Works with media buttons.

Example uses:
- Adjust your music's volume without changing system volume/other applications' volume
- Raise the volume of a voice call without needing to change windows
- Mute a single application without needing to fiddle with your OS's volume mixer
- Finely adjust your volume levels with dynamic step sizes that get more precise the closer you get to 0%

## Features

- Lightweight overlay shows you the current application's volume (after changing it, then goes away)
- Hotkey: Cycle between all currently playing audio sources
- Hotkey: Switch to and control the currently focused application's volume
- Hotkey: Switch to and control the system/global volume
- Set a default application to revert audio controls to after an idle delay
- Smart volume controls allow the same keypress/knob turn to perform fine adjustments when approaching lower values (logarithmic scaling, configurable)
- Rebindable hotkeys
- Single, portable binary. No installer
- Tiny resource footprint
- No network calls or telemetry
- Anti-cheat safe

<br />

## Usage

### Precompiled Binary

Download the [latest release](https://github.com/cnajm/betterknob/releases/latest) and extract it. Run `BetterKnob.exe`.

Check `config.ini` for configurable settings

To change the hotkeys in the config file, the included `HotkeyFinder.exe` tool can help you figure out what values to use in your config


> [!NOTE]  
> When used in an application with elevated privileges (e.g Task Manager), betterknob won't be able to listen to any keypresses. Run the mixer with admin rights if you need it to work in these cases

### Running from source

```
python -m venv .venv
source .venv/Scripts/activate
pip install -r src/requirements.txt
python src/keyb.py
```

### Config

> [!INFO]  
> Hotkeys can be set using their name or scan codes. Use the hotkey finder utility to find both

| Setting                         | Required to be set | What it does                                                                                              | Default Value |
|---------------------------------|----------|---------------------------------------------------------------------------------------------------------------------|---------------|
| `default_process`               | ✅        | Reverts audio controls to this process after some idle time. Set it to your most active audio source               | chrome.exe    |
| `key_quit`                      | ✅        | Hotkey to exit Betterknob                                                                                          | f13           |
| `key_cycle_audio_source`        | ✅        | Hotkey to cycle volume controls to the next (active) audio source                                                  | f15           |
| `key_currently_focused`         | ❌        | Hotkey to cycle volume controls to the currently focused application (won't do anything if it isn't playing audio) | f16           |
| `key_swap_to_system`            | ❌        | Hotkey to cycle volume controls to the global system audio source                                                  | f17           |
| `key_volume_up`                 | ❌        | Hotkey to raise the volume (default = vol up)                                                                      | scan:-175     |
| `key_volume_down`               | ❌        | Hotkey to lower the volume (default = vol down)                                                                    | scan:-174     |
| `volume_step_min`               | ❌        | Minimum volume step (% change) per volume down event                                                               | 0.02          |
| `volume_step_max`               | ❌        | Minimum volume step (% change) per volume up event                                                                 | 0.10          |
| `change_system_vol_if_no_audio` | ❌        | Betterknob only activates if there's audio playing. If there isn't, should it adjust the system volume?            | true          |
| `show_overlay`                  | ❌        | Whether to show the visual overlay when you use Betterknob                                                         | true          |
| `debug`                         | ❌        | Whether to enable extra console logging. If true, also creates a log file in the current directory.                | false         |

## How it works

BetterKnob hooks into volume up/down key events (which by default adjust the system volume) and adds more functionality to them.

It strives to be lightweight, invisible, and reduce cognitive load. It's smart enough to adjust its normal behavior when an action would do nothing. For example, if you change the volume of a focused process with no audio, Betterknob will first swap to an active audio source.

If you do not have a keyboard with a knob, you can use media buttons (fn+f11/f12, conventionally) or bind volume up/down to a modifier key like alt + scrollwheel in your mouse's software or with AutoHotKey.

## Limitations

- Windows 7+ only
- Some applications (mainly competitive games) use aggressive anticheat software that blocks Betterknob from working when they are focused. This is not a bug and Betterknob does not/will not try to work around these restrictions. If running Betterknob as admin doesn't make it work, then Betterknob will likely never work when that application is focused
- Does not write to disk other than to your %TEMP% folder, and only once on launch ([PyInstaller does](https://pyinstaller.org/en/stable/operating-mode.html#how-the-one-file-program-works), not betterknob) 

<br />

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

#### Attribution

<a href="https://www.flaticon.com/free-icons/baking" title="baking icons">icons by Freepik - Flaticon</a>
