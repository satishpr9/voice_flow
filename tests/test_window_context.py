import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.window_context import WindowContextDetector, WindowContext

def test_categorization():
    print("Testing WindowContextDetector categorization...")

    ctx_code = WindowContextDetector._categorize("code.exe", "main.py - Visual Studio Code")
    assert ctx_code.category == "code"
    assert "Code Editor" in ctx_code.prompt_guidance

    ctx_slack = WindowContextDetector._categorize("slack.exe", "#general - Slack")
    assert ctx_slack.category == "chat"
    assert "Messaging / Chat" in ctx_slack.prompt_guidance

    ctx_gmail = WindowContextDetector._categorize("chrome.exe", "Inbox (2) - user@gmail.com - Google Chrome")
    assert ctx_gmail.category == "email"
    assert "email" in ctx_gmail.prompt_guidance.lower()

    ctx_notion = WindowContextDetector._categorize("notion.exe", "Project Roadmap - Notion")
    assert ctx_notion.category == "docs"

    live_ctx = WindowContextDetector.get_active_context()
    print(f"Live context: app='{live_ctx.app_name}', category='{live_ctx.category}'")
    print("WindowContextDetector tests PASSED!")

if __name__ == "__main__":
    test_categorization()
