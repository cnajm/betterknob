import threading
import time
from typing import TYPE_CHECKING, Literal, Optional

import keyboard
import psutil
import win32gui
import win32process
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation

from utils import hotkey_handler
from utils.audio_session_handler import AudioSessionHandler
from utils.com_utils import com_initialized
from utils.logger import logger

if TYPE_CHECKING:
    from utils.system_audio_handler import SystemAudioHandlerWin
    from utils.volume_overlay import VolumeOverlay


class MixerProfile:
    """A mixer profile manages audio sessions which could be associated with a specific process or with system audio."""

    def __init__(self, settings, volume_overlay: "VolumeOverlay", system_audio: "SystemAudioHandlerWin"):
        self.settings = settings
        self.volume_indicator = volume_overlay
        self.system_audio_ref = system_audio

        self.default_process_name: str = settings.get("default_process")
        self.min_step: float = settings.get("volume_step_min")
        self.max_step: float = settings.get("volume_step_max")
        # self.name = name
        self.current_session = AudioSessionHandler(self.default_process_name, self.system_audio_ref)
        self.revert_timer: threading.Timer | None = None
        self.last_session_change = time.time()
        self.current_session_id: int = 0

        self.last_check_time: float = 0
        self.cycle_debounce: float = 0.3  # seconds

        self.hotkeys = hotkey_handler.UserHotkeys(settings)

    def revert_to_default_process(self):
        if self.current_session.name != self.default_process_name:
            # process might not exist anymore, try to get it again
            self.current_session = AudioSessionHandler(self.default_process_name, self.system_audio_ref)
            logger.info(f"Reverting to default profile: {self.default_process_name}")

    def start_revert_timer(self):
        if self.revert_timer:
            self.revert_timer.cancel()
        self.revert_timer = threading.Timer(5.0, self.revert_to_default_process)
        self.revert_timer.start()

    def switch_process(self, profile_name: str):
        logger.info(f"On {'system' if profile_name == '_system' else profile_name} profile")
        self.current_session = AudioSessionHandler(profile_name, self.system_audio_ref)
        self.last_session_change = time.time()
        self.start_revert_timer()

    def get_dynamic_step(self, current_volume: float, direction: Optional[Literal[1, -1]] = None) -> float:
        """Log scaling for larger steps when volume is high, smaller steps as volume approaches 0."""
        step = self.max_step * (current_volume)
        if direction == 1 and current_volume <= 0.3:
            # on positive volume changes, double the step size until log scaling kicks in (feels more natural)
            step *= 2
        return max(self.min_step, min(step, self.max_step))

    def handle_volume_keys(self, event):
        if event.event_type == keyboard.KEY_DOWN:
            # if event.name == 'esc':  # debugging
            #     logger.warning("manually running gc")
            #     import gc
            #     gc.collect()
            #     return False

            if event.scan_code in self.hotkeys.lookup_scan_codes:
                action = self.hotkeys.lookup_scan_codes[event.scan_code]
                logger.debug(f"Handling hotkey: {action} for scan code: {event.scan_code}")
                return self._handle_hotkey_action(action, event)

            if event.name in self.hotkeys.lookup_names:
                action = self.hotkeys.lookup_names[event.name]
                logger.debug(f"Handling hotkey: {event.name}")
                return self._handle_hotkey_action(action, event)

        return True

    def _handle_hotkey_action(self, action, event):
        """Handle a specific hotkey action."""
        logger.debug(f"Handling action: {action} for event: {event}")
        if action == "key_volume_up":
            self.volume_up()
            return False

        elif action == "key_volume_down":
            self.volume_down()
            return False

        elif action == "key_cycle_audio_source":
            current_time = time.time()
            if current_time - self.last_check_time > self.cycle_debounce:
                self.last_check_time = current_time
                active_sessions = self.get_audio_sessions_names()
                logger.debug(f"Active sessions: {active_sessions} {len(active_sessions)}")
                if len(active_sessions) > 0:
                    self.current_session_id += 1
                    self.current_session_id %= len(active_sessions)

                    # the "revert to default process" behavior sometimes creates weird scenarios with cycling
                    # where the next profile to switch to is the one we're currently on
                    # this feels weird and breaks the mental flow of cycling through audio sources
                    # this accounts for that
                    if len(active_sessions) > 1 and active_sessions[self.current_session_id] == self.current_session.name:
                        self.current_session_id += 1
                        self.current_session_id %= len(active_sessions)

                    next_process_name = active_sessions[self.current_session_id]
                    logger.info(f"Switching to session {self.current_session_id}")
                    self.switch_process(next_process_name)
                    current_volume = self.current_session.volume
                    self.volume_indicator.show_volume(next_process_name, current_volume, self.current_session_id)
                else:
                    logger.info("No active audio sources")
            return False

        elif action == "key_currently_focused":
            focused_app = self.get_focused_process()
            if isinstance(focused_app, psutil.Process):
                focused_app = focused_app.name()
            self.switch_process(focused_app)
            self.volume_indicator.show_volume(focused_app, self.current_session.volume, self.current_session_id)
            return False

        elif action == "key_swap_to_system":
            self.switch_process("_system")
            self.volume_indicator.show_volume("_system", self.current_session.volume, self.current_session_id)
            return False

        return True

    def get_focused_process(self) -> psutil.Process | str:
        try:
            # Get handle of active window
            hwnd = win32gui.GetForegroundWindow()
            # Get process ID from window handle
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process

        except Exception as e:
            logger.error(f"Failed to get currently focused process {e}")
            return self.default_process_name

    def get_audio_sessions_names(self) -> list[str]:
        """Get active audio sessions with their volumes."""
        active_sessions_names = set()

        with com_initialized():
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if not session.Process:
                    continue

                try:
                    meter = session._ctl.QueryInterface(IAudioMeterInformation)

                    peak = meter.GetPeakValue()
                    # current_vol = volume.GetMasterVolume() if volume else 0
                    # Only show processes with audio activity
                    if peak > 0.0:
                        # logger.debug(
                        #     f"\nActive audio sessions:\n- {session.Process.name()}: "
                        #     f"{current_vol * 100:.1f}% (Peak: {peak:.3f})"
                        # )
                        active_sessions_names.add(session.Process.name())

                except Exception as e:
                    logger.error(f"Failed to get audio session: {e}")
                    continue
        return list(active_sessions_names)

    def volume_up(self):
        with com_initialized():
            did_swap = self.handle_no_audio_swap(self.current_session.name)
            if did_swap:
                logger.debug("swapped audio source")

            current_volume = self.current_session.volume

            if current_volume is not None:
                step = self.get_dynamic_step(current_volume, 1)
                new_volume = min(current_volume + step, 1.0)
                self.current_session.volume = new_volume
                logger.debug(f"{self.current_session.name} volume increased to {new_volume * 100}%")
                self.volume_indicator.show_volume(self.current_session.name, new_volume, self.current_session_id)

                # Reset revert timer on volume change
                self.start_revert_timer()

    def volume_down(self):
        with com_initialized():
            did_swap = self.handle_no_audio_swap(self.current_session.name)
            if did_swap:
                logger.debug("swapped audio source")

            current_volume = self.current_session.volume

            if current_volume is not None:
                step = self.get_dynamic_step(current_volume)
                new_volume = max(current_volume - step, 0.0)
                if new_volume <= 0.01:
                    new_volume = 0.0
                self.current_session.volume = new_volume
                logger.debug(f"{self.current_session.name} volume decreased to {new_volume * 100}%")
                self.volume_indicator.show_volume(self.current_session.name, new_volume, self.current_session_id)
                self.start_revert_timer()  # Reset timer on volume change

    def handle_no_audio_swap(self, target_process_name: str) -> bool:
        """If the target process has no audio, switch to the focused app or first audio source instead.

        Returns True if the audio source was swapped away from target_process_name, False otherwise.
        """
        if target_process_name == "_system":
            # always allow system volume to be changed
            return False

        active_session_names = self.get_audio_sessions_names()
        if target_process_name in active_session_names:
            logger.debug(f"Current target process is valid: {target_process_name}")
            return False

        logger.debug("switching to focused app or first audio source, whichever is first")
        focused_app = self.get_focused_process()
        if isinstance(focused_app, psutil.Process):
            focused_app = focused_app.name()

        if focused_app in active_session_names:
            logger.debug("Switching to focused app: %s", focused_app)
            self.switch_process(focused_app)
            return True

        if len(active_session_names) > 0:
            logger.debug("Switching to first audio source")
            self.switch_process(active_session_names[0])
            return True

        if self.settings.get("change_system_vol_if_no_audio").lower() == "true":
            logger.info("Switching to system audio source")
            self.switch_process("_system")
            return True

        logger.debug("no active audio sources to switch to")
        return False
