# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-07-04

### Added

#### Config

- Added show_overlay config option
- Added ability to rebind every hotkey, including volume up/down keys
	- Useful if your rotary encoder emits non-standard events

#### Misc

- Double volume up step size at low volumes until logarithmic scaling kicks in

## [1.1.0] - 2025-02-16

### Added

#### Config

- Added config option `change_system_vol_if_no_audio` to control system audio instead when there are no audio sources active.
	- Set it to `true` if you want the audio source selection to be consistent with the way vol up/down works by default without BetterKnob.
	- Set it to `false` (default) if you prefer to keep system volume fixed and adjust other applications' volumes relative to it.

## [1.0.0] - 2025-02-14

### Added

- public release
