import io
import time
import base64
import requests
import numpy as np
import scipy.io.wavfile as wavfile
from typing import Tuple, Optional

from app.config import AppConfig
from app.core.text_cleaner import TextCleaner


class AIService:
    """Manages AI cloud inference for Wispr Flow-style text polish and omni-audio dictation.
    Supports OpenRouter, Xiaomi MiMo API, Groq, or any OpenAI-compatible API gateway.
    Features instant fallback to local regex TextCleaner if offline or on network failure.
    """

    SYSTEM_POLISH_PROMPT = (
        "You are an expert spoken-dictation editor (Wispr Flow style).\n"
        "Transform raw transcribed speech into polished, natural written text:\n"
        "- Eliminate verbal hesitations and fillers (um, uh, like, you know, sort of, basically).\n"
        "- Remove stutter repetitions and fix mid-sentence self-corrections cleanly.\n"
        "- Apply proper punctuation, capitalization, paragraphs, and list formatting (markdown bullets or numbered lists) if the speaker was enumerating items.\n"
        "- Preserve the speaker's original meaning, vocabulary, and tone.\n"
        "- Output ONLY the polished text. Do not add quotes, introductory remarks, conversational replies, or explanations."
    )

    SYSTEM_OMNI_PROMPT = (
        "You are an expert voice-to-text transcription engine (Wispr Flow style).\n"
        "Listen to the audio and transcribe it into polished, clean written text:\n"
        "- Remove verbal fillers (um, uh, you know) and stutter repetitions.\n"
        "- Add natural punctuation, capitalization, and formatting.\n"
        "- Output ONLY the final transcribed text without any comments or quotes."
    )

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load()

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def _get_headers(self) -> dict:
        api_key = self.config.ai_api_key.strip() if self.config.ai_api_key else ""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        # OpenRouter optional identification headers
        if "openrouter.ai" in self.config.ai_base_url.lower():
            headers["HTTP-Referer"] = "https://github.com/flow-stt"
            headers["X-Title"] = "Voice Flow STT"
        return headers

    def _get_chat_url(self) -> str:
        base = self.config.ai_base_url.strip().rstrip("/")
        if not base.endswith("/chat/completions"):
            return f"{base}/chat/completions"
        return base

    def polish_text(self, raw_text: str) -> str:
        """Transforms raw transcribed text into polished prose via AI LLM.
        Falls back seamlessly to local regex TextCleaner on failure.
        """
        if not raw_text or not raw_text.strip():
            return ""

        # If AI polish is disabled or no key provided, use local regex cleaner immediately
        if not self.config.ai_enabled or not self.config.ai_api_key.strip():
            return TextCleaner.clean(raw_text)

        t0 = time.time()
        try:
            payload = {
                "model": self.config.ai_model.strip() or "xiaomi/mimo-v2.6-flash",
                "messages": [
                    {"role": "system", "content": self.SYSTEM_POLISH_PROMPT},
                    {"role": "user", "content": raw_text.strip()},
                ],
                "temperature": 0.2,
                "max_tokens": 800,
            }

            resp = requests.post(
                self._get_chat_url(),
                headers=self._get_headers(),
                json=payload,
                timeout=3.5,
            )

            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                # Strip wrapping markdown code blocks if the model generated them
                if content.startswith("```") and content.endswith("```"):
                    lines = content.splitlines()
                    if len(lines) >= 3:
                        content = "\n".join(lines[1:-1]).strip()

                print(f"[AIService] Polished with '{self.config.ai_model}' in {time.time() - t0:.2f}s")
                return content
            else:
                print(f"[AIService] API returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[AIService] Request failed ({e}). Falling back to local cleaner.")

        # Graceful fallback to regex
        return TextCleaner.clean(raw_text)

    def transcribe_omni_audio(self, audio_data: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
        """Direct audio transcription using an Omni multimodal model (e.g. qwen/qwen3.8-omni-flash).
        Returns None if omni call fails or model doesn't support audio payload.
        """
        if not self.config.ai_enabled or not self.config.ai_api_key.strip():
            return None

        t0 = time.time()
        try:
            # Convert float32 numpy audio buffer [-1.0, 1.0] to int16 WAV in memory
            int16_audio = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            wav_io = io.BytesIO()
            wavfile.write(wav_io, sample_rate, int16_audio)
            b64_audio = base64.b64encode(wav_io.getvalue()).decode("utf-8")

            payload = {
                "model": self.config.ai_model.strip() or "qwen/qwen3.8-omni-flash",
                "messages": [
                    {"role": "system", "content": self.SYSTEM_OMNI_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": b64_audio,
                                    "format": "wav",
                                },
                            },
                            {
                                "type": "text",
                                "text": "Please transcribe this audio following the guidelines.",
                            },
                        ],
                    },
                ],
                "temperature": 0.1,
                "max_tokens": 1024,
            }

            resp = requests.post(
                self._get_chat_url(),
                headers=self._get_headers(),
                json=payload,
                timeout=6.0,
            )

            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                print(f"[AIService] Omni transcribed with '{self.config.ai_model}' in {time.time() - t0:.2f}s")
                return content
            else:
                print(f"[AIService] Omni API returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[AIService] Omni transcription error: {e}")

        return None

    def test_connection(self) -> Tuple[bool, str]:
        """Tests the configured AI API endpoint and returns (success, status_message)."""
        if not self.config.ai_api_key.strip():
            return False, "API Key is empty. Please enter your API key."

        t0 = time.time()
        try:
            payload = {
                "model": self.config.ai_model.strip() or "xiaomi/mimo-v2.6-flash",
                "messages": [
                    {"role": "system", "content": "You are a test assistant. Reply with 'OK'."},
                    {"role": "user", "content": "ping"},
                ],
                "max_tokens": 10,
                "temperature": 0.0,
            }

            resp = requests.post(
                self._get_chat_url(),
                headers=self._get_headers(),
                json=payload,
                timeout=4.0,
            )

            latency = time.time() - t0
            if resp.status_code == 200:
                return True, f"Connection successful! Latency: {latency:.2f}s (Status 200 OK)"
            else:
                err_snippet = resp.text[:150]
                return False, f"API Error (HTTP {resp.status_code}): {err_snippet}"
        except requests.exceptions.Timeout:
            return False, "Connection timed out after 4 seconds. Check your network or base URL."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
