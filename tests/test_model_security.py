import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import AppConfig
from app.core.ai_service import AIService


def test_model_security_guardrails():
    print("=" * 60)
    print("  Testing Flow Model Security & Privacy Guardrails")
    print("=" * 60)

    # 1. Test PII Auto-Redaction
    print("\n[Guardrail 1] Testing PII Auto-Redaction...")
    text_with_cc = "Here is my credit card 4111 2222 3333 4444 and my SSN 123-45-6789 for the invoice."
    redacted = AIService._redact_pii(text_with_cc)
    print(f"Original: {text_with_cc}")
    print(f"Redacted: {redacted}")
    assert "4111" not in redacted
    assert "123-45-6789" not in redacted
    assert "[CARD REDACTED]" in redacted
    assert "[SSN REDACTED]" in redacted
    print("[OK] PII Auto-Redaction validated successfully.")

    # 2. Test Error Message Sanitization (stripping API keys and bearer tokens)
    print("\n[Guardrail 2] Testing Error Message Token Sanitization...")
    error_with_key = "Failed request with sk-live-ab12cd34ef56gh78 and Authorization: Bearer sk-live-secret-9999"
    sanitized = AIService._sanitize_sensitive(error_with_key)
    print(f"Sanitized: {sanitized}")
    assert "sk-live" not in sanitized
    assert "sk-live-ab12cd34ef56gh78" not in sanitized
    assert "[KEY REDACTED]" in sanitized or "Bearer [REDACTED]" in sanitized
    print("[OK] Token sanitization validated successfully.")

    # 3. Test Strict Offline Privacy Mode
    print("\n[Guardrail 3] Testing Strict Offline Mode...")
    offline_cfg = AppConfig(
        strict_offline_mode=True,
        ai_enabled=True,
        ai_api_key="sk-live-dummy-key",
        ai_base_url="https://invalid-host-should-never-be-called.org",
    )
    offline_svc = AIService(offline_cfg)

    # Test connection must be blocked immediately without network attempt
    ok, msg = offline_svc.test_connection()
    assert not ok
    assert "strict offline mode" in msg.lower()
    print(f"Offline Connection Test Blocked: '{msg}'")

    # Polish text must return clean text using local cleaner without network
    voice_input = "um uh hello world this is a test"
    res = offline_svc.polish_text(voice_input)
    print(f"Offline Polish Local Fallback: '{res}'")
    assert "Hello world this is a test" in res
    print("[OK] Strict Offline Mode validated successfully.")

    # 4. Test Prompt Injection Guard Sandbox Format
    print("\n[Guardrail 4] Testing Prompt Injection Guard Sandboxing...")
    cfg_sandbox = AppConfig(prompt_injection_guard=True)
    svc_sandbox = AIService(cfg_sandbox)
    assert "CRITICAL SECURITY GUARDRAILS" in svc_sandbox.SYSTEM_POLISH_PROMPT
    assert "<spoken_dictation>" in svc_sandbox.SYSTEM_POLISH_PROMPT
    print("[OK] Prompt Injection Guard System Prompt & Sandbox validated.")

    print("\n" + "=" * 60)
    print("  ALL MODEL SECURITY & PRIVACY GUARDRAILS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_model_security_guardrails()
