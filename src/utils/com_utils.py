"""Utility classes for managing COM initialization and references."""

import threading
from contextlib import contextmanager

from comtypes import CoInitialize, CoUninitialize

from utils.logger import logger

# Thread-local storage for COM initialization state
_thread_local = threading.local()


@contextmanager
def com_initialized():
    """Context manager for COM initialization."""
    # Check if already initialized in this thread
    if not getattr(_thread_local, "com_initialized", False):
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


# Abandon all hope, ye who enter here
class ComObject:
    def __init__(self):
        self.refs = []  # store refs to prevent GC until we're done
        self._initialized = False
        self._lock = threading.RLock()

    def __enter__(self):
        with self._lock:
            if not self._initialized:
                CoInitialize()
                self._initialized = True
        return self

    def store_ref(self, obj):
        if obj:
            with self._lock:
                self.refs.append(obj)  # Store direct reference
        return obj

    def clear(self):
        """Clear references in reverse order."""
        with self._lock:
            while self.refs:
                obj = self.refs.pop()  # LIFO order
                try:
                    if hasattr(obj, "Release"):
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
