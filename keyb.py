from typing import List, Literal
import tkinter as tk
import sys
import signal
from tkinter import ttk
from threading import Lock, local
from ctypes import cast, POINTER
import threading
import time
from contextlib import contextmanager
import queue
import logging
import os
import configparser
import psutil
import win32gui
import win32process
from comtypes import CoInitialize, CoUninitialize, CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation, IAudioEndpointVolume, AudioSession
import keyboard

logging.basicConfig(level=logging.INFO)  # Hide debug logs from other modules
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

volume_lock = Lock()

def load_config():
    config = configparser.ConfigParser()

    if getattr(sys, 'frozen', False):
        # Running as bundled exe
        exe_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        exe_dir = os.path.dirname(__file__)

    config_path = os.path.join(exe_dir, 'config.ini')

    # Create default config if not exists
    if not os.path.exists(config_path):
        config['Settings'] = {
            'default_process': 'chrome.exe',
            'volume_step_min': '0.05',
            'volume_step_max': '0.10',
            'key_quit': 'f13', # 100
            'key_cycle_audio_source': 'f15', # 102
            'key_currently_focused': 'f16', # 103
            'key_swap_to_system': 'f17', # 104
            'debug': 'false'
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            logger.info(f'No config.ini, creating default config at {config_path}')
            config.write(f)
    else:
        logger.info(f'Loading config from {config_path}')
    
    config.read(config_path)
    try:
        config['Settings']
    except KeyError:
        logger.error('No settings found in config.ini')
        exit(1)

    settings_ = dict(config['Settings'])
    settings_['volume_step_min'] = float(settings_['volume_step_min'])
    settings_['volume_step_max'] = float(settings_['volume_step_max'])

    if settings_['debug'].lower() == 'true':
        logger.setLevel(logging.DEBUG)
        logger.info('Debug enabled')

    return settings_

# Thread-local storage for COM initialization state
_thread_local = local()

@contextmanager
def com_initialized():
    """Context manager for COM initialization"""
    # Check if already initialized in this thread
    if not getattr(_thread_local, 'com_initialized', False):
        CoInitialize()
        _thread_local.com_initialized = True
        needs_uninit = True
    else:
        needs_uninit = False
        
    try:
        yield
    finally:
        if needs_uninit:
            CoUninitialize()
            _thread_local.com_initialized = False

def _debug_AudioSession(session):
    return (session.Process.name(), session.ProcessId)

class AudioSessionHandler():
    def __init__(self, name: str):
        self.name = name
        self.is_system_audio = name == '_system'
        if self.is_system_audio:
            # there's no need to create a new system handler every time
            self._audio_sessions = [system_audio]
        else:
            self._audio_sessions: List[AudioSession] = None

    @property
    def audio_sessions(self) -> List[AudioSession] | List['SystemAudioManager']:
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
                        logger.debug(f"\nActive audio sessions:\n- {session.Process.name()}: {current_vol * 100:.1f}% (Peak: {peak:.3f})")
                        active_sessions_names.add(session.Process.name())
    
                except Exception as e:
                    logger.error(f"Failed to get audio session: {e}")
                    continue

            active_sessions = [s for s in sessions if s.Process and s.Process.name() in active_sessions_names]
            self._audio_sessions = active_sessions
            return active_sessions
    
    @property
    def volume(self) -> float:
        if self.is_system_audio:
            return self.audio_sessions[0].get_volume()

        # no audio
        if not self.audio_sessions:
            return None

        com = ComObject()
        try:
            with volume_lock, com:
                session = self.audio_sessions[0]
                volume = com.store_ref(session.SimpleAudioVolume)
                if volume:
                    return volume.GetMasterVolume()
        except Exception as e:
            logger.error(f"Failed to get volume for {self.name}: {e}")
        finally:
            com.clear()

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
                    volume = com.store_ref(session.SimpleAudioVolume) # type: ignore # pylint: disable=no-member # HACK: i don't feel like refactoring SystemAudioManager right now
                    if volume:
                        volume.SetMasterVolume(level, None)
        except Exception as e:
            logger.error(f"Failed to set volume for {self.name}: {e}")
        finally:
            com.clear()

settings = load_config()
DEFAULT_PROFILE_NAME = settings.get('default_process')
current_session = AudioSessionHandler(DEFAULT_PROFILE_NAME)
last_profile_change = time.time()
profile_timer = None
current_session_id = 0
COOLDOWN_PERIOD = 0.5  # seconds
last_check_time = 0

class ComObject:
    def __init__(self):
        self.refs = []  # Strong references
        self._initialized = False
        self._lock = threading.RLock()

    def __enter__(self):
        with self._lock:
            if not self._initialized:
                CoInitialize()
                self._initialized = True
        return self

    def store_ref(self, obj):
        """Store strong reference to COM object"""
        if obj:
            with self._lock:
                self.refs.append(obj)  # Store direct reference
        return obj

    def clear(self):
        """Clear references in reverse order"""
        with self._lock:
            while self.refs:
                obj = self.refs.pop()  # LIFO order
                try:
                    if hasattr(obj, 'Release'):
                        obj.Release()
                except Exception as e:
                    logger.debug(f"Error releasing COM object: {e}")
                obj = None

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.clear()
        finally:
            if self._initialized:
                try:
                    CoUninitialize()
                except Exception as e:
                    logger.debug(f"Error uninitializing COM: {e}")
                self._initialized = False
        return False


class SystemAudioManager:
    def __init__(self):
        self._volume = None
        self._initialized = False
        self._lock = threading.RLock()

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
        with self._lock:  # Single lock point
            try:
                if not self._initialized:
                    if not self.initialize():
                        return None
                        
                if self._volume:
                    try:
                        return self._volume.GetMasterVolumeLevelScalar()
                    except Exception as e:
                        logger.error(f"Error getting volume level: {e}")
                        self.cleanup()
                return None
            except Exception as e:
                logger.error(f"Error getting system volume: {e}")
                self.cleanup()
                return None

    def set_volume(self, level):
        with self._lock:  # Single lock point
            try:
                if not self._initialized:
                    if not self.initialize():
                        return None

                if self._volume:
                    try:
                        self._volume.SetMasterVolumeLevelScalar(level, None)
                        return level
                    except Exception:
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

class VolumeIndicator:
    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        
        # Create root window
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        
        # Style
        style = ttk.Style()
        style.theme_use("classic")
        style.configure("Volume.Horizontal.TProgressbar", 
                       background='#440053',
                       troughcolor='#E0E0E0')
        
        # Frame and widgets setup remains the same
        self.frame = ttk.Frame(self.root, padding="10")
        self.frame.grid()
        
        self.app_label = ttk.Label(self.frame)
        self.app_label.grid(column=0, row=0)
        
        self.progress = ttk.Progressbar(self.frame, length=200,
                                      style="Volume.Horizontal.TProgressbar",
                                      maximum=100)
        self.progress.grid(column=0, row=1, pady=5)
        
        self.volume_label = ttk.Label(self.frame)
        self.volume_label.grid(column=0, row=2)
        
        # Start processing queue
        self.process_queue()
        self.hide_timer = None
        
    def process_queue(self):
        try:
            msg = self.queue.get_nowait()
            if msg is not None:
                name, volume_level = msg
                self._update_display(name, volume_level)
        except queue.Empty:
            pass
        if self.running:
            self.root.after(10, self.process_queue)
    
    def _update_display(self, name, volume_level):
        label = name
        if settings['debug'].lower() == 'true':
            label = f'{label} {current_session_id}'

        self.app_label.config(text=label)
        if volume_level is None:
            self.volume_label.config(text="No audio")
            self.progress['value'] = 0
        elif isinstance(volume_level, str):
            self.volume_label.config(text=volume_level)
            self.progress['value'] = 0
        else:
            self.volume_label.config(text=f"{int(volume_level * 100)}%")
            self.progress['value'] = volume_level * 100

        self.root.update_idletasks()
        width = self.root.winfo_width()
        # height = self.root.winfo_height()
        # x = self.root.winfo_screenwidth() - width - 20 # right aligned
        x = (self.root.winfo_screenwidth() // 2) - (width // 2) # center aligned
        y = 20
        self.root.geometry(f'+{x}+{y}')

        self.root.deiconify()
        if self.hide_timer is not None:
            self.root.after_cancel(self.hide_timer)
        self.hide_timer = self.root.after(5000, self.root.withdraw)
    
    def show_volume(self, process, volume_level):
        if process == '_system':
            process = 'System'
        self.queue.put((process, volume_level))
    
    def cleanup(self):
        self.running = False
        self.queue.put(None)  # Signal to stop
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.warning(f"error while destroy root window {e}")

def reset_to_default_profile():
    global current_session
    if current_session.name != DEFAULT_PROFILE_NAME:
        current_session = AudioSessionHandler(DEFAULT_PROFILE_NAME)
        print(f'Reverting to default profile: {DEFAULT_PROFILE_NAME}')

def start_profile_timer():
    global profile_timer
    if profile_timer:
        profile_timer.cancel()
    profile_timer = threading.Timer(5.0, reset_to_default_profile)
    profile_timer.start()

def switch_profile(profile_name: str):
    global last_profile_change, current_session
    logger.info(f'On {profile_name} profile')
    current_session = AudioSessionHandler(profile_name)
    last_profile_change = time.time()
    start_profile_timer()

def get_dynamic_step(current_volume):
    # Log scaling for larger steps when volume is high, smaller steps as volume approaches 0
    min_step = settings.get('volume_step_min')
    max_step = settings.get('volume_step_max')
    step = max_step * (current_volume)
    return max(min_step, min(step, max_step))

def handle_no_audio_swap(target_process_name: str) -> bool:
    """ If the target process has no audio, switch to the focused app or first audio source instead 
        Returns True if the audio source was swapped away from target_process_name, False otherwise
    """
    if target_process_name == '_system':
        return False # always allow system volume to be changed

    active_session_names = get_audio_sessions_names()
    if target_process_name in active_session_names:
        logger.debug(f"Current target process is valid: {target_process_name}")
        return False

    logger.debug('switching to focused app or first audio source, whichever is first')
    focused_app = get_focused_process()
    if focused_app in active_session_names:
        logger.debug("Switching to focused app: %s", focused_app)
        switch_profile(focused_app)
        return True
    else:
        logger.debug('Switching to first audio source')
        if len(active_session_names) > 0:
            switch_profile(active_session_names[0])
            return True

    logger.debug('no audio source to switch to')
    return False

def volume_up():
    with com_initialized():
        did_swap = handle_no_audio_swap(current_session.name)
        if did_swap:
            logger.debug('swapped audio source')

        current_volume = current_session.volume

        if current_volume is not None:
            step = get_dynamic_step(current_volume)
            new_volume = min(current_volume + step, 1.0)
            current_session.volume = new_volume
            logger.info(f"{current_session.name} volume increased to {new_volume * 100}%")
            volume_indicator.show_volume(current_session.name, new_volume)
            start_profile_timer()  # Reset timer on volume change

def volume_down():
    with com_initialized():
        did_swap = handle_no_audio_swap(current_session.name)
        if did_swap:
            logger.debug('swapped audio source')

        current_volume = current_session.volume

        if current_volume is not None:
            step = get_dynamic_step(current_volume)
            new_volume = max(current_volume - step, 0.0)
            if new_volume <= 0.01:
                new_volume = 0.0
            current_session.volume = new_volume
            logger.info(f"{current_session.name} volume decreased to {new_volume * 100}%")
            volume_indicator.show_volume(current_session.name, new_volume)
            start_profile_timer()  # Reset timer on volume change

def get_audio_sessions_names() -> List[str]:
    """Get active audio sessions with their volumes"""
    active_sessions_names = set()

    with com_initialized():
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if not session.Process:
                continue

            try:
                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                # volume = session.SimpleAudioVolume

                peak = meter.GetPeakValue()
                # current_vol = volume.GetMasterVolume() if volume else 0
                # Only show processes with audio activity
                if peak > 0.0:
                    # logger.debug(f"\nActive audio sessions:\n- {session.Process.name()}: {current_vol * 100:.1f}% (Peak: {peak:.3f})")
                    active_sessions_names.add(session.Process.name())

            except Exception as e:
                logger.error(f"Failed to get audio session: {e}")
                continue
    return list(active_sessions_names)

def get_focused_process() -> psutil.Process | str:
    try:
        # Get handle of active window
        hwnd = win32gui.GetForegroundWindow()
        # Get process ID from window handle
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        # Get process name from process ID
        process = psutil.Process(pid)
        return process
    except Exception as e:
        print(f"Failed to get currently focused process {e}")
        return DEFAULT_PROFILE_NAME

def handle_volume_keys(event):
    # print(f"Key: {event.name}, Scan: {event.scan_code}, Event type: {event.event_type}")
    if event.event_type == keyboard.KEY_DOWN:

        if event.scan_code == -175:  # Volume Up
            volume_up()
            return False

        elif event.scan_code == -174:  # Volume Down
            volume_down()
            return False

        elif event.name == settings.get('key_cycle_audio_source'):
            global last_check_time
            global current_session_id
            current_time = time.time()
            if current_time - last_check_time > COOLDOWN_PERIOD:
            # if 1 == 1: #current_time - last_check_time > COOLDOWN_PERIOD:
                last_check_time = current_time
                active_sessions = get_audio_sessions_names()
                print(f"Active sessions: {active_sessions} {len(active_sessions)}")
                if len(active_sessions) > 0:
                    current_session_id += 1
                    current_session_id %= len(active_sessions)
                    # the return to default behavior often leads to scenarios where the next profile to switch to is the same as the current one
                    # this checks for that
                    if len(active_sessions) > 1 and active_sessions[current_session_id] == current_session.name:
                        current_session_id += 1
                        current_session_id %= len(active_sessions)
                    next_process_name = active_sessions[current_session_id]
                    print(f"Switching to session {current_session_id}")
                    switch_profile(next_process_name)
                    current_volume = current_session.volume
                    volume_indicator.show_volume(next_process_name, current_volume)

            return False

        elif event.name == settings.get('key_currently_focused'):
            focused_app = get_focused_process()
            switch_profile(focused_app.name())
            if current_session.volume is None:
                current_session.volume = "no audio"
            volume_indicator.show_volume(focused_app.name(), current_session.volume)
            return False

        elif event.name == settings.get('key_swap_to_system'):
            switch_profile('_system')
            volume_indicator.show_volume("_system", current_session.volume)
            return False

        # elif event.name == 'esc':
        #     logger.info("manually running gc")
        #     import gc
        #     gc.collect()
        #     return False

    # suppress system handling of volume keys 
    # if event.scan_code in [-175, -174]:
    #     return False

    return True

def cleanup():
    if profile_timer:
        profile_timer.cancel()
    volume_indicator.cleanup()
    # system_audio.cleanup()
    keyboard.unhook_all()

def signal_handler(signum, frame):
    print("Force exit, cleaning up...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

system_audio = SystemAudioManager()
volume_indicator = VolumeIndicator()  # Create here only once
def main():
    def check_exit():
        if keyboard.is_pressed(f'{settings.get("key_quit")}'):
            print("Exiting...")
            cleanup()
            sys.exit(0)
        else:
            volume_indicator.root.after(100, check_exit)

    try:
        keyboard.hook(handle_volume_keys, suppress=True)
        key_name = settings.get("key_quit")
        print(f"Press volume up/down keys to adjust volume. Press '{key_name}' to exit.")
        volume_indicator.root.after(100, check_exit)
        volume_indicator.root.mainloop()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
