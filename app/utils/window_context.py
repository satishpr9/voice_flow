import ctypes
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowContext:
    app_name: str           # e.g. "VS Code", "Slack", "Gmail", "Notion", "General"
    category: str           # "code", "chat", "email", "docs", "general"
    window_title: str       # Full window title
    process_exe: str        # e.g. "code.exe", "slack.exe"
    prompt_guidance: str    # Contextual instruction for AI LLM polish


class WindowContextDetector:
    """Detects active foreground window and application context on Windows."""

    CODE_EXES = {
        "code.exe": "VS Code",
        "cursor.exe": "Cursor",
        "pycharm64.exe": "PyCharm",
        "idea64.exe": "IntelliJ",
        "sublime_text.exe": "Sublime Text",
        "windowsterminal.exe": "Terminal",
        "powershell.exe": "PowerShell",
        "cmd.exe": "Command Prompt",
        "devenv.exe": "Visual Studio",
        "notepad++.exe": "Notepad++",
    }

    CHAT_EXES = {
        "slack.exe": "Slack",
        "discord.exe": "Discord",
        "whatsapp.exe": "WhatsApp",
        "telegram.exe": "Telegram",
        "teams.exe": "Microsoft Teams",
        "signal.exe": "Signal",
        "messenger.exe": "Messenger",
    }

    DOCS_EXES = {
        "winword.exe": "Microsoft Word",
        "word.exe": "Microsoft Word",
        "notion.exe": "Notion",
        "obsidian.exe": "Obsidian",
        "onenote.exe": "OneNote",
        "wordpad.exe": "WordPad",
    }

    EMAIL_EXES = {
        "outlook.exe": "Outlook",
        "thunderbird.exe": "Thunderbird",
    }

    @classmethod
    def get_active_context(cls) -> WindowContext:
        """Retrieves context of the currently focused foreground window."""
        title = ""
        exe_name = ""

        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            hwnd = user32.GetForegroundWindow()
            if hwnd:
                # 1. Get Window Title
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf_title = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf_title, length + 1)
                    title = buf_title.value

                # 2. Get Process Executable Name
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value:
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                    if h_proc:
                        buf_path = ctypes.create_unicode_buffer(512)
                        size = ctypes.c_ulong(512)
                        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf_path, ctypes.byref(size)):
                            exe_name = Path(buf_path.value).name.lower()
                        kernel32.CloseHandle(h_proc)
        except Exception:
            pass

        return cls._categorize(exe_name, title)

    @classmethod
    def _categorize(cls, exe_name: str, title: str) -> WindowContext:
        lower_title = title.lower()

        # Check Code Editors / Terminals
        if exe_name in cls.CODE_EXES:
            app = cls.CODE_EXES[exe_name]
            return WindowContext(
                app_name=app,
                category="code",
                window_title=title,
                process_exe=exe_name,
                prompt_guidance=(
                    f"The user is dictating into {app} (Code Editor / Terminal). "
                    "Retain programming jargon, camelCase/snake_case variable names, markdown code backticks, "
                    "or shell commands if the user is dictating code."
                ),
            )

        # Check Chat Apps
        if exe_name in cls.CHAT_EXES:
            app = cls.CHAT_EXES[exe_name]
            return WindowContext(
                app_name=app,
                category="chat",
                window_title=title,
                process_exe=exe_name,
                prompt_guidance=(
                    f"The user is dictating into {app} (Messaging / Chat). "
                    "Keep the tone natural, concise, conversational, and direct. "
                    "Avoid overly formal email greetings unless explicitly spoken."
                ),
            )

        # Check Native Email Clients or Browser Webmail
        if exe_name in cls.EMAIL_EXES or "gmail" in lower_title or "outlook" in lower_title or "mail" in lower_title:
            app = "Email"
            return WindowContext(
                app_name=app,
                category="email",
                window_title=title,
                process_exe=exe_name,
                prompt_guidance=(
                    "The user is dictating an email. Format with proper paragraph structure, polite professional tone, "
                    "and clear sentence flow."
                ),
            )

        # Check Document / Note Taking Apps or Web Docs
        if exe_name in cls.DOCS_EXES or "notion" in lower_title or "docs.google" in lower_title or "notes" in lower_title:
            app = cls.DOCS_EXES.get(exe_name, "Notes / Docs")
            return WindowContext(
                app_name=app,
                category="docs",
                window_title=title,
                process_exe=exe_name,
                prompt_guidance=(
                    f"The user is dictating into {app} (Document / Notes). "
                    "Structure thoughts clearly, using clean paragraph breaks and bullet lists if items are being enumerated."
                ),
            )

        # General Default
        app_label = title[:24] if title else "Active Window"
        return WindowContext(
            app_name=app_label,
            category="general",
            window_title=title,
            process_exe=exe_name,
            prompt_guidance=(
                "The user is dictating general text. Produce crisp, natural prose with standard punctuation and capitalization."
            ),
        )
