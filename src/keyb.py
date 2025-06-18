import configparser
import os
import signal
import sys

import keyboard

from utils.logger import logger, setup_logger
from utils.mixer_profile import MixerProfile
from utils.system_audio_handler import SystemAudioHandlerWin
from utils.volume_overlay import VolumeOverlay


def get_version() -> str:
    try:
        if getattr(sys, "frozen", False):
            # Running as compiled exe, the version file will be in the extracted temp dir
            version_path = os.path.join(sys._MEIPASS, "version.dat")  # type: ignore[attr-defined]
            with open(version_path, encoding="utf-8") as f:
                return f.read().strip()
        else:
            # running as a python script, read directly from pyproject
            import tomllib

            with open("pyproject.toml", "rb") as f:
                data = tomllib.load(f)
                return data["project"]["version"]

    except Exception as e:
        logger.error(f"Failed to read version: {e}")
        return "unknown"


def load_config():
    config = configparser.ConfigParser()

    if getattr(sys, "frozen", False):  # noqa: SIM108
        # Running as bundled exe
        exe_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        exe_dir = os.path.dirname(__file__)

    config_path = os.path.join(exe_dir, "config.ini")

    # Create default config if not exists
    if not os.path.exists(config_path):
        config["Settings"] = {
            "default_process": "chrome.exe",
            "key_quit": "f13",  # 100
            "key_cycle_audio_source": "f15",  # 102
            "key_currently_focused": "f16",  # 103
            "key_swap_to_system": "f17",  # 104
            "key_volume_up": "scan:-175",
            "key_volume_down": "scan:-174",
            "volume_step_min": "0.05",
            "volume_step_max": "0.10",
            "change_system_vol_if_no_audio": "false",
            "show_overlay": "true",
            "debug": "false",
        }
        with open(config_path, "w", encoding="utf-8") as f:
            logger.info(f"No config.ini, creating default config at {config_path}")
            config.write(f)
    else:
        logger.debug(f"Loading config from {config_path}")

    config.read(config_path)
    try:
        config["Settings"]
    except KeyError:
        logger.error("No settings found in config.ini")
        exit(1)

    settings_: dict[str, str | float] = dict(config["Settings"])

    numeric_settings = ["volume_step_min", "volume_step_max"]
    for key in numeric_settings:
        settings_[key] = float(settings_[key])

    enable_debugging = False
    if str(settings_["debug"]).lower() == "true":
        enable_debugging = True
        # recreate logger with debug enabled
        setup_logger(debug=True)
        logger.info("Debug logging enabled")

    return settings_, enable_debugging


settings, is_debugging = load_config()


def cleanup(mixer_profile=False):
    if mixer_profile:
        if mixer_profile.revert_timer:
            mixer_profile.revert_timer.cancel()

        mixer_profile.volume_indicator.cleanup()
        mixer_profile.system_audio_ref.cleanup()

    keyboard.unhook_all()


def signal_handler(signum, frame):
    logger.info("Force exit, cleaning up...")
    cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def main():
    logger.info(f"Starting BetterKnob v{get_version()}")
    show_overlay = settings.get("show_overlay", "true").lower() == "true"
    volume_mixer = MixerProfile(settings, VolumeOverlay(is_debugging, show_overlay), SystemAudioHandlerWin())
    key_quit = volume_mixer.hotkeys.key_quit

    def check_exit():
        if keyboard.is_pressed(key_quit["keybind"]):
            logger.info("Exiting...")
            cleanup(volume_mixer)
            sys.exit(0)
        else:
            volume_mixer.volume_indicator.root.after(1000, check_exit)

    try:
        keyboard.hook(volume_mixer.handle_volume_keys, suppress=True)
        logger.info(
            f"Press volume up/down keys to adjust volume. "
            f"Press '{key_quit['keybind']}{' (scan code)' if key_quit['use_scan'] else ''}' to exit."
        )
        volume_mixer.volume_indicator.root.after(1000, check_exit)
        volume_mixer.volume_indicator.root.mainloop()
    except Exception as e:
        logger.error(f"Error: {e}")
        if is_debugging:
            raise e
    finally:
        cleanup(volume_mixer)


if __name__ == "__main__":
    main()
