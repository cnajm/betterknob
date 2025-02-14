from threading import Lock
from typing import TYPE_CHECKING

from pycaw.pycaw import AudioSession, AudioUtilities, IAudioMeterInformation

from utils.com_utils import ComObject, com_initialized
from utils.logger import logger

if TYPE_CHECKING:
    from utils.system_audio_handler import SystemAudioHandlerWin

volume_lock = Lock()


class AudioSessionHandler:
    def __init__(self, name: str, system_audio: "SystemAudioHandlerWin"):
        self.name = name
        self.is_system_audio = name == "_system"
        if self.is_system_audio:
            # there's no need to create a new system handler every time because it should never change
            self._audio_sessions: list[AudioSession] = [system_audio]
        else:
            self._audio_sessions = []

    @property
    def audio_sessions(self) -> list[AudioSession] | list["SystemAudioHandlerWin"]:
        if self.is_system_audio:
            return self._audio_sessions

        active_sessions = []
        active_sessions_names = set()

        with com_initialized():
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if not session.Process:
                    continue
                if session.Process.name() != self.name:
                    continue
                try:
                    meter = session._ctl.QueryInterface(IAudioMeterInformation)
                    volume = session.SimpleAudioVolume

                    peak = meter.GetPeakValue()
                    current_vol = volume.GetMasterVolume() if volume else 0
                    # Only show processes with audio activity
                    if peak > 0.0:
                        logger.debug(
                            f"\nActive audio sessions:\n- {session.Process.name()}: {current_vol * 100:.1f}% (Peak: {peak:.3f})"
                        )
                        active_sessions_names.add(session.Process.name())

                except Exception as e:
                    logger.error(f"Failed to get audio session: {e}")
                    continue

            active_sessions = [s for s in sessions if s.Process and s.Process.name() in active_sessions_names]
            self._audio_sessions = active_sessions
            return active_sessions

    @property
    def volume(self) -> float | None:
        if self.is_system_audio:
            return self.audio_sessions[0].get_volume()

        # no audio
        if not self.audio_sessions:
            return None

        com = ComObject()
        try:
            with volume_lock, com:
                session = self.audio_sessions[0]
                volume = None
                if isinstance(session, AudioSession):
                    volume = com.store_ref(session.SimpleAudioVolume)
                if volume:
                    return volume.GetMasterVolume()
        except Exception as e:
            logger.error(f"Failed to get volume for {self.name}: {e}")
        finally:
            com.clear()
        return None

    @volume.setter
    def volume(self, level: float):
        if self.is_system_audio:
            return self.audio_sessions[0].set_volume(level)

        # no audio
        if not self.audio_sessions:
            return None

        com = ComObject()
        try:
            with volume_lock, com:
                for session in self.audio_sessions:
                    volume = None
                    if isinstance(session, AudioSession):
                        volume = com.store_ref(session.SimpleAudioVolume)
                    if volume:
                        volume.SetMasterVolume(level, None)
        except Exception as e:
            logger.error(f"Failed to set volume for {self.name}: {e}")
        finally:
            com.clear()
