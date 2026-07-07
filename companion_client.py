import customtkinter as ctk
import threading
import requests
import time
import sounddevice as sd
import soundfile as sf
import numpy as np
import io
import json
import base64
import websocket
from PIL import Image
from customtkinter import filedialog

API_URL = "http://100.100.150.74:8000"
API_KEY = "ember-secret-key-123"
HEADERS = {"X-API-Key": API_KEY}

BOT_NAME = "Ember Client"

ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("blue")

class AICompanionClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{BOT_NAME} - API Client")
        self.geometry("1000x700")
        self.configure(fg_color="#0A0A0A")
        
        self.is_recording = False
        self.audio_data = []
        self.attached_image_path = None
        self.wake_word_enabled = False
        self.wake_thread_active = False
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        import queue
        self.playback_queue = queue.Queue()
        threading.Thread(target=self.audio_player_worker, daemon=True).start()
        self.ws = None
        
        self.build_ui()
        self.append_to_chat("System", "Client UI Initialized. Connecting to API...\n")
        self.connect_ws()

    def audio_player_worker(self):
        while True:
            audio_bytes = self.playback_queue.get()
            try:
                buf = io.BytesIO(audio_bytes)
                audio_data, fs = sf.read(buf)
                sd.play(audio_data, samplerate=fs)
                sd.wait()
            except Exception as e:
                pass
            finally:
                self.playback_queue.task_done()

    def connect_ws(self):
        def run_ws():
            ws_url = API_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
            self.ws = websocket.WebSocketApp(ws_url,
                                             on_open=self.on_ws_open,
                                             on_message=self.on_ws_message,
                                             on_error=self.on_ws_error,
                                             on_close=self.on_ws_close)
            self.ws.run_forever()
        threading.Thread(target=run_ws, daemon=True).start()

    def on_ws_open(self, ws):
        ws.send(json.dumps({"api_key": API_KEY}))
        self.after(0, self.append_to_chat, "System", "Connected to Brain.")

    def on_ws_close(self, ws, close_status_code, close_msg):
        self.after(0, self.append_to_chat, "System", "Disconnected from Brain. Reconnecting in 5s...")
        self.after(5000, self.connect_ws)

    def on_ws_error(self, ws, error):
        pass

    def on_ws_message(self, ws, message):
        data = json.loads(message)
        msg_type = data.get("type")
        
        if msg_type == "text":
            def _update_chunk(c=data["chunk"]):
                self.chat_history.configure(state="normal")
                self.chat_history.insert("end", c)
                self.chat_history.configure(state="disabled")
                self.chat_history.see("end")
            self.after(0, _update_chunk)
        elif msg_type == "audio":
            audio_bytes = base64.b64decode(data["data"])
            self.playback_queue.put(audio_bytes)
        elif msg_type == "stream_start":
            def _start_msg():
                self.chat_history.configure(state="normal")
                self.chat_history.insert("end", "\nEmber: ")
                self.chat_history.configure(state="disabled")
                self.chat_history.see("end")
            self.after(0, _start_msg)
        elif msg_type == "stream_done":
            def _end_msg():
                self.chat_history.configure(state="normal")
                self.chat_history.insert("end", "\n")
                self.chat_history.configure(state="disabled")
                if self.wake_word_enabled:
                    def _wait_and_resume():
                        self.playback_queue.join()
                        self.after(500, self.resume_listening)
                    threading.Thread(target=_wait_and_resume, daemon=True).start()
            self.after(0, _end_msg)
        elif msg_type == "error":
            self.after(0, self.append_to_chat, "System Error", data["message"])
        elif msg_type == "interrupt":
            sd.stop()
            with self.playback_queue.mutex:
                self.playback_queue.queue.clear()
            self.after(0, self.append_to_chat, "System", "Audio interrupted.")
        elif msg_type == "ui_action":
            action_data = data.get("data", {})
            action = action_data.get("action")
            
            if action == "open_browser":
                import webbrowser
                url = action_data.get("url")
                if url:
                    webbrowser.open(url)
                    self.after(0, self.append_to_chat, "System", f"Opening browser: {url}")
            elif action == "launch_app":
                app_id = action_data.get("app_id")
                name = action_data.get("name")
                import subprocess
                subprocess.Popen(f"explorer.exe shell:AppsFolder\\{app_id}", shell=True)
                self.after(0, self.append_to_chat, "System", f"Launched App: {name}")
            elif action == "mouse_move":
                try:
                    import pyautogui
                    x, y = int(action_data.get("x", 0)), int(action_data.get("y", 0))
                    pyautogui.moveTo(x, y)
                except Exception as e:
                    print(f"Mouse move error: {e}")
            elif action == "mouse_click":
                try:
                    import pyautogui
                    button = action_data.get("button", "left")
                    pyautogui.click(button=button)
                except Exception as e:
                    print(f"Mouse click error: {e}")
            elif action == "keyboard_type":
                try:
                    import pyautogui
                    text = action_data.get("text", "")
                    pyautogui.write(text, interval=0.01)
                except Exception as e:
                    print(f"Keyboard type error: {e}")
            elif action == "take_screenshot":
                def _do_screenshot():
                    try:
                        from PIL import ImageGrab
                        import requests
                        import io
                        
                        img = ImageGrab.grab()
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        buf.seek(0)
                        
                        # Upload to Host API
                        res = requests.post(
                            f"{API_URL}/api/client_screenshot",
                            headers={"X-API-Key": API_KEY},
                            files={"file": ("screenshot.png", buf, "image/png")},
                            timeout=10
                        )
                        if res.status_code == 200:
                            self.after(0, self.append_to_chat, "System", "Sent screenshot to Host.")
                    except Exception as e:
                        print(f"Screenshot error: {e}")
                threading.Thread(target=_do_screenshot, daemon=True).start()
    def build_ui(self):
        self.chat_history = ctk.CTkTextbox(self, state="disabled", wrap="word", font=("Segoe UI", 16))
        self.chat_history.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")

        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        bottom_frame.grid_columnconfigure(1, weight=1)

        input_frame = ctk.CTkFrame(bottom_frame, height=60)
        input_frame.grid(row=0, column=0, sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        self.mic_btn = ctk.CTkButton(input_frame, text="🎤", command=self.toggle_mic, width=40)
        self.mic_btn.grid(row=0, column=0, padx=(10, 10), pady=15)

        self.entry = ctk.CTkEntry(input_frame, placeholder_text="Talk to Ember (via API)...")
        self.entry.grid(row=0, column=1, padx=(0, 10), pady=15, sticky="ew")
        self.entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(input_frame, text="Send", command=self.send_message, width=80)
        self.send_btn.grid(row=0, column=2, padx=(0, 10), pady=15)
        
        self.img_btn = ctk.CTkButton(input_frame, text="📷 Image", command=self.attach_image, width=80)
        self.img_btn.grid(row=0, column=3, padx=(0, 10), pady=15)
        
        self.generate_btn = ctk.CTkButton(input_frame, text="🎨 Generate Art", command=self.generate_image, width=100)
        self.generate_btn.grid(row=0, column=4, padx=(0, 10), pady=15)
        
        self.settings_btn = ctk.CTkButton(input_frame, text="⚙️ Settings", command=self.open_settings, width=100)
        self.settings_btn.grid(row=0, column=5, padx=(0, 10), pady=15)
        
        self.wake_btn = ctk.CTkButton(input_frame, text="👂 Wake Word: OFF", command=self.toggle_wake_word, width=130, fg_color="#333333", hover_color="#555555")
        self.wake_btn.grid(row=0, column=6, padx=(0, 10), pady=15)

    def attach_image(self):
        filepath = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if filepath:
            self.attached_image_path = filepath
            self.img_btn.configure(text="📷 Attached", fg_color="#228B22")

    def toggle_mic(self):
        self.listen_to_mic(auto_stop=False)

    def listen_to_mic(self, auto_stop=False, pre_buffer_list=None):
        if self.is_recording:
            self.is_recording = False
            return
        
        self.is_recording = True
        self.audio_data = []
        
        import queue
        audio_queue = queue.Queue()
        
        if pre_buffer_list:
            for item in pre_buffer_list:
                audio_queue.put(item)
                self.audio_data.append(item)
                
        def callback(indata, frames, time_info, status):
            audio_queue.put(indata.copy())
            self.audio_data.append(indata.copy())
            
        self.mic_btn.configure(text="🔴", fg_color="#8B0000")
        self.stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32', callback=callback)
        self.stream.start()
        
        if auto_stop:
            self.append_to_chat("System", "Listening... (Auto-stop active)")
        else:
            self.append_to_chat("System", "Recording... Click 🔴 to stop.")
            
        def _monitor():
            silence_start = None
            while self.is_recording:
                try:
                    chunk = audio_queue.get(timeout=0.1)
                    if auto_stop:
                        if np.max(np.abs(chunk)) < 0.02:
                            if silence_start is None: silence_start = time.time()
                            elif time.time() - silence_start > 2.0:
                                self.is_recording = False
                                break
                        else:
                            silence_start = None
                except queue.Empty: pass
                time.sleep(0.01)
                
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
            self.after(0, lambda: self.mic_btn.configure(text="🎤", fg_color="#1f538d"))
            threading.Thread(target=self.transcribe_audio).start()
            
        threading.Thread(target=_monitor).start()

    def transcribe_audio(self):
        self.after(0, self.append_to_chat, "System", "Transcribing via API...")
        try:
            audio_np = np.concatenate(self.audio_data, axis=0).flatten()
            buf = io.BytesIO()
            sf.write(buf, audio_np, 16000, format='WAV')
            buf.seek(0)
            
            files = {'audio': ('audio.wav', buf, 'audio/wav')}
            res = requests.post(f"{API_URL}/transcribe", headers=HEADERS, files=files)
            
            if res.status_code == 200:
                text = res.json().get('text', '')
                self.after(0, lambda: self.entry.delete(0, 'end'))
                self.after(0, lambda: self.entry.insert(0, text))
                self.after(0, self.send_message)
            else:
                self.after(0, self.append_to_chat, "System Error", f"STT failed: {res.text}")
        except Exception as e:
            self.after(0, self.append_to_chat, "System Error", str(e))

    def send_message(self):
        text = self.entry.get().strip()
        if not text: return
        self.append_to_chat("You", text)
        self.entry.delete(0, 'end')
        
        threading.Thread(target=self.api_chat, args=(text, self.attached_image_path)).start()
        
        self.attached_image_path = None
        self.img_btn.configure(text="📷 Image", fg_color="#1f538d")

    def api_chat(self, text, img_path):
        if not getattr(self, 'ws', None) or not self.ws.sock or not self.ws.sock.connected:
            self.after(0, self.append_to_chat, "System Error", "Not connected to API.")
            return
        payload = {"user_text": text, "attached_image_path": img_path}
        self.ws.send(json.dumps(payload))

    def generate_image(self):
        text = self.entry.get().strip()
        if not text:
            self.append_to_chat("System", "Type an image prompt first before clicking Generate Art.")
            return
        
        self.entry.delete(0, 'end')
        self.append_to_chat("System", f"Requesting image for: {text}")
        
        def api_gen():
            try:
                res = requests.post(f"{API_URL}/generate_image", headers=HEADERS, json={"prompt": text})
                if res.status_code == 200:
                    b64 = res.json().get('image_base64', '')
                    img_data = base64.b64decode(b64)
                    
                    img = Image.open(io.BytesIO(img_data))
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(512, 512))
                    self.after(0, self.show_image_popup, ctk_img)
                else:
                    self.after(0, self.append_to_chat, "System Error", f"Image API Failed: {res.text}")
            except Exception as e:
                self.after(0, self.append_to_chat, "System Error", f"Image Gen Error: {e}")
                
        threading.Thread(target=api_gen).start()
        
    def show_image_popup(self, ctk_img):
        top = ctk.CTkToplevel(self)
        top.title("Generated Artwork")
        top.geometry("550x550")
        top.configure(fg_color="#0A0A0A")

    def toggle_wake_word(self):
        self.wake_word_enabled = not self.wake_word_enabled
        if self.wake_word_enabled:
            self.wake_btn.configure(text="👂 Wake Word: ON", fg_color="#228B22", hover_color="#006400")
            self.append_to_chat("System", "Wake Word active. Say 'Ember' to start a conversation.")
            if not getattr(self, 'wake_thread_active', False):
                self.wake_thread_active = True
                threading.Thread(target=self.wake_word_worker).start()
        else:
            self.wake_btn.configure(text="👂 Wake Word: OFF", fg_color="#333333", hover_color="#555555")
            self.append_to_chat("System", "Wake Word deactivated.")

    def wake_word_worker(self):
        import queue
        audio_queue = queue.Queue()
        def callback(indata, frames, time_info, status):
            audio_queue.put(indata.copy())
            
        try:
            stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32', blocksize=8000, callback=callback)
            stream.start()
        except Exception as e:
            self.after(0, self.append_to_chat, "System Error", f"Wake word mic failed: {e}")
            self.wake_thread_active = False
            return
            
        buffer = np.zeros(0, dtype='float32')
        while self.wake_word_enabled:
            if self.is_recording:
                time.sleep(0.5)
                while not audio_queue.empty():
                    try: audio_queue.get_nowait()
                    except: break
                buffer = np.zeros(0, dtype='float32')
                continue
                
            try:
                chunk = audio_queue.get(timeout=1.0)
                buffer = np.concatenate((buffer, chunk.flatten()))
                if len(buffer) > 3 * 16000:
                    buffer = buffer[-3 * 16000:]
                
                if len(buffer) >= 1.5 * 16000:
                    if np.max(np.abs(buffer)) > 0.01:
                        buf = io.BytesIO()
                        sf.write(buf, buffer, 16000, format='WAV')
                        buf.seek(0)
                        files = {'audio': ('audio.wav', buf, 'audio/wav')}
                        try:
                            res = requests.post(f"{API_URL}/detect_wake_word", headers=HEADERS, files=files, timeout=2)
                            if res.status_code == 200 and res.json().get('detected'):
                                remainder = []
                                while not audio_queue.empty():
                                    try: remainder.append(audio_queue.get_nowait())
                                    except: break
                                self.after(0, lambda rem=remainder: self.trigger_wake_word_detected(rem))
                                buffer = np.zeros(0, dtype='float32')
                        except Exception: pass
                    buffer = np.zeros(0, dtype='float32')
            except queue.Empty: continue
            
        stream.stop()
        stream.close()
        self.wake_thread_active = False

    def trigger_wake_word_detected(self, pre_buffer_list=None):
        if not self.is_recording:
            self.append_to_chat("System", "Conversation started! Listening...")
            self.listen_to_mic(auto_stop=True, pre_buffer_list=pre_buffer_list)
            
    def resume_listening(self):
        if self.wake_word_enabled and not self.is_recording:
            self.append_to_chat("System", "Listening for follow-up...")
            self.listen_to_mic(auto_stop=True)

    def append_to_chat(self, sender, text):
        def _update():
            self.chat_history.configure(state="normal")
            self.chat_history.insert("end", f"\n{sender}: {text}\n")
            self.chat_history.configure(state="disabled")
            self.chat_history.see("end")
        self.after(0, _update)

    def open_settings(self):
        top = ctk.CTkToplevel(self)
        top.title("Companion Settings")
        top.geometry("450x450")
        top.attributes('-topmost', 'true')
        top.configure(fg_color="#121212")
        
        loading_lbl = ctk.CTkLabel(top, text="Fetching settings from API...", font=("Segoe UI", 12))
        loading_lbl.pack(pady=20)
        
        def fetch():
            try:
                res = requests.get(f"{API_URL}/models", headers=HEADERS)
                models = res.json().get("models", [])
                
                res2 = requests.get(f"{API_URL}/settings", headers=HEADERS)
                settings = res2.json()
                
                self.after(0, self.populate_settings, top, loading_lbl, models, settings)
            except Exception as e:
                self.after(0, lambda: loading_lbl.configure(text=f"API Error: {e}"))
                
        threading.Thread(target=fetch).start()

    def populate_settings(self, top, loading_lbl, models, settings):
        loading_lbl.destroy()
        
        # Model selection has been removed per user request.
        ctk.CTkLabel(top, text="Voice Accent:").pack(pady=(10,0))
        voices = ['af_bella', 'af_sarah', 'am_michael', 'bf_emma', 'bm_george']
        voice_var = ctk.StringVar(value=settings.get("voice", "af_bella"))
        
        def change_voice(choice):
            requests.post(f"{API_URL}/settings", headers=HEADERS, json={"voice": choice})
            self.append_to_chat("System", f"Switched voice to: {choice}")
            
        ctk.CTkOptionMenu(top, variable=voice_var, values=voices, command=change_voice).pack(pady=5)
        
        ctk.CTkLabel(top, text="Stable Diffusion API URL:").pack(pady=(10,0))
        sd_url_var = ctk.StringVar(value=settings.get("sd_api_url", "http://127.0.0.1:7860/sdapi/v1/txt2img"))
        
        def save_sd_url(*args):
            requests.post(f"{API_URL}/settings", headers=HEADERS, json={"sd_api_url": sd_url_var.get()})
            
        sd_url_var.trace_add("write", save_sd_url)
        ctk.CTkEntry(top, textvariable=sd_url_var, width=300).pack(pady=5)

        control_var = ctk.BooleanVar(value=settings.get("complete_computer_control", False))

        def toggle_complete_control():
            enabled = control_var.get()
            requests.post(f"{API_URL}/settings", headers=HEADERS, json={"complete_computer_control": enabled})
            status = "enabled" if enabled else "disabled"
            self.append_to_chat("System", f"Complete computer control on the client is now {status}.")

        ctk.CTkCheckBox(
            top,
            text="Enable complete computer control on this client",
            variable=control_var,
            command=toggle_complete_control
        ).pack(pady=(15, 5))
        
        def wipe_memory():
            res = requests.post(f"{API_URL}/wipe_memory", headers=HEADERS)
            if res.status_code == 200:
                self.append_to_chat("System", "Amnesia initiated. All memories wiped!")
                self.chat_history.configure(state="normal")
                self.chat_history.delete("1.0", "end")
                self.chat_history.configure(state="disabled")
                top.destroy()
            else:
                self.append_to_chat("System Error", "Failed to wipe memory via API.")

        ctk.CTkButton(top, text="Wipe Memory", fg_color="#8B0000", hover_color="#A52A2A", command=wipe_memory).pack(pady=20)

if __name__ == "__main__":
    app = AICompanionClient()
    app.mainloop()
