import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.text_cleaner import TextCleaner

def test_cleaner():
    print("Testing Wispr Flow style TextCleaner...")

    # Test 1: Verbal Fillers
    raw1 = "um so basically I wanted to ask uh if you are free tomorrow"
    clean1 = TextCleaner.clean(raw1)
    print(f"Raw:   '{raw1}'")
    print(f"Clean: '{clean1}'")
    assert "um" not in clean1.lower()
    assert "uh" not in clean1.lower()

    # Test 2: Stuttering
    raw2 = "we we need to update the the database"
    clean2 = TextCleaner.clean(raw2)
    print(f"\nRaw:   '{raw2}'")
    print(f"Clean: '{clean2}'")
    assert "we we" not in clean2
    assert "the the" not in clean2

    # Test 3: Capitalization & punctuation
    raw3 = "hello this is a test. i am writing code and it works"
    clean3 = TextCleaner.clean(raw3)
    print(f"\nRaw:   '{raw3}'")
    print(f"Clean: '{clean3}'")
    assert "I am" in clean3
    assert clean3.endswith(".")

    print("\nTextCleaner tests PASSED!")

if __name__ == "__main__":
    test_cleaner()
