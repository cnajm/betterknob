import keyboard
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioMeterInformation
from ctypes import cast, POINTER
from comtypes import CoInitialize, CoUninitialize
import threading
import time
import win32gui
import win32process
from threading import Lock
from contextlib import contextmanager
from threading import local
import psutil

DEFAULT_PROFILE = "chrome.exe"
process_name = DEFAULT_PROFILE
volume_step = 0.05
last_profile_change = time.time()
profile_timer = None
current_session_id = 0
COOLDOWN_PERIOD = 0.5  # seconds
last_check_time = 0
audio_lock = Lock()

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
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name().lower() == process_name.lower():
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            if volume:
                volume.SetMasterVolume(volume_level, None)
                return volume_level
    return None

def get_current_volume(process_name):
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
    print(f'On {profile_name} profile')
    process_name = new_profile
    last_profile_change = time.time()
    start_profile_timer()

def get_dynamic_step(current_volume):
    # Larger steps when volume is high, smaller steps as it approaches 0
    min_step = 0.02  # Minimum 5% change
    max_step = 0.15  # Maximum 15% change
    # Log scaling to make steps smaller as volume decreases
    step = max_step * (current_volume)# + 0.1)  # Add 0.1 to prevent step becoming 0
    return max(min_step, min(step, max_step))

def volume_up():
    with com_initialized():
        current_volume = get_current_volume(process_name)
        if current_volume is not None:
            step = get_dynamic_step(current_volume)
            new_volume = min(current_volume + step, 1.0)
            set_volume_by_process_name(process_name, new_volume)
            print(f"{process_name} volume increased to {new_volume * 100}%")
            start_profile_timer()  # Reset timer on volume change

def volume_down():
    with com_initialized():
        current_volume = get_current_volume(process_name)
        if current_volume is not None:
            step = get_dynamic_step(current_volume)
            new_volume = max(current_volume - step, 0.0)
            set_volume_by_process_name(process_name, new_volume)
            print(f"{process_name} volume decreased to {new_volume * 100}%")
            start_profile_timer()  # Reset timer on volume change

def get_audio_sessions():
    """Get active audio sessions with their volumes"""
    print("\nActive audio sessions:")
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
                    print(f"- {session.Process.name()}: {current_vol * 100:.1f}% (Peak: {peak:.3f})")
                    active_sessions.append(session.Process.name())
                    
            except Exception:
                continue
                
    print()
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
        elif event.scan_code == 102:  # f15
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
                    print(f"Switching to session {current_session_id}")
                    switch_profile(active_sessions[current_session_id], active_sessions[current_session_id])
                # if current_session_id >= len(active_sessions):
                #     current_session_id = 0
            return False
        elif event.scan_code == 103:  # f16
            # switch_profile("Overwatch.exe()", "Overwatch")
            focused_app = get_focused_process_name()
            switch_profile(focused_app, focused_app)
            return False
        elif event.scan_code == 104:  # f17
            switch_profile("chrome.exe", "Chrome")
            return False
        # elif event.scan_code == 81:  # numpad 3
        #     switch_profile("discord.exe", "Discord")
        #     return False

    if event.scan_code in [-175, -174]:
        return False
    
    return True

def cleanup():
    if profile_timer:
        profile_timer.cancel()
    keyboard.unhook_all()

import atexit
atexit.register(cleanup)


keyboard.unhook_all()
keyboard.hook(handle_volume_keys, suppress=True)

print("Press volume up/down keys to adjust volume. Press 'esc' to exit.")
keyboard.wait("esc")
cleanup()
