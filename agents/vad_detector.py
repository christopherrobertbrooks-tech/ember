import os
import sys
import time
import numpy as np
import requests
import sounddevice as sd

def load_config():
    import json
    CONFIG_PATH = "ember_config.json"
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def trigger_interrupt():
    """Immediately stops Ember from speaking so you can barge in."""
    config = load_config()
    # Find host IP from config if running on client
    chroma_url = config.get("chroma_server_url", "http://127.0.0.1:8001")
    try:
        host_ip = chroma_url.split("://")[1].split(":")[0]
    except Exception:
        host_ip = "127.0.0.1"
        
    url = f"http://{host_ip}:8000/api/interrupt"
    try:
        requests.post(url, timeout=2)
        print("[VAD] Speech detected. Sent interrupt!")
    except Exception as e:
        print(f"[VAD] Failed to send interrupt: {e}")

def run_vad():
    fs = 16000
    print("[VAD] Calibrating ambient noise for barge-in...")
    try:
        recording = sd.rec(int(1.0 * fs), samplerate=fs, channels=1, dtype='int16')
        sd.wait()
        ambient_rms = np.sqrt(np.mean(recording**2))
        threshold = max(ambient_rms * 2.5, 120.0)
    except Exception as e:
        print(f"⚠️ [VAD] Calibration failed: {e}. Using static threshold.")
        threshold = 200.0
        
    print(f"⚡ [VAD] Barge-in Active. Threshold = {threshold:.1f}")
    
    in_speech = False
    
    def callback(indata, frames, time_info, status):
        nonlocal in_speech
        rms = np.sqrt(np.mean(indata**2))
        
        if rms > threshold:
            if not in_speech:
                in_speech = True
                trigger_interrupt()
        else:
            in_speech = False

    try:
        with sd.InputStream(samplerate=fs, channels=1, dtype='int16', blocksize=1024, callback=callback):
            while True:
                time.sleep(0.5)
    except Exception as e:
        print(f"⚠️ [VAD] SoundDevice stream failed: {e}")

if __name__ == "__main__":
    try:
        run_vad()
    except KeyboardInterrupt:
        print("\n[*] VAD detector stopped by user.")
        sys.exit(0)
