import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox
from app.config import AppConfig
from app.utils.db import HistoryDatabase
from app.ui.main_window import MainWindow

# Mock QMessageBox to prevent blocking test dialogs
QMessageBox.information = lambda *args, **kwargs: None
QMessageBox.warning = lambda *args, **kwargs: None
QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes

# Ensure headless offscreen platform for Qt test
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_ui_security():
    app = QApplication.instance() or QApplication(sys.argv)

    test_db_path = Path("test_history.db")
    test_cfg_path = Path("test_config.json")
    for p in (test_db_path, test_cfg_path):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    # Initialize config with a configured secret key and model
    test_key = "sk-live-supersecretapikey123456789"
    cfg = AppConfig(ai_api_key=test_key, ai_enabled=True, ai_model="xiaomi/mimo-v2.6-flash")
    # Redirect save to temporary test file
    cfg.save = lambda file_path=test_cfg_path: None
    db = HistoryDatabase(test_db_path)

    window = MainWindow(config=cfg, stt_engine=None, db=db, hotkey_manager=None, ai_service=None)

    # 1. Verify API Key and Model fields are completely REMOVED from Desktop UI
    print("[UI Test 1] Verifying API Key and Model fields are removed from Desktop UI...")
    assert not hasattr(window, "edit_ai_key"), "API key input field must be completely removed from UI!"
    assert not hasattr(window, "combo_ai_model"), "Model selection field must be completely removed from UI!"
    assert not hasattr(window, "edit_ai_base_url"), "Base URL field must be completely removed from UI!"
    assert not hasattr(window, "combo_provider"), "Provider dropdown must be completely removed from UI!"
    assert not hasattr(window, "_toggle_key_visibility"), "Unmasking toggle must not exist!"
    print("[OK] All model and API key fields are completely absent from the UI.")

    # 2. Verify Top Bar does not expose raw model or keys
    print("\n[UI Test 2] Verifying Top Bar status badges...")
    badge_text = window.pill_model.text()
    print(f"Top Bar AI Badge: '{badge_text.encode('ascii', 'replace').decode()}'")
    assert "sk-" not in badge_text
    assert "mimo" not in badge_text.lower()
    assert "AI Polish: Active" in badge_text
    print("[OK] Top Bar shows clean status badge without leaking model or key.")

    # 3. Test saving settings preserves environment / config keys
    print("\n[UI Test 3] Testing settings save preserves backend credentials...")
    window._save_settings()
    assert window.config.ai_api_key == test_key
    assert window.config.ai_model == "xiaomi/mimo-v2.6-flash"
    print("[OK] Settings save leaves credentials intact in configuration.")

    # 4. Test offline mode toggle
    print("\n[UI Test 4] Testing Strict Offline Mode GUI behavior...")
    window.check_strict_offline.setChecked(True)
    assert not window.check_ai_enabled.isEnabled()
    assert not window.btn_test_ai.isEnabled()
    assert "offline" in window.lbl_test_status.text().lower()
    window._save_settings()
    assert "AI: Offline" in window.pill_model.text()
    print("[OK] Strict offline mode disables cloud AI and updates status pill.")

    window.close()
    try:
        if test_db_path.exists():
            test_db_path.unlink()
    except Exception:
        pass
    print("\nALL UI SECURITY TESTS PASSED!")


if __name__ == "__main__":
    test_ui_security()
