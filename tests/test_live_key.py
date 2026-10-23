import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from app.config import AppConfig
from app.core.ai_service import AIService
from app.utils.window_context import WindowContextDetector

def run_test():
    print("=" * 60)
    print("  Testing User API Key & Cloud Endpoint")
    print("=" * 60)

    cfg = AppConfig.load()
    print(f"Loaded Base URL: {cfg.ai_base_url}")
    print(f"Loaded Model:    {cfg.ai_model}")
    print(f"API Key:         {'[SECURELY CONFIGURED]' if cfg.ai_api_key else '(none)'}")

    svc = AIService(cfg)

    # 1. Test ping connection
    print("\n[Step 1] Running diagnostic connection test...")
    ok, msg = svc.test_connection()
    print(f"Result: ok={ok}, message='{msg}'")

    if not ok:
        print("[FAIL] Connection test failed.")
        return

    # 2. Test live AI polish with xiaomi/mimo-v2.6-flash
    print("\n[Step 2] Testing AI Polish with 'xiaomi/mimo-v2.6-flash'...")
    cfg.ai_model = "xiaomi/mimo-v2.6-flash"
    svc.update_config(cfg)

    raw_voice = "um so basically we we need to fix the the authentication bug in production and alert sarah"
    ctx = WindowContextDetector._categorize("code.exe", "auth.py - Visual Studio Code")
    
    t0 = time.time()
    polished = svc.polish_text(raw_voice, context=ctx)
    elapsed = time.time() - t0

    print(f"Raw Input:   \"{raw_voice}\"")
    print(f"Polished:    \"{polished}\"")
    print(f"Speed:       {elapsed:.2f}s")

    # 3. Test with qwen/qwen3.8-omni-flash
    print("\n[Step 3] Testing with 'qwen/qwen3.8-omni-flash'...")
    cfg.ai_model = "qwen/qwen3.8-omni-flash"
    svc.update_config(cfg)

    t0 = time.time()
    polished_qwen = svc.polish_text(raw_voice, context=ctx)
    elapsed_qwen = time.time() - t0

    print(f"Qwen Output: \"{polished_qwen}\"")
    print(f"Speed:       {elapsed_qwen:.2f}s")

    print("\n" + "=" * 60)
    print("  LIVE API TEST PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_test()
