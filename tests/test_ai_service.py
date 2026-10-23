import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import AppConfig
from app.core.ai_service import AIService
from app.core.text_cleaner import TextCleaner


def test_ai_service_fallback():
    print("Testing AIService fallback behaviors...")

    # Case 1: When AI is disabled, polish_text immediately falls back to TextCleaner without making network calls
    config = AppConfig(
        ai_enabled=False,
        ai_model="xiaomi/mimo-v2.6-flash",
        ai_api_key="",
    )
    service = AIService(config)

    raw_text = "um hello basically we we want to test this"
    polished = service.polish_text(raw_text)
    print(f"Disabled AI output: '{polished}'")
    assert "um" not in polished.lower()
    assert "we we" not in polished.lower()
    assert polished.endswith(".")

    # Case 2: When AI is enabled but API key is empty, it also safely falls back
    config2 = AppConfig(
        ai_enabled=True,
        ai_model="xiaomi/mimo-v2.6-flash",
        ai_api_key="",
    )
    service2 = AIService(config2)
    polished2 = service2.polish_text("uh I think this works")
    print(f"Empty key fallback: '{polished2}'")
    assert "uh" not in polished2.lower()

    # Case 3: Test connection with empty key returns helpful error
    ok, msg = service2.test_connection()
    print(f"Test connection empty key: ok={ok}, msg='{msg}'")
    assert not ok
    assert "empty" in msg.lower()

    # Case 4: Omni audio fallback when key is empty
    dummy_audio = np.zeros(16000, dtype=np.float32)
    omni_res = service2.transcribe_omni_audio(dummy_audio)
    assert omni_res is None

    print("\nAIService unit tests PASSED!")


if __name__ == "__main__":
    test_ai_service_fallback()
