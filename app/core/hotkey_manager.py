import threading
from typing import Callable, Optional, Set
from pynput import keyboard


class HotkeyManager:
    """Manages system-wide global hotkeys with both Toggle and Push-to-Talk capabilities."""

    def __init__(
        self,
        hotkey_str: str = "<ctrl>+<alt>+<space>",
        on_toggle: Optional[Callable[[], None]] = None,
        on_press_start: Optional[Callable[[], None]] = None,
        on_release_stop: Optional[Callable[[], None]] = None,
        mode: str = "toggle",
    ):
        self.hotkey_str = hotkey_str.strip()
        self.on_toggle = on_toggle
        self.on_press_start = on_press_start
        self.on_release_stop = on_release_stop
        self.mode = mode

        self._listener: Optional[keyboard.Listener] = None
        self._target_keys: Set = self._parse_hotkey(self.hotkey_str)
        self._current_keys: Set = set()
        self._is_active = False
        self._is_running = False

    def _parse_hotkey(self, hotkey_str: str) -> Set:
        try:
            s = hotkey_str.strip()
            if "<" not in s:
                if "+" in s:
                    s = "+".join(f"<{p.strip().lower()}>" for p in s.split("+") if p.strip())
                elif s.lower().startswith("f"):
                    s = f"<{s.lower()}>"
                elif s.lower() == "space":
                    s = "<space>"
            return set(keyboard.HotKey.parse(s))
        except Exception as e:
            print(f"[HotkeyManager] Could not parse '{hotkey_str}': {e}. Using fallback '<ctrl>+<alt>+<space>'.")
            return set(keyboard.HotKey.parse("<ctrl>+<alt>+<space>"))

    def update_hotkey(self, hotkey_str: str, mode: str) -> None:
        """Updates hotkey string and mode dynamically."""
        self.hotkey_str = hotkey_str.strip()
        self.mode = mode
        self._target_keys = self._parse_hotkey(self.hotkey_str)
        self._current_keys.clear()
        self._is_active = False
        print(f"[HotkeyManager] Updated hotkey: {self.hotkey_str} (mode: {self.mode})")

    def _handle_press(self, key):
        self._current_keys.add(key)
        if self._target_keys <= self._current_keys:
            if not self._is_active:
                self._is_active = True
                if self.mode == "push_to_talk":
                    if self.on_press_start:
                        self.on_press_start()
                else:
                    if self.on_toggle:
                        self.on_toggle()

    def _handle_release(self, key):
        self._current_keys.discard(key)
        if not (self._target_keys <= self._current_keys):
            if self._is_active:
                self._is_active = False
                if self.mode == "push_to_talk":
                    if self.on_release_stop:
                        self.on_release_stop()

    def _on_key_press(self, key):
        if self._listener is not None:
            c_key = self._listener.canonical(key)
        else:
            c_key = key
        self._handle_press(c_key)

    def _on_key_release(self, key):
        if self._listener is not None:
            c_key = self._listener.canonical(key)
        else:
            c_key = key
        self._handle_release(c_key)

    def start(self) -> None:
        """Starts listening for global hotkeys in a background thread."""
        if self._is_running:
            return

        try:
            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._listener.daemon = True
            self._listener.start()
            self._is_running = True
            print(f"[HotkeyManager] Global hotkey active: {self.hotkey_str} (mode: {self.mode})")
        except Exception as e:
            print(f"[HotkeyManager] Error starting listener: {e}")

    def stop(self) -> None:
        """Stops the global hotkey listener."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._is_running = False
        self._current_keys.clear()
        self._is_active = False
