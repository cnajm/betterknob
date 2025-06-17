"""Helpers for handling user-defined hotkeys."""

from typing import Literal, Optional, TypedDict, Union, overload


class ScanHotkeyBinding(TypedDict):
    keybind: int
    use_scan: Literal[True]


class NameHotkeyBinding(TypedDict):
    keybind: str
    use_scan: Literal[False]


HotkeyBinding = Union[ScanHotkeyBinding, NameHotkeyBinding]


class UserHotkeys:
    def __init__(self, settings: dict):
        self.hotkeys = self.load_hotkeys(settings)
        self.lookup_scan_codes, self.lookup_names = self.generate_lookup_tables(self.hotkeys)

    def load_hotkeys(self, settings: dict) -> dict[str, HotkeyBinding]:
        hotkeys: dict[str, HotkeyBinding] = {}
        for key, binding in settings.items():
            if not key.startswith("key_"):
                continue

            use_scan = False
            if "scan:" in binding:
                use_scan = True
                binding = binding.replace("scan:", "", 1)
                # scan codes are handled as ints
                binding = int(binding)

            if use_scan:
                hotkeys[key] = {"keybind": binding, "use_scan": True}
            else:
                hotkeys[key] = {"keybind": binding, "use_scan": False}

        return hotkeys

    def generate_lookup_tables(self, hotkeys: dict[str, HotkeyBinding]):
        """Create lookup dictionaries for O(1) access."""
        hotkeys_key_code: dict[int, str] = {}
        hotkeys_key_name: dict[str, str] = {}
        for key, key_info in hotkeys.items():
            keybind = key_info["keybind"]
            use_scan = key_info["use_scan"]

            if use_scan:
                assert isinstance(keybind, int)
                hotkeys_key_code[keybind] = key
            else:
                assert isinstance(keybind, str)
                hotkeys_key_name[keybind] = key

        return hotkeys_key_code, hotkeys_key_name

    @overload
    def _get_hotkey(self, key: str, required: Literal[False], default_scan: str) -> Optional[HotkeyBinding]: ...

    @overload
    def _get_hotkey(self, key: str, required: Literal[True], default_scan: Optional[str] = None) -> HotkeyBinding: ...

    def _get_hotkey(self, key: str, required: bool = False, default_scan: Optional[str] = None):
        hotkey = self.hotkeys.get(key, None)
        if not hotkey:
            # fallback to default hotkey
            if required:
                raise ValueError(f"{key} missing from config")

            if default_scan is None:
                raise ValueError(f"{key} missing default_scan, report this to the developer")

            scan_value = int(default_scan.replace("scan:", ""))
            return {"keybind": scan_value, "use_scan": True}
        return hotkey

    @property
    def key_quit(self):
        return self._get_hotkey("key_quit", required=True)

    @property
    def key_cycle_audio_source(self):
        return self._get_hotkey("key_cycle_audio_source", required=True)

    @property
    def key_currently_focused(self):
        return self._get_hotkey("key_currently_focused", required=False, default_scan="scan:103")  # f16

    @property
    def key_swap_to_system(self):
        return self._get_hotkey("key_swap_to_system", required=False, default_scan="scan:104")  # f17

    @property
    def key_volume_up(self):
        return self._get_hotkey("key_volume_up", required=False, default_scan="scan:-175")

    @property
    def key_volume_down(self):
        return self._get_hotkey("key_volume_down", required=False, default_scan="scan:-174")
