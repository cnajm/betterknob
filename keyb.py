import collections
from typing import List, Optional
import keyboard
import sys
import signal
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioMeterInformation, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CoInitialize, CoUninitialize, CLSCTX_ALL
import threading
import time
import win32gui
import win32process
from contextlib import contextmanager
from threading import local
import psutil
import queue
import tkinter as tk
from tkinter import ttk
import logging
import os
import configparser

logging.basicConfig(level=logging.INFO)  # Hide debug logs from other modules
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def load_config():
    config = configparser.ConfigParser()

    # config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    # Get executable directory, handling PyInstaller ca

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

    return settings_

settings = load_config()
DEFAULT_PROFILE = settings.get('default_process')
process_name = DEFAULT_PROFILE
last_profile_change = time.time()
profile_timer = None
current_session_id = 0
# COOLDOWN_PERIOD = 0.5  # seconds
# last_check_time = 0
# audio_lock = Lock()

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
                process_name, volume_level = msg
                self._update_display(process_name, volume_level)
        except queue.Empty:
            pass
        if self.running:
            self.root.after(10, self.process_queue)
    
    def _update_display(self, process_name, volume_level):
        self.app_label.config(text=process_name)
        if type(volume_level) is str:
            self.volume_label.config(text=volume_level)
            self.progress['value'] = 0
        else:
            self.volume_label.config(text=f"{int(volume_level * 100)}%")
            self.progress['value'] = volume_level * 100

        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        # x = self.root.winfo_screenwidth() - width - 20 # right aligned
        x = (self.root.winfo_screenwidth() // 2) - (width // 2) # center aligned
        y = 20
        self.root.geometry(f'+{x}+{y}')

        self.root.deiconify()
        if self.hide_timer is not None:
            self.root.after_cancel(self.hide_timer)
        self.hide_timer = self.root.after(5000, self.root.withdraw)
    
    def show_volume(self, process_name, volume_level):
        if process_name == '_system':
            process_name = 'System'
        self.queue.put((process_name, volume_level))
    
    def cleanup(self):
        self.running = False
        self.queue.put(None)  # Signal to stop
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass

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

def set_volume_by_process_name(process_name, volume_level):
    with com_initialized():  # Add context manager here
        if process_name.lower() == "_system":
            # Handle system-wide volume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            if volume:
                volume.SetMasterVolumeLevelScalar(volume_level, None)
                return volume_level
            return None

        # Handle process-specific volume
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and session.Process.name().lower() == process_name.lower():
                volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                if volume:
                    volume.SetMasterVolume(volume_level, None)
                    return volume_level
    return None

def get_current_volume(process_name):
    with com_initialized():
        if process_name.lower() == "_system":
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            if volume:
                return volume.GetMasterVolumeLevelScalar()
            return None

        # Handle process-specific volume
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and session.Process.name().lower() == process_name.lower():
                volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                if volume:
                    return volume.GetMasterVolume()
        return None

def reset_to_default_profile():
    global process_name
    if process_name != DEFAULT_PROFILE:
        process_name = DEFAULT_PROFILE
        print(f'Reverting to default profile: {DEFAULT_PROFILE}')

def start_profile_timer():
    global profile_timer
    if profile_timer:
        profile_timer.cancel()
    profile_timer = threading.Timer(5.0, reset_to_default_profile)
    profile_timer.start()

def switch_profile(new_profile, profile_name):
    global process_name, last_profile_change
    logger.info(f'On {profile_name} profile')
    process_name = new_profile
    last_profile_change = time.time()
    start_profile_timer()

def get_dynamic_step(current_volume):
    # Larger steps when volume is high, smaller steps as it approaches 0
    min_step = settings.get('volume_step_min')
    max_step = settings.get('volume_step_max')
    # Log scaling to make steps smaller as volume decreases
    step = max_step * (current_volume)# + 0.1)  # Add 0.1 to prevent step becoming 0
    return max(min_step, min(step, max_step))

def handle_no_audio_swap(target_process_name: str, volume: int | None) -> dict | bool:
    if target_process_name == '_system':
        return False # always allow system volume to be changed

    logger.debug('switching to focused app or first audio source, whichever is first')
    active_sessions = get_audio_sessions()
    if target_process_name in active_sessions:
        logger.debug(f"Current target process is valid: {target_process_name}")
        return {"volume": volume, "process": target_process_name}

    focused_app = get_focused_process_name()
    if focused_app in active_sessions:
        logger.debug("Switching to focused app: %s", focused_app)
        volume = get_current_volume(focused_app)
        switch_profile(focused_app, focused_app)
        return {"volume": volume, "process": focused_app}
    else:
        logger.debug('Switching to first audio source')
        if len(active_sessions) > 0:
            volume = get_current_volume(active_sessions[0])
            switch_profile(active_sessions[0], active_sessions[0])
            return {"volume": volume, "process": active_sessions[0]}

    logger.debug('no audio source to switch to')
    return False

def volume_up():
    with com_initialized():
        current_volume = get_current_volume(process_name)
        should_swap_audio_source = handle_no_audio_swap(process_name, current_volume)
        if should_swap_audio_source is not False:
            current_volume = should_swap_audio_source.get("volume")
            new_process_name = should_swap_audio_source.get("process")
            switch_profile(new_process_name, new_process_name)

        if current_volume is not None:
            step = get_dynamic_step(current_volume)
            new_volume = min(current_volume + step, 1.0)
            set_volume_by_process_name(process_name, new_volume)
            print(f"{process_name} volume increased to {new_volume * 100}%")
            volume_indicator.show_volume(process_name, new_volume)
            start_profile_timer()  # Reset timer on volume change

def volume_down():
    with com_initialized():
        current_volume = get_current_volume(process_name)
        should_swap_audio_source = handle_no_audio_swap(process_name, current_volume)
        if should_swap_audio_source is not False:
            current_volume = should_swap_audio_source.get("volume")
            new_process_name = should_swap_audio_source.get("process")
            switch_profile(new_process_name, new_process_name)

        if current_volume is not None:
            step = get_dynamic_step(current_volume)
            new_volume = max(current_volume - step, 0.0)
            set_volume_by_process_name(process_name, new_volume)
            print(f"{process_name} volume decreased to {new_volume * 100}%")
            volume_indicator.show_volume(process_name, new_volume)
            start_profile_timer()  # Reset timer on volume change

def get_audio_sessions():
    """Get active audio sessions with their volumes"""
    active_sessions = []

    with com_initialized():
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if not session.Process:
                continue

            try:
                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                volume = session._ctl.QueryInterface(ISimpleAudioVolume)

                peak = meter.GetPeakValue()
                current_vol = volume.GetMasterVolume() if volume else 0

                # Only show processes with audio activity
                if peak > 0.0:
                    logger.debug(f"\nActive audio sessions:\n- {session.Process.name()}: {current_vol * 100:.1f}% (Peak: {peak:.3f})")
                    active_sessions.append(session.Process.name())

            except Exception:
                continue

    return active_sessions

def get_focused_process_name():
    try:
        # Get handle of active window
        hwnd = win32gui.GetForegroundWindow()
        # Get process ID from window handle
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        # Get process name from process ID
        process = psutil.Process(pid)
        return process.name()
    except Exception as e:
        print(f"Failed to get currently focused process {e}")
        return DEFAULT_PROFILE

def handle_volume_keys(event):
    # print(f"Key: {event.name}, Scan: {event.scan_code}, Event type: {event.event_type}")
    if event.event_type == keyboard.KEY_DOWN:
        # current_time = time.time()
        # get_audio_sessions()
        if event.scan_code == -175:  # Volume Up
            volume_up()
            return False
        elif event.scan_code == -174:  # Volume Down
            volume_down()
            return False
        # elif event.scan_code == 75:  # numpad 4
        elif event.name == settings.get('key_cycle_audio_source'):
            # global last_check_time
            global current_session_id
            if 1 == 1: #current_time - last_check_time > COOLDOWN_PERIOD:
                # last_check_time = current_time
                active_sessions = get_audio_sessions()
                print(f"Active sessions: {active_sessions} {len(active_sessions)}")
                if len(active_sessions) > 0:
                    current_session_id += 1
                    current_session_id %= len(active_sessions)
                    if len(active_sessions) > 1 and active_sessions[current_session_id] == process_name:
                        # the return to default behavior often leads to scenarios where the next profile to switch to is the same as the current one
                        # this checks for that
                        current_session_id += 1
                        current_session_id %= len(active_sessions)
                    next_process_name = active_sessions[current_session_id]
                    print(f"Switching to session {current_session_id}")
                    switch_profile(next_process_name, next_process_name)
                    current_volume = get_current_volume(next_process_name)
                    volume_indicator.show_volume(next_process_name, current_volume)

            return False
        elif event.name == settings.get('key_currently_focused'):
            focused_app = get_focused_process_name()
            switch_profile(focused_app, focused_app)
            current_volume = get_current_volume(focused_app)
            if current_volume is None:
                current_volume = "no audio"
            volume_indicator.show_volume(focused_app, current_volume)
            return False
        elif event.name == settings.get('key_swap_to_system'):
            switch_profile('_system', '_system')
            current_volume = get_current_volume('_system')
            volume_indicator.show_volume("_system", current_volume)  # Change label to "System"
            return False

    if event.scan_code in [-175, -174]:
        return False
    
    return True

def cleanup():
    if profile_timer:
        profile_timer.cancel()
    volume_indicator.cleanup()
    keyboard.unhook_all()

# import atexit
# atexit.register(cleanup)


# keyboard.unhook_all()
# keyboard.hook(handle_volume_keys, suppress=True)

# print("Press volume up/down keys to adjust volume. Press 'esc' to exit.")
# # keyboard.wait("esc")
# while True:
#     volume_indicator.update()
#     if keyboard.is_pressed('esc'):
#         break
#     time.sleep(0.01)
# cleanup()

def signal_handler(signum, frame):
    print("Force exit, cleaning up...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

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
