import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pynput.keyboard import HotKey, Key, KeyCode
from app.core.hotkey_manager import HotkeyManager

def test_hotkey_manager_parsing():
    print("Testing HotkeyManager parsing and key tracking...")

    events = []
    mgr = HotkeyManager(
        hotkey_str="<ctrl>+<alt>+<space>",
        on_press_start=lambda: events.append("START"),
        on_release_stop=lambda: events.append("STOP"),
        on_toggle=lambda: events.append("TOGGLE"),
        mode="push_to_talk",
    )

    # Verify target keys parsing
    target = mgr._target_keys
    print(f"Target keys parsed: {target}")
    assert len(target) == 3

    # Simulate key events
    keys_list = list(target)
    for k in keys_list:
        mgr._handle_press(k)
    assert events == ["START"], f"Expected ['START'], got {events}"

    # Simulate key release
    mgr._handle_release(keys_list[0])
    assert events == ["START", "STOP"], f"Expected ['START', 'STOP'], got {events}"

    # Test Toggle Mode
    events.clear()
    mgr.mode = "toggle"
    for k in keys_list:
        mgr._handle_press(k)
    assert events == ["TOGGLE"]
    mgr._handle_release(keys_list[0])

    for k in keys_list:
        mgr._handle_press(k)
    assert events == ["TOGGLE", "TOGGLE"]

    print("HotkeyManager unit tests PASSED!")

if __name__ == "__main__":
    test_hotkey_manager_parsing()
