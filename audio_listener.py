"""
Audio Listener with Real-time Topic Detection.
This script listens to microphone input and detects topics dynamically via the
UnifiedIntentEngine (semantic Self-Adaptive Understanding Layer, no keywords).
"""

import sys
import os
import time
import json
import threading
from collections import deque

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Single source of truth for topic/intent classification (semantic, no keywords)
from backend.nlp.unified_intent_engine import UnifiedIntentEngine

# Try to import RealtimeSTT (optional - for better performance)
try:
    from RealtimeSTT import AudioToTextRecorder
    USE_REALTIME_STT = True
    print("✅ Using RealtimeSTT for speech recognition")
except ImportError:
    USE_REALTIME_STT = False
    print("⚠️ RealtimeSTT not installed. Using Web Speech API fallback.")
    print("   Install with: pip install RealtimeSTT")

# Try to import speech_recognition as fallback
try:
    import speech_recognition as sr
    USE_SPEECH_RECOGNITION = True
except ImportError:
    USE_SPEECH_RECOGNITION = False
    print("⚠️ speech_recognition not installed. Install with: pip install SpeechRecognition")


class AudioTopicListener:
    """
    Real-time audio listener that detects topics via the UnifiedIntentEngine
    (semantic Self-Adaptive Understanding Layer).
    """
    
    def __init__(self):
        self.analyzer = UnifiedIntentEngine.instance()
        self.is_listening = False
        self.current_topic = {"name": "Waiting for speech...", "confidence": 0, "keywords": []}
        self.text_buffer = deque(maxlen=50)
        self.last_topic_update = time.time()
        self.topic_update_interval = 5  # seconds
        
    def update_topic(self, text):
        """Update topic analysis with new text"""
        if not text or len(text) < 15:
            return
        
        self.text_buffer.append(text)
        current_time = time.time()
        
        # Analyze every 5 seconds or when buffer is full
        if len(self.text_buffer) >= 5 or (current_time - self.last_topic_update) > self.topic_update_interval:
            self.last_topic_update = current_time
            documents = list(self.text_buffer)
            combined = " ".join(documents)
            
            try:
                result = self.analyzer.detect_topic(combined)
                if result and result.get('confidence', 0) > 30:
                    self.current_topic = result
                    self.display_topic()
            except Exception as e:
                print(f"❌ Topic analysis error: {e}")
    
    def display_topic(self):
        """Display the current detected topic"""
        confidence = self.current_topic.get('confidence', 0)
        name = self.current_topic.get('name', 'Unknown')
        keywords = self.current_topic.get('keywords', [])
        
        # Clear line and print
        bar_length = min(50, confidence // 2)
        bar = "█" * bar_length + "░" * (50 - bar_length)
        
        print(f"\r🎯 Topic: {name[:40]:<40} | Confidence: {confidence:3}% {bar}", end="")
        
        if keywords:
            print(f"\n   📝 Keywords: {', '.join(keywords[:5])}")
    
    def listen_with_realtimestt(self):
        """Listen using RealtimeSTT library"""
        if not USE_REALTIME_STT:
            print("❌ RealtimeSTT not available")
            return
        
        def on_text(text):
            """Callback when text is recognized"""
            if text and len(text) > 5:
                print(f"\n🎤 Heard: {text[:80]}...")
                self.update_topic(text)
        
        try:
            recorder = AudioToTextRecorder(
                language='de',  # German
                silero_sensitivity=0.5,
                webrtc_sensitivity=0.5,
                post_speech_silence_duration=0.6,
                on_recording_start=lambda: print("\n🎤 Recording started..."),
                on_recording_stop=lambda: print("\n⏸️ Processing...")
            )
            
            print("\n🎤 Listening with RealtimeSTT... Speak in German!")
            print("Press Ctrl+C to stop\n")
            
            while self.is_listening:
                text = recorder.text()
                if text:
                    on_text(text)
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\n👋 Stopped listening.")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def listen_with_speech_recognition(self):
        """Listen using speech_recognition library (fallback)"""
        if not USE_SPEECH_RECOGNITION:
            print("❌ SpeechRecognition not available")
            return
        
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        
        print("\n🎤 Adjusting for ambient noise...")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=2)
        
        print("🎤 Listening with SpeechRecognition... Speak in German!")
        print("Press Ctrl+C to stop\n")
        
        try:
            while self.is_listening:
                with microphone as source:
                    print("👂 Listening...", end="\r")
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                try:
                    text = recognizer.recognize_google(audio, language="de-DE")
                    if text:
                        print(f"\n🎤 Heard: {text[:80]}...")
                        self.update_topic(text)
                except sr.UnknownValueError:
                    pass  # No speech detected
                except sr.RequestError as e:
                    print(f"\n⚠️ Recognition error: {e}")
                    
        except KeyboardInterrupt:
            print("\n\n👋 Stopped listening.")
    
    def start(self, method='auto'):
        """Start listening with specified method"""
        self.is_listening = True
        
        print("=" * 60)
        print("🎙️ AUDIO TOPIC DETECTOR")
        print("=" * 60)
        print(f"Topic update interval: {self.topic_update_interval} seconds")
        print()
        
        if method == 'realtime' and USE_REALTIME_STT:
            self.listen_with_realtimestt()
        elif method == 'speech' and USE_SPEECH_RECOGNITION:
            self.listen_with_speech_recognition()
        elif method == 'auto':
            if USE_REALTIME_STT:
                self.listen_with_realtimestt()
            elif USE_SPEECH_RECOGNITION:
                self.listen_with_speech_recognition()
            else:
                print("❌ No speech recognition library available")
                print("   Install with: pip install RealtimeSTT SpeechRecognition")
        else:
            print(f"❌ Method '{method}' not available")
    
    def stop(self):
        """Stop listening"""
        self.is_listening = False
        print("\n✅ Stopped audio listener")


def test_with_text():
    """Test topic detection with sample text (no microphone needed)"""
    print("=" * 60)
    print("📝 TESTING TOPIC DETECTION WITH SAMPLE TEXT")
    print("=" * 60)
    
    analyzer = UnifiedIntentEngine.instance()
    
    test_texts = [
        "Today we will learn about sorting algorithms. Bubble sort works by repeatedly swapping adjacent elements if they are in the wrong order.",
        "Quick sort uses a divide and conquer approach. It selects a pivot element and partitions the array around it.",
        "In databases, we use SQL to query data. SELECT, INSERT, UPDATE, and DELETE are the main operations.",
        "We need to understand primary keys and foreign keys to establish relationships between tables.",
        "Web development includes HTML for structure, CSS for styling, and JavaScript for interactivity."
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n📄 Sample {i}: {text[:60]}...")
        result = analyzer.detect_topic(text)
        
        if result:
            print(f"   🎯 Topic: {result.get('name', 'Unknown')}")
            print(f"   📊 Confidence: {result.get('confidence', 0)}%")
            print(f"   🔑 Keywords: {', '.join(result.get('keywords', [])[:5])}")
        print("-" * 40)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time Audio Topic Detector')
    parser.add_argument('--test', action='store_true', help='Run test with sample text (no microphone)')
    parser.add_argument('--method', choices=['auto', 'realtime', 'speech'], default='auto',
                        help='Speech recognition method')
    
    args = parser.parse_args()
    
    if args.test:
        test_with_text()
    else:
        listener = AudioTopicListener()
        try:
            listener.start(method=args.method)
        except KeyboardInterrupt:
            listener.stop()