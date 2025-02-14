import threading
from ctypes import POINTER, cast

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

from utils.com_utils import com_initialized
from utils.logger import logger


class SystemAudioHandlerWin:
    def __init__(self):
        self._volume = None
        self._initialized = False
        self._lock = threading.RLock()  # keep things clean

    def _get_audio_interface(self):
        try:
            with com_initialized():
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            logger.error(f"Failed to get audio interface: {e}")
            return None

    def initialize(self):
        if self._initialized and self._volume:
            return True

        try:
            self._volume = self._get_audio_interface()
            if self._volume:
                self._initialized = True
                return True
        except Exception as e:
            logger.error(f"Failed to initialize system audio: {e}")
            self.cleanup()
        return False

    def get_volume(self):
        with self._lock:
            try:
                if not self._initialized and not self.initialize():
                    return None

                if self._volume:
                    try:
                        return self._volume.GetMasterVolumeLevelScalar()
                    except OSError as e:
                        logger.error(f"Error getting system volume level: {e}")
                        self.cleanup()
                return None
            except Exception as e:
                logger.error(f"Error initializing or getting system volume level: {e}")
                self.cleanup()
                return None

    def set_volume(self, level):
        with self._lock:
            try:
                if not self._initialized and not self.initialize():
                    return None

                if self._volume:
                    try:
                        self._volume.SetMasterVolumeLevelScalar(level, None)
                        return level
                    except OSError:
                        self.cleanup()
                return None
            except Exception as e:
                logger.error(f"Error setting system volume: {e}")
                self.cleanup()
                return None

    def cleanup(self):
        try:
            self._volume = None
            self._initialized = False
        except Exception as e:
            logger.debug(f"Error during cleanup: {e}")
