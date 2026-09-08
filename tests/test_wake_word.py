#!/usr/bin/env python3
"""
Test wake word detection.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_wake_word():
    """Test wake word model loading and basic detection."""
    from senses.wake_word_detector import WakeWordDetector
    from config import Config
    
    print("Testing wake word detector...\n")
    
    # Test model loading
    try:
        config = Config.load()
        detector = WakeWordDetector(
            model_path=config.wake_word_model,
            threshold=config.wake_word_threshold,
            sample_rate=config.target_sample_rate,
            mic_sample_rate=config.mic_sample_rate,
            mic_name=config.mic_name,
        )
        print("✓ Wake word model loaded successfully")
    except FileNotFoundError as e:
        print(f"✗ Model not found: {e}")
        return False
    except Exception as e:
        print(f"✗ Error loading model: {e}")
        return False
    
    # Test listening (interactive)
    print("\nStarting interactive test...")
    print("Speak the phrase configured for this legacy detector.")
    print("Press Ctrl+C to stop.\n")
    
    detected = False
    
    def on_wake_word():
        nonlocal detected
        detected = True
        print("✓ Wake word detected!")
    
    try:
        detector.start(callback=on_wake_word)
        
        import time
        timeout = 30
        start = time.time()
        
        while not detected and (time.time() - start) < timeout:
            time.sleep(0.5)
        
        if not detected:
            print(f"No detection in {timeout} seconds")
        
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        detector.stop()
    
    return detected


if __name__ == "__main__":
    success = test_wake_word()
    sys.exit(0 if success else 1)
