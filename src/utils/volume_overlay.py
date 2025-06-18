import queue
import tkinter as tk
from tkinter import ttk

from utils.logger import logger


class VolumeOverlay:
    def __init__(self, debug_logging: bool = False, show_overlay: bool = False):
        self.queue: queue.Queue = queue.Queue(50)
        self.running = True
        self.show_overlay = show_overlay
        self.debug_logging = debug_logging

        self.root = tk.Tk()  # the event loop is coupled to the overlay, refactor later if needed
        self.root.withdraw()
        if self.show_overlay:
            is_topmost = True
            self.root.attributes("-topmost", is_topmost)
            self.root.overrideredirect(boolean=True)

            # Styling
            style = ttk.Style()
            style.theme_use("classic")
            style.configure(
                "Volume.Horizontal.TProgressbar",
                background="#440053",
                troughcolor="#E0E0E0",
            )

            self.frame = ttk.Frame(self.root, padding="10")
            self.frame.grid()

            self.app_label = ttk.Label(self.frame)
            self.app_label.grid(column=0, row=0)

            self.progress = ttk.Progressbar(self.frame, length=200, style="Volume.Horizontal.TProgressbar", maximum=100)
            self.progress.grid(column=0, row=1, pady=5)

            self.volume_label = ttk.Label(self.frame)
            self.volume_label.grid(column=0, row=2)

        self.process_queue()
        self.hide_overlay_timer: str | None = None

    # the queue is used to avoid blocking the main thread while updating the UI
    def process_queue(self):
        try:
            msg = self.queue.get_nowait()
            if msg is not None:
                name, volume_level, current_session_id = msg
                self._update_display(name, volume_level, current_session_id)
        except queue.Empty:
            pass
        if self.running:
            self.root.after(10, self.process_queue)

    def _update_display(self, name: str, volume_level: float, current_session_id: str = ""):
        if not self.show_overlay:
            return

        label = name
        if self.debug_logging:
            label = f"{label} {current_session_id}"

        self.app_label.config(text=label)
        if volume_level is None:
            self.volume_label.config(text="No audio")
            self.progress["value"] = 0
        elif isinstance(volume_level, str):
            self.volume_label.config(text=volume_level)
            self.progress["value"] = 0
        else:
            self.volume_label.config(text=f"{int(volume_level * 100)}%")
            self.progress["value"] = volume_level * 100

        self.root.update_idletasks()
        width = self.root.winfo_width()
        # height = self.root.winfo_height()
        # x = self.root.winfo_screenwidth() - width - 20 # right aligned
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)  # center aligned
        y = 20
        self.root.geometry(f"+{x}+{y}")

        self.root.deiconify()
        if self.hide_overlay_timer is not None:
            self.root.after_cancel(self.hide_overlay_timer)
        self.hide_overlay_timer = self.root.after(5000, self.root.withdraw)

    def show_volume(self, process, volume_level, current_session_id=""):
        if process == "_system":
            process = "System"
        self.queue.put((process, volume_level, current_session_id))

    def cleanup(self):
        self.running = False
        try:
            self.root.quit()
        except Exception as e:
            logger.warning(f"error while destroy root window {e}")
