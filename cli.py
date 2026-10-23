import sys
import time
from app.config import AppConfig
from app.core.audio_recorder import AudioRecorder
from app.core.stt_engine import STTEngine
from app.core.text_injector import TextInjector
from app.utils.db import HistoryDatabase

def main():
    print("=" * 60)
    print("  Flow STT - Command-Line Dictation Runner")
    print("=" * 60)
    
    config = AppConfig.load()
    engine = STTEngine(model_size=config.model_size, device=config.device, compute_type=config.compute_type)
    
    print(f"Loading local Whisper model: '{config.model_size}'...")
    engine.load_model()
    
    recorder = AudioRecorder(sample_rate=config.sample_rate)
    injector = TextInjector()
    db = HistoryDatabase()
    
    print("\nReady! Instructions:")
    print("  - Press [ENTER] to start recording.")
    print("  - Press [ENTER] again to stop recording and transcribe.")
    print("  - Type 'exit' or press Ctrl+C to quit.\n")
    
    try:
        while True:
            cmd = input("Press [ENTER] to record (or 'q' to quit): ").strip().lower()
            if cmd in ("q", "exit", "quit"):
                break
                
            print("\n🎙️  Recording... Speak now! (Press [ENTER] to stop)")
            t0 = time.time()
            recorder.start_recording()
            
            input() # wait for Enter
            
            duration = time.time() - t0
            audio = recorder.stop_recording()
            print(f"Recorded {duration:.2f}s of audio. Transcribing...")
            
            t1 = time.time()
            text = engine.transcribe_audio(audio)
            elapsed = time.time() - t1
            
            if text:
                print(f"\n[TRANSCRIPT] ({elapsed:.2f}s):")
                print(f"  \"{text}\"\n")
                db.save_record(text=text, duration_seconds=duration, model_used=config.model_size)
                
                # Copy to clipboard
                import pyperclip
                pyperclip.copy(text)
                print("  -> Copied to clipboard!")
            else:
                print("\n[TRANSCRIPT]: (No speech detected)\n")
                
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
