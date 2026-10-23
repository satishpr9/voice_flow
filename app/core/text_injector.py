import time
from typing import Optional
import pyperclip
from pynput.keyboard import Controller, Key


class TextInjector:
    """Injects transcribed text into whichever window is currently focused in Windows."""

    def __init__(self):
        self._keyboard = Controller()

    def paste_text(self, text: str, restore_clipboard: bool = False, delay: float = 0.05) -> bool:
        """Copies text to clipboard and issues a Ctrl+V event to paste into the active window."""
        if not text:
            return False

        old_clipboard = None
        if restore_clipboard:
            try:
                old_clipboard = pyperclip.paste()
            except Exception:
                old_clipboard = None

        try:
            # Set new text to clipboard
            pyperclip.copy(text)
            time.sleep(delay)

            # Simulate Ctrl + V
            with self._keyboard.pressed(Key.ctrl):
                self._keyboard.press('v')
                self._keyboard.release('v')

            if restore_clipboard and old_clipboard is not None:
                time.sleep(0.1)
                try:
                    pyperclip.copy(old_clipboard)
                except Exception:
                    pass

            return True
        except Exception as e:
            print(f"[TextInjector] Error pasting text: {e}")
            return False

    def type_text(self, text: str, delay_per_char: float = 0.005) -> bool:
        """Types characters sequentially (useful if paste is blocked or for specific terminals)."""
        if not text:
            return False

        try:
            for char in text:
                self._keyboard.type(char)
                if delay_per_char > 0:
                    time.sleep(delay_per_char)
            return True
        except Exception as e:
            print(f"[TextInjector] Error typing text: {e}")
            return False
