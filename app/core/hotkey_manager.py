import threading
from typing import Callable, Optional
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

        self._hotkey_listener: Optional[keyboard.GlobalHotKeys] = None
        self._is_running = False

    def _handle_trigger(self):
        """Called when the hotkey combination is activated."""
        if self.mode == "toggle" and self.on_toggle:
            self.on_toggle()

    def start(self) -> None:
        """Starts listening for global hotkeys in a background thread."""
        if self._is_running:
            return

        try:
            hotkey_map = {self.hotkey_str: self._handle_trigger}
            self._hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
            self._is_running = True
            print(f"[HotkeyManager] Wispr Flow style hotkey active: {self.hotkey_str} (mode: {self.mode})")
        except Exception as e:
            print(f"[HotkeyManager] Could not register hotkey '{self.hotkey_str}': {e}")
            # Fallback to standard Ctrl+Space or Ctrl+Alt+Space
            try:
                fallback_str = "<ctrl>+<space>"
                hotkey_map = {fallback_str: self._handle_trigger}
                self._hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
                self._hotkey_listener.daemon = True
                self._hotkey_listener.start()
                self._is_running = True
                print(f"[HotkeyManager] Registered fallback hotkey: {fallback_str}")
            except Exception as e2:
                print(f"[HotkeyManager] Fallback failed: {e2}")

    def stop(self) -> None:
        """Stops the global hotkey listener."""
        if self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None
        self._is_running = False
