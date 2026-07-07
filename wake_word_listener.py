import speech_recognition as sr
import requests
import time
import os
import numpy as np
import threading
import sounddevice as sd

API_URL = "http://127.0.0.1:8000/api/remote_command"
INTERRUPT_URL = "http://127.0.0.1:8000/api/interrupt"

# --- CONFIGURATION ---
WAKE_WORDS = ["ember", "amber", "emmer", "member"]
ACTIVE_WINDOW_SECONDS = 15
CUSTOM_MODEL_PATH = "hey_ember.onnx" # If you train a custom openWakeWord model, place it here

# --- STATE ---
active_mode = False
last_wake_time = 0

# --- OPENWAKEWORD INITIALIZATION ---
oww_model = None
try:
    import openwakeword
    from openwakeword.model import Model
    if os.path.exists(CUSTOM_MODEL_PATH):
        print(f"Loading custom openWakeWord model: {CUSTOM_MODEL_PATH}")
        oww_model = Model(wakeword_models=[CUSTOM_MODEL_PATH], inference_framework="onnx")
    else:
        print(f"⚠️ Custom openWakeWord model '{CUSTOM_MODEL_PATH}' not found.")
        print("Fallback: Using Google STT text-matching for wake words.")
        print("To use offline openWakeWord, train a model using the openWakeWord Colab notebook and place it in this directory.")
except ImportError:
    print("⚠️ openwakeword not installed. Run 'pip install openwakeword' if you want offline wake word detection.")

def trigger_interrupt():
    """Immediately stops Ember from speaking so you can barge in."""
    try:
        requests.post(INTERRUPT_URL, timeout=2)
    except:
        pass

def handle_command(command, is_wake=False):
    global active_mode, last_wake_time
    
    if not command:
        if is_wake:
            command = "Hey Ember."
        else:
            return
            
    print(f"🚀 Sending command to API: {command}")
    
    # We are barging in or starting a command, so interrupt any current TTS!
    trigger_interrupt()
    
    try:
        requests.post(API_URL, json={"text": command}, timeout=5)
        print("✅ Sent successfully!")
        
        # Update active listening state
        active_mode = True
        last_wake_time = time.time()
    except Exception as e:
        print(f"❌ Failed to send command to API: {e}")

def listen_for_wake_word():
    global active_mode, last_wake_time
    
    # Start the local real-time VAD barge-in thread from agents.vad_detector
    try:
        from agents.vad_detector import run_vad
        t = threading.Thread(target=run_vad, daemon=True)
        t.start()
    except Exception as e:
        print(f"⚠️ Failed to start VAD thread: {e}")
    
    recognizer = sr.Recognizer()
    
    # We need a slightly higher energy threshold if relying on STT, but sr auto-adjusts.
    try:
        microphone = sr.Microphone(sample_rate=16000)
        print("🎤 Iron Man Module Active: Adjusting for ambient noise...")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=2)
    except OSError as e:
        print(f"⚠️ Microphone Error: {e}")
        print("⚠️ No default microphone detected! Iron Man Agent is paused.")
        while True:
            time.sleep(60)
            
    print("👂 Listening for wake word ('Hey Ember')...")

    def callback(recognizer, audio):
        global active_mode, last_wake_time
        
        # 1. OpenWakeWord Offline Detection (If Model Available)
        wake_detected_offline = False
        if oww_model:
            # speech_recognition provides audio data in raw bytes. 
            # Convert to numpy array for openwakeword (16khz, 16-bit PCM)
            audio_data = np.frombuffer(audio.frame_data, dtype=np.int16)
            
            # Feed chunks to openwakeword
            chunk_size = 1280
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                if len(chunk) == chunk_size:
                    prediction = oww_model.predict(chunk)
                    # prediction is a dict: {'hey_ember': 0.05}
                    for model_name, score in prediction.items():
                        if score > 0.5: # Threshold
                            wake_detected_offline = True
                            break
                if wake_detected_offline:
                    break
            
            if wake_detected_offline:
                print("🔥 [OpenWakeWord] Offline Wake Word Detected!")
                trigger_interrupt()
                # We reset the openWakeWord state so it doesn't get stuck
                oww_model.reset()
        
        # Check if we are in active listening window
        if active_mode and (time.time() - last_wake_time > ACTIVE_WINDOW_SECONDS):
            active_mode = False
            print("💤 Active listening window expired. Going back to sleep.")

        try:
            # 2. Transcribe the audio chunk
            # We skip this if we didn't hear a wake word AND we aren't in active mode,
            # BUT if we don't have an offline model, we MUST transcribe to check for the wake word.
            if not wake_detected_offline and not active_mode and oww_model:
                # Save API calls: we have an offline model, it didn't trigger, and we aren't active.
                return
                
            text = recognizer.recognize_google(audio).lower()
            
            if wake_detected_offline:
                # The model already triggered, just send whatever text we captured.
                # Strip the wake word if STT also picked it up
                command = text
                for w in WAKE_WORDS:
                    if command.startswith(w):
                        command = command[len(w):].strip()
                    elif command.startswith(f"hey {w}"):
                        command = command[len(f"hey {w}"):].strip()
                handle_command(command, is_wake=True)
                
            elif active_mode:
                # We are active! Any speech is a command.
                print(f"🎙️ [Active Mode] Heard: '{text}'")
                handle_command(text, is_wake=False)
                
            else:
                # 3. Fallback text-based wake word check (if no offline model or it missed)
                # Stricter check: must START with the wake word (or "hey <wake_word>")
                is_wake = False
                command = text
                
                for w in WAKE_WORDS:
                    if text.startswith(w):
                        is_wake = True
                        command = text[len(w):].strip()
                        break
                    elif text.startswith(f"hey {w}"):
                        is_wake = True
                        command = text[len(f"hey {w}"):].strip()
                        break
                        
                if is_wake:
                    print(f"🔥 [STT Fallback] Wake Word Detected! You said: '{text}'")
                    handle_command(command, is_wake=True)

        except sr.UnknownValueError:
            pass # Incomprehensible audio
        except sr.RequestError as e:
            print(f"⚠️ Could not request results from Google Speech Recognition service; {e}")

    # Listen in the background silently
    # phrase_time_limit prevents it from recording forever if there's continuous background noise
    stop_listening = recognizer.listen_in_background(microphone, callback, phrase_time_limit=10)

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping wake word listener...")
        stop_listening(wait_for_stop=False)

if __name__ == "__main__":
    listen_for_wake_word()
