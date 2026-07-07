import os
import time
import re
import asyncio
import uvicorn
import logging

import numpy as np
from fastapi import FastAPI, HTTPException, Security, UploadFile, File, WebSocket, WebSocketDisconnect

from ember_app.auth import API_KEY, API_KEY_NAME, get_api_key
from ember_app.brain.speech import clean_assistant_text
from ember_app.daemons import start_background_daemons
from ember_app.state import init_state
from ember_app.routes.clipboard import router as clipboard_router
from ember_app.routes.files import router as files_router
from ember_app.routes.media import router as media_router
from ember_app.routes.permissions import router as permissions_router
from ember_app.routes.remote import router as remote_router
from ember_app.routes.research import router as research_router
from ember_app.routes.settings import router as settings_router
from ember_app.routes.status import router as status_router
from tools.permission_gate import (
    describe_permission_error,
    guard,
)

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.args and len(record.args) >= 3 and "/clipboard_sync" not in record.args[2]

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

from ember_engine import EmberCore

# Add current directory to PATH so faster_whisper can find the bundled ffmpeg
os.environ["PATH"] += os.pathsep + os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Ember Backend API")
engine = EmberCore()

from phidata_engine import PhidataEmberCore
phidata_engine = PhidataEmberCore()
app_state = init_state(engine, phidata_engine)

app.include_router(files_router)
app.include_router(clipboard_router)
app.include_router(media_router)
app.include_router(permissions_router)
app.include_router(remote_router)
app.include_router(research_router)
app.include_router(settings_router)
app.include_router(status_router)

@app.on_event("startup")
async def startup_event():
    def warm_audio_engines():
        try:
            engine.init_stt()
        except Exception as e:
            logging.error(f"STT startup failed: {e}")
        try:
            engine.init_tts()
        except Exception as e:
            logging.error(f"TTS startup failed: {e}")

    threading.Thread(target=warm_audio_engines, daemon=True).start()
    start_background_daemons()

import threading
global_sync_queue = app_state.global_sync_queue
active_websockets = app_state.active_websockets

@app.post("/api/remote_command")
async def remote_command(request: dict):
    # Allows a background python script (like wake word listener) to inject a prompt into the UI
    if "text" in request:
        global_sync_queue.put({"type": "remote_text", "text": request["text"]})
    return {"status": "ok"}

@app.post("/api/interrupt")
async def interrupt_command():
    messaged = 0
    for ws in list(active_websockets):
        try:
            await ws.send_json({"type": "interrupt"})
            messaged += 1
        except Exception:
            pass
    return {"status": "ok", "clients_messaged": messaged}

@app.post("/api/ui_action")
async def ui_action_endpoint(request: dict):
    action = request.get("action", "ui_action")
    category = {
        "take_screenshot": "screenshot",
        "capture_webcam": "webcam",
        "launch_app": "launch_app",
        "open_browser": "browser_open",
        "mouse_move": "keyboard_mouse",
        "mouse_click": "keyboard_mouse",
        "keyboard_type": "keyboard_mouse",
        "sync_clipboard": "clipboard_write",
    }.get(action)

    if category:
        try:
            guard(category, action, source="api_ui_action", payload=request)
        except Exception as e:
            raise HTTPException(status_code=403, detail=describe_permission_error(e))

    # Broadcast to all connected clients
    messaged = 0
    for ws in list(active_websockets):
        try:
            await ws.send_json({"type": "ui_action", "data": request})
            messaged += 1
        except Exception as e:
            print(f"Failed to send ui_action to a client: {e}")
    return {"status": "ok", "clients_messaged": messaged}

@app.post("/api/client_screenshot")
async def client_screenshot_endpoint(file: UploadFile = File(...), api_key: str = Security(get_api_key)):
    try:
        os.makedirs("companion_images", exist_ok=True)
        img_path = os.path.abspath("companion_images/client_screenshot.png")
        with open(img_path, "wb") as buffer:
            buffer.write(await file.read())
        return {"status": "ok", "path": img_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    state = "wake_word" # "wake_word" or "command"
    wake_words = ["ember", "amber", "emmer", "member"]
    
    SAMPLE_RATE = 16000
    BYTES_PER_SEC = 32000 # 16kHz * 1 channel * 2 bytes (int16)
    
    # Wake word buffer: rolling 3 seconds of audio
    MAX_BUFFER_WAKE = BYTES_PER_SEC * 3
    wake_buffer = bytearray()
    
    # Command buffer: accumulate until silence
    command_buffer = bytearray()
    has_spoken_in_command = False
    
    silence_bytes = 0
    SILENCE_THRESHOLD_BYTES_END = int(BYTES_PER_SEC * 2.5) # 2.5 seconds of silence to end
    SILENCE_THRESHOLD_BYTES_START = int(BYTES_PER_SEC * 15.0) # 15 seconds to start speaking
    
    last_transcribe_time = time.time()
    
    try:
        while True:
            message = await websocket.receive()
            
            if "text" in message and message["text"]:
                import json
                try:
                    msg = json.loads(message["text"])
                    if msg.get("type") == "force_command":
                        state = "command"
                        command_buffer = bytearray()
                        has_spoken_in_command = False
                        silence_bytes = 0
                        print("FORCED COMMAND MODE via UI")
                except: pass
                continue
                
            if "bytes" not in message or not message["bytes"]:
                continue
                
            data = message["bytes"]
            
            # Simple RMS VAD
            audio_array = np.frombuffer(data, dtype=np.int16)
            if len(audio_array) == 0: continue
            
            float_array = audio_array.astype(np.float32)
            rms = np.sqrt(np.mean(float_array**2))
            is_speaking = rms > 300 # threshold for 16-bit PCM (max 32768)
            
            if state == "wake_word":
                wake_buffer.extend(data)
                if len(wake_buffer) > MAX_BUFFER_WAKE:
                    wake_buffer = wake_buffer[-MAX_BUFFER_WAKE:]
                
                # Transcribe every ~1 second
                if time.time() - last_transcribe_time > 1.0:
                    last_transcribe_time = time.time()
                    
                    if len(wake_buffer) >= BYTES_PER_SEC:
                        np_audio = np.frombuffer(wake_buffer, dtype=np.int16).astype(np.float32) / 32768.0
                        text = await asyncio.to_thread(engine.transcribe_audio, np_audio)
                        text = text.lower()
                        text = re.sub(r'[^\w\s]', '', text)
                        
                        interrupt_words = ["stop", "hey", "wait", "enough"]
                        
                        if any(w in text for w in wake_words):
                            print(f"WAKE WORD DETECTED IN STREAM: '{text}'")
                            await websocket.send_json({"type": "wake_word_detected"})
                            state = "command"
                            command_buffer = bytearray()
                            has_spoken_in_command = False
                            silence_bytes = 0
                        elif any(w in text for w in interrupt_words):
                            print(f"INTERRUPT DETECTED IN STREAM: '{text}'")
                            await websocket.send_json({"type": "interrupt_detected"})
                            state = "command"
                            command_buffer = bytearray()
                            has_spoken_in_command = False
                            silence_bytes = 0
            
            elif state == "command":
                if is_speaking:
                    silence_bytes = 0
                    if not has_spoken_in_command:
                        has_spoken_in_command = True
                        command_buffer = bytearray() # Clear leading silence
                else:
                    silence_bytes += len(data)
                
                command_buffer.extend(data)
                
                current_threshold = SILENCE_THRESHOLD_BYTES_END if has_spoken_in_command else SILENCE_THRESHOLD_BYTES_START
                
                # If silence detected, process the accumulated command
                if silence_bytes > current_threshold:
                    if len(command_buffer) > int(BYTES_PER_SEC * 0.5) and has_spoken_in_command:
                        print("Silence detected, transcribing command...")
                        np_audio = np.frombuffer(command_buffer, dtype=np.int16).astype(np.float32) / 32768.0
                        text = await asyncio.to_thread(engine.transcribe_audio, np_audio)
                        text = text.strip()
                        
                        if text:
                            print(f"COMMAND TRANSCRIBED: '{text}'")
                            await websocket.send_json({"type": "command_transcribed", "text": text})
                            # Stay in command mode for continuous conversation
                            command_buffer = bytearray()
                            has_spoken_in_command = False
                            silence_bytes = 0
                            continue
                        else:
                            await websocket.send_json({"type": "command_empty"})
                    else:
                        await websocket.send_json({"type": "command_empty"})
                    
                    # Reset back to wake word mode
                    state = "wake_word"
                    wake_buffer = bytearray()
                    last_transcribe_time = time.time()
                    
    except WebSocketDisconnect:
        print("Audio WebSocket disconnected")
    except Exception as e:
        print(f"Audio WebSocket error: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    data = await websocket.receive_json()
    if data.get("api_key") != API_KEY:
        await websocket.close(code=1008)
        return
        
    active_websockets.append(websocket)
        
    import queue
    import threading
    import asyncio
    event_queue = queue.Queue()
    out_queue = queue.Queue()
    task_queue = queue.Queue()
    
    def engine_runner():
        while True:
            try:
                task = task_queue.get()
                if task is None: break
                text, img_path = task
                engine_worker(text, img_path)
            except Exception as e:
                print(f"engine_runner error: {e}")

    runner_thread = threading.Thread(target=engine_runner, daemon=True)
    runner_thread.start()
    
    def engine_worker(text, img_path=None):
        engine.last_interaction_time = time.time()
        try:
            out_queue.put(("thinking", True))
            out_queue.put(("stream_start", None))
            
            import re
            
            # 1. Use Phidata for inference
            bot_reply = phidata_engine.chat(text, engine, img_path=img_path)

            # Extract gestures
            gestures = re.findall(r'\[(wave|shrug|cheer)\]', bot_reply, re.IGNORECASE)
            spoken_text = clean_assistant_text(
                re.sub(r'\[(wave|shrug|cheer)\]', '', bot_reply, flags=re.IGNORECASE)
            )
            
            out_queue.put(("thinking", False))
            
            if gestures:
                out_queue.put(("gesture", gestures[0].lower()))
            
            # 2. Output the full text block (cleaned)
            out_queue.put(("text", spoken_text))
            
            # 3. Trigger Kokoro TTS manually on the full block and stream audio chunks
            if getattr(engine, "tts_pipeline", None):
                for _, _, audio_chunk in engine.tts_pipeline(spoken_text, voice=engine.voice):
                    out_queue.put(("audio", audio_chunk))
                    
            out_queue.put(("stream_done", None))
        except Exception as e:
            out_queue.put(("error", str(e)))

    async def send_loop():
        while True:
            try:
                try:
                    msg_type, content = await asyncio.to_thread(out_queue.get, True, 1.0)
                except queue.Empty:
                    continue
                if msg_type == "stream_start":
                    await websocket.send_json({"type": "stream_start"})
                elif msg_type == "stream_done":
                    await websocket.send_json({"type": "stream_done"})
                elif msg_type == "error":
                    await websocket.send_json({"type": "error", "message": content})
                elif msg_type == "ui_action":
                    await websocket.send_json({"type": "ui_action", "data": content})
                elif msg_type == "thinking":
                    await websocket.send_json({"type": "thinking", "status": content})
                elif msg_type == "text":
                    await websocket.send_json({"type": "text", "chunk": content})
                elif msg_type == "gesture":
                    await websocket.send_json({"type": "gesture", "gesture": content})
                elif msg_type == "interrupt":
                    await websocket.send_json({"type": "interrupt"})
                elif msg_type == "image":
                    await websocket.send_json({"type": "image", "data": content})
                elif msg_type == "audio":
                    import base64
                    import io
                    import soundfile as sf
                    try:
                        if hasattr(content, "numpy"):
                            content = content.numpy()
                        buf = io.BytesIO()
                        sf.write(buf, content, 24000, format='WAV')
                        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                        await websocket.send_json({"type": "audio", "data": b64})
                    except Exception as e:
                        print(f"Audio processing error: {e}")
            except Exception as e:
                print(f"WS send loop error: {e}")
                break
                
    async def event_loop():
        while True:
            try:
                try:
                    event_type, event_data = await asyncio.to_thread(event_queue.get, timeout=1.0)
                except queue.Empty:
                    continue
                if event_type == "system_trigger":
                    if isinstance(event_data, str) and "[URGENT]" in event_data:
                        out_queue.put(("interrupt", None))
                    task_queue.put((event_data, None))
                elif event_type == "game_loop_trigger":
                    text, img_path = event_data
                    task_queue.put((text, img_path))
                elif event_type == "image_trigger":
                    out_queue.put(("image", event_data))
                elif event_type == "ui_action":
                    out_queue.put(("ui_action", event_data))
            except Exception as e:
                print(f"Event loop error: {e}")
                break

    async def global_queue_loop():
        while True:
            try:
                try:
                    msg = await asyncio.to_thread(global_sync_queue.get, True, 1.0)
                except queue.Empty:
                    continue
                if msg["type"] == "remote_text":
                    # Send it to the UI first so the user sees it in chat
                    await websocket.send_json({"type": "remote_text", "text": msg["text"]})
                    # Then trigger the LLM to think about it!
                    task_queue.put((msg["text"], None))
                elif msg["type"] == "system_trigger":
                    task_queue.put((msg["text"], msg.get("image_path")))
                elif msg["type"] == "ui_action":
                    await websocket.send_json({"type": "ui_action", "data": msg["data"]})
            except Exception as e:
                print(f"Global queue error: {e}")
                break

    task1 = asyncio.create_task(send_loop())
    task2 = asyncio.create_task(event_loop())
    task3 = asyncio.create_task(global_queue_loop())



    try:
        while True:
            data = await websocket.receive_json()
            
            # Handle background memory telemetry
            if data.get("type") == "memory_telemetry":
                engine.latest_telemetry = data
                continue

            user_text = data.get("user_text", "")
            img_path = data.get("attached_image_path", None)
            img_b64 = data.get("attached_image_b64", None)
            share_screen = data.get("share_screen", False)
            
            if share_screen:
                from PIL import ImageGrab
                try:
                    os.makedirs("companion_images", exist_ok=True)
                    screenshot = ImageGrab.grab()
                    img_path = os.path.abspath(f"companion_images/context_{int(time.time())}.png")
                    screenshot.save(img_path)
                except Exception as e:
                    print(f"Failed to capture screen context: {e}")
            elif img_b64:
                import uuid, base64, os
                os.makedirs("companion_images", exist_ok=True)
                img_path = f"companion_images/web_{uuid.uuid4().hex}.jpg"
                try:
                    # Strip data:image/...;base64, prefix if present
                    header_split = img_b64.split(",")
                    b64_str = header_split[1] if len(header_split) > 1 else img_b64
                    with open(img_path, "wb") as f:
                        f.write(base64.b64decode(b64_str))
                except Exception as e:
                    print(f"Failed to decode image: {e}")
                    img_path = None
                    
            if user_text or img_path:
                task_queue.put((user_text, img_path))
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        task_queue.put(None) # stop engine_runner
        task1.cancel()
        task2.cancel()
        task3.cancel()

if __name__ == "__main__":
    uvicorn.run("ember_api:app", host="0.0.0.0", port=8000, reload=False)
