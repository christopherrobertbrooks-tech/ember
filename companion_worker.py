import os
import io
import json
import base64
import time
import subprocess
import shutil
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from tools.permission_gate import describe_permission_error, guard

app = FastAPI()

TOOL_PERMISSION_CATEGORIES = {
    "os_command": "shell",
    "launch_app": "launch_app",
    "control_computer": "keyboard_mouse",
    "take_screenshot": "screenshot",
    "capture_webcam": "webcam",
    "find_text_on_screen": "screenshot",
    "manage_window": "keyboard_mouse",
    "minimize_all_windows": "keyboard_mouse",
    "manage_media": "keyboard_mouse",
    "kill_process": "shell",
    "lock_computer": "system_power",
    "read_clipboard": "clipboard_read",
    "write_clipboard": "clipboard_write",
    "read_file": "file_read",
    "write_file": "file_write",
    "move_file": "file_write",
    "organize_folder": "file_write",
}

FILE_CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Executables": [".exe", ".msi", ".bat", ".cmd"],
    "Code": [".py", ".js", ".html", ".css", ".json", ".xml", ".cpp", ".c", ".h", ".cs", ".java"],
}

def resolve_known_folder(path: str) -> str:
    if not path:
        return path
    normalized = path.strip().lower()
    home = os.path.expanduser("~")
    known_folders = {
        "desktop": os.path.join(home, "Desktop"),
        "downloads": os.path.join(home, "Downloads"),
        "documents": os.path.join(home, "Documents"),
        "pictures": os.path.join(home, "Pictures"),
        "music": os.path.join(home, "Music"),
        "videos": os.path.join(home, "Videos"),
    }
    return known_folders.get(normalized, os.path.expandvars(os.path.expanduser(path)))

def unique_destination(path: str) -> str:
    if not os.path.exists(path):
        return path

    directory, filename = os.path.split(path)
    stem, ext = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = os.path.join(directory, f"{stem} ({counter}){ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1

def draw_grid_on_image(img):
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    width, height = img.size
    grid_spacing = 100
    for x in range(0, width, grid_spacing):
        draw.line([(x, 0), (x, height)], fill=(255, 0, 0, 128), width=1)
        for y in range(0, height, grid_spacing):
            draw.text((x + 5, y + 5), f"{x},{y}", fill=(255, 0, 0, 128))
    for y in range(0, height, grid_spacing):
        draw.line([(0, y), (width, y)], fill=(255, 0, 0, 128), width=1)
    return img

@app.post("/execute")
async def execute_tool(request: Request):
    data = await request.json()
    name = data.get("tool")
    args = data.get("args", {})
    
    result = {"status": "success", "output": ""}
    
    try:
        category = TOOL_PERMISSION_CATEGORIES.get(name)
        if category:
            guard(category, name, source="companion_worker", payload=args)

        if name == "os_command":
            cmd = args.get("command", "")
            p = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=15)
            result["output"] = p.stdout.strip() or p.stderr.strip() or "Success."
            
        elif name == "launch_app":
            app_name = args.get("app_name", "")
            ps_cmd = f"Get-StartApps | Where-Object {{ $_.Name -match '(?i){app_name}' }} | ConvertTo-Json -Compress"
            p = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
            out = p.stdout.strip()
            if out:
                apps = json.loads(out)
                if isinstance(apps, dict): apps = [apps]
                if len(apps) >= 1:
                    subprocess.Popen(f"explorer.exe shell:AppsFolder\\{apps[0]['AppID']}", shell=True)
                    time.sleep(2.0)
                    result["output"] = f"Successfully Launched {apps[0]['Name']}."
                else:
                    result["output"] = f"Could not find app '{app_name}'."
            else:
                result["output"] = f"Could not find app '{app_name}'."
                
        elif name == "control_computer":
            import pyautogui
            action = args.get("action", "")
            x = args.get("x")
            y = args.get("y")
            text = args.get("text", "")
            amount = args.get("amount", 0)
            
            if action == "click":
                pyautogui.click(x=x, y=y)
                result["output"] = f"Clicked at ({x}, {y})"
            elif action == "type":
                pyautogui.write(text, interval=0.05)
                pyautogui.press('enter')
                result["output"] = f"Typed '{text}' and pressed Enter"
            elif action == "press_key":
                pyautogui.press(text)
                result["output"] = f"Pressed key '{text}'"
            elif action == "scroll":
                pyautogui.scroll(amount)
                result["output"] = f"Scrolled {amount}"
            elif action == "wait":
                time.sleep(amount)
                result["output"] = f"Waited {amount} seconds"
            else:
                result["output"] = f"Unknown action: {action}"
                
        elif name == "take_screenshot":
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img = img.convert('RGB')
            img = draw_grid_on_image(img)
            img.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            result["output"] = "Screenshot taken"
            result["image_b64"] = b64
            
        elif name == "capture_webcam":
            try:
                import cv2
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    result["status"] = "error"
                    result["output"] = "Error: Webcam could not be opened. Check if it is plugged in or used by another application."
                else:
                    for _ in range(5):
                        cap.read() # Let camera warm up
                    ret, frame = cap.read()
                    cap.release()
                    if ret:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        from PIL import Image
                        img = Image.fromarray(rgb_frame)
                        img.thumbnail((1024, 1024))
                        
                        buf = io.BytesIO()
                        img.save(buf, format='JPEG', quality=80)
                        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                        result["output"] = "Webcam image captured"
                        result["image_b64"] = b64
                    else:
                        result["status"] = "error"
                        result["output"] = "Error: Failed to read frame from webcam."
            except ImportError:
                result["status"] = "error"
                result["output"] = "Error: opencv-python is not installed on the client machine. Please run 'pip install opencv-python' and restart the client."
            except Exception as e:
                result["status"] = "error"
                result["output"] = f"Error capturing webcam: {e}"
            
        elif name == "find_text_on_screen":
            text_to_find = args.get("text", "").lower()
            from PIL import ImageGrab
            import pytesseract
            if os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
                pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            img = ImageGrab.grab()
            try:
                ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                found = False
                for i, word in enumerate(ocr_data['text']):
                    if word and text_to_find in word.lower():
                        px = ocr_data['left'][i] + ocr_data['width'][i] // 2
                        py = ocr_data['top'][i] + ocr_data['height'][i] // 2
                        result["output"] = f"Found '{word}' at coordinates x={px}, y={py}. You can now use control_computer to click it."
                        found = True
                        break
                if not found:
                    result["output"] = f"Could not find text '{text_to_find}' on the screen."
            except pytesseract.pytesseract.TesseractNotFoundError:
                result["output"] = "ERROR: Tesseract OCR is not installed or not in PATH."
                
        elif name == "manage_window":
            action = args.get("action", "")
            window_title = args.get("window_title", "")
            if action == "minimize_all":
                import pyautogui
                pyautogui.hotkey('win', 'd')
                result["output"] = "Successfully minimized all windows using Win+D."
            else:
                import pygetwindow as gw
                windows = gw.getWindowsWithTitle(window_title)
                if not windows:
                    result["output"] = f"Could not find any window with title containing '{window_title}'."
                else:
                    win = windows[0]
                    if action == "maximize": win.maximize()
                    elif action == "minimize": win.minimize()
                    elif action == "restore": win.restore()
                    elif action == "close": win.close()
                    elif action == "activate": win.activate()
                    result["output"] = f"Successfully performed '{action}' on window '{win.title}'."
                    
        elif name == "minimize_all_windows":
            import pyautogui
            pyautogui.hotkey('win', 'd')
            result["output"] = "Successfully minimized all windows to show the desktop."
            
        elif name == "manage_media":
            action = args.get("action", "")
            import pyautogui
            if action == "playpause": pyautogui.press("playpause")
            elif action == "next": pyautogui.press("nexttrack")
            elif action == "previous": pyautogui.press("prevtrack")
            elif action == "volume_up": pyautogui.press("volumeup", presses=5)
            elif action == "volume_down": pyautogui.press("volumedown", presses=5)
            elif action == "mute": pyautogui.press("volumemute")
            result["output"] = f"Successfully performed media action: {action}"
            
        elif name == "kill_process":
            process_name = args.get("process_name", "")
            p = subprocess.run(["powershell", "-Command", f"Stop-Process -Name '{process_name}' -Force -ErrorAction SilentlyContinue"], capture_output=True, text=True)
            result["output"] = f"Successfully attempted to kill process '{process_name}'."
            
        elif name == "lock_computer":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            result["output"] = "Computer locked successfully."
            
        elif name == "read_clipboard":
            p = subprocess.run(["powershell", "-Command", "Get-Clipboard"], capture_output=True, text=True)
            result["output"] = f"Clipboard contents:\n{p.stdout.strip()}"
            
        elif name == "write_clipboard":
            text = args.get("text", "")
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
                f.write(text)
                temp_path = f.name
            subprocess.run(["powershell", "-Command", f"Get-Content '{temp_path}' -Raw | Set-Clipboard"])
            os.remove(temp_path)
            result["output"] = "Text successfully written to clipboard."
            
        elif name == "read_file":
            filepath = resolve_known_folder(args.get("filepath", ""))
            if not os.path.exists(filepath):
                result["status"] = "error"
                result["output"] = f"Error: File '{filepath}' does not exist."
            elif not os.path.isfile(filepath):
                result["status"] = "error"
                result["output"] = f"Error: '{filepath}' is not a file."
            else:
                with open(filepath, "r", encoding="utf-8") as f:
                    result["output"] = f.read()
                    
        elif name == "write_file":
            filepath = resolve_known_folder(args.get("filepath", ""))
            content = args.get("content", "")
            # Ensure parent directory exists
            parent_dir = os.path.dirname(filepath)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            result["output"] = f"Successfully wrote to file '{filepath}'."

        elif name == "move_file":
            source_path = resolve_known_folder(args.get("source_path", ""))
            destination_path = resolve_known_folder(args.get("destination_path", ""))
            if not source_path or not destination_path:
                result["status"] = "error"
                result["output"] = "Error: source_path and destination_path are required."
            elif not os.path.exists(source_path):
                result["status"] = "error"
                result["output"] = f"Error: Source path '{source_path}' does not exist."
            else:
                if os.path.isdir(destination_path):
                    destination_path = os.path.join(destination_path, os.path.basename(source_path))
                parent_dir = os.path.dirname(destination_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                final_destination = unique_destination(destination_path)
                shutil.move(source_path, final_destination)
                result["output"] = f"Successfully moved '{source_path}' to '{final_destination}'."

        elif name == "organize_folder":
            folder_path = resolve_known_folder(args.get("folder_path", "Desktop"))
            if not os.path.exists(folder_path):
                result["status"] = "error"
                result["output"] = f"Error: Folder '{folder_path}' does not exist."
            elif not os.path.isdir(folder_path):
                result["status"] = "error"
                result["output"] = f"Error: '{folder_path}' is not a folder."
            else:
                moved_count = 0
                skipped_count = 0
                for item in os.listdir(folder_path):
                    item_path = os.path.join(folder_path, item)
                    if not os.path.isfile(item_path):
                        continue

                    _, ext = os.path.splitext(item)
                    ext = ext.lower()
                    target_category = "Other"
                    for category_name, extensions in FILE_CATEGORIES.items():
                        if ext in extensions:
                            target_category = category_name
                            break

                    target_dir = os.path.join(folder_path, target_category)
                    os.makedirs(target_dir, exist_ok=True)
                    destination = unique_destination(os.path.join(target_dir, item))
                    try:
                        shutil.move(item_path, destination)
                        moved_count += 1
                    except Exception:
                        skipped_count += 1

                result["output"] = (
                    f"Successfully organized {moved_count} files in '{folder_path}' into categorized folders."
                )
                if skipped_count:
                    result["output"] += f" Skipped {skipped_count} file(s) that could not be moved."
            
        else:
            result["output"] = f"Tool '{name}' not supported by companion worker."
            result["status"] = "error"
            
    except Exception as e:
        result["status"] = "error"
        result["output"] = describe_permission_error(e)
        
    return JSONResponse(content=result)

if __name__ == "__main__":
    print("Starting Ember Companion Worker on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002)
