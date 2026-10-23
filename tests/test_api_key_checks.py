import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import AppConfig
from app.core.ai_service import AIService


def test_api_key_checks():
    print("Testing AI API key loading, normalization, and verification...")

    # 1. Test Base URL Normalization for common providers
    cfg = AppConfig(ai_base_url="openrouter.ai", ai_api_key="sk-test-1234")
    svc = AIService(cfg)
    chat_url = svc._get_chat_url()
    print(f"Normalized 'openrouter.ai' -> '{chat_url}'")
    assert chat_url == "https://openrouter.ai/api/v1/chat/completions"

    cfg_groq = AppConfig(ai_base_url="https://api.groq.com", ai_api_key="gsk-test")
    svc_groq = AIService(cfg_groq)
    assert svc_groq._get_chat_url() == "https://api.groq.com/openai/v1/chat/completions"

    cfg_mimo = AppConfig(ai_base_url="https://api.xiaomimimo.com", ai_api_key="mimo-test")
    svc_mimo = AIService(cfg_mimo)
    assert svc_mimo._get_chat_url() == "https://api.xiaomimimo.com/v1/chat/completions"

    # 2. Test Authorization Headers
    headers = svc._get_headers()
    assert headers["Authorization"] == "Bearer sk-test-1234"
    assert headers["Content-Type"] == "application/json"
    assert "HTTP-Referer" in headers

    # 3. Test Missing API Key reporting
    empty_cfg = AppConfig(ai_api_key="")
    empty_svc = AIService(empty_cfg)
    ok, msg = empty_svc.test_connection()
    assert not ok
    assert "empty" in msg.lower()
    print(f"Empty key handled: '{msg}'")

    # 4. Test Environment Variable Fallback
    orig_key = os.environ.get("OPENAI_API_KEY")
    try:
        test_key = "sk-env-test-key-5678"
        os.environ["OPENAI_API_KEY"] = test_key
        loaded_cfg = AppConfig.load(Path("non_existent_config_for_test.json"))
        assert loaded_cfg.ai_api_key == test_key
        assert loaded_cfg.ai_enabled is True
        print(f"Loaded key from OPENAI_API_KEY environment variable successfully!")
    finally:
        if orig_key is not None:
            os.environ["OPENAI_API_KEY"] = orig_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)

    print("\nAll AI API key check codes PASSED!")


if __name__ == "__main__":
    test_api_key_checks()
