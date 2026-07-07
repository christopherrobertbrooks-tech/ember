import datetime
import os
import random
import threading
import time
import uuid

from ember_app.state import get_state


def start_background_daemons() -> None:
    threading.Thread(target=reminder_daemon, daemon=True).start()
    threading.Thread(target=idle_daemon, daemon=True).start()
    threading.Thread(target=vision_loop_daemon, daemon=True).start()
    threading.Thread(target=memory_consolidation_daemon, daemon=True).start()


def memory_consolidation_daemon():
    from tools.memory_manager import EmberMemoryManager

    mem_mgr = EmberMemoryManager()
    time.sleep(30)
    while True:
        try:
            mem_mgr.consolidate_memories()
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            cursor = mem_mgr.conn.cursor()
            cursor.execute("SELECT date FROM daily_diary WHERE date = ?", (today_str,))
            if not cursor.fetchone():
                mem_mgr.generate_daily_diary()
        except Exception as e:
            print(f"Memory consolidation daemon error: {e}")
        time.sleep(300)


def reminder_daemon():
    app_state = get_state()
    while True:
        for reminder in app_state.engine.reminders[:]:
            if time.time() >= reminder["trigger_time"]:
                app_state.engine.reminders.remove(reminder)
                msg = (
                    "[SYSTEM NOTIFICATION: A timer just went off! "
                    f"The user asked you to remind them about: '{reminder['message']}'. "
                    "Alert them immediately! CRITICAL: You MUST use the 'send_push_notification' tool "
                    "to send a push notification to Chris so he actually sees this reminder!]"
                )
                app_state.global_sync_queue.put({"type": "system_trigger", "text": msg})
        time.sleep(5)


def idle_daemon():
    app_state = get_state()
    target_idle_minutes = random.randint(15, 45)
    while True:
        time.sleep(60)
        engine = app_state.engine
        if getattr(engine, "dnd_enabled", False):
            continue

        idle_time = time.time() - getattr(engine, "last_interaction_time", time.time())
        if idle_time > target_idle_minutes * 60:
            msg = (
                f"[SYSTEM NOTIFICATION: You have been idle for over {target_idle_minutes} minutes. "
                "Would you like to check in on the user, share a thought, or suggest something? "
                "CRITICAL: You MUST use the 'send_push_notification' tool to send a push notification "
                "to Chris so he gets your message!]"
            )
            app_state.global_sync_queue.put({"type": "system_trigger", "text": msg})
            engine.last_interaction_time = time.time()
            target_idle_minutes = random.randint(15, 45)


def vision_loop_daemon():
    from PIL import ImageGrab

    app_state = get_state()
    while True:
        time.sleep(10)
        if getattr(app_state.engine, "game_mode", False):
            try:
                os.makedirs("companion_images", exist_ok=True)
                img_path = os.path.abspath(f"companion_images/game_loop_{uuid.uuid4().hex}.jpg")
                img = ImageGrab.grab()
                width, height = img.size
                img = img.convert("RGB")
                img.thumbnail((1024, 1024))
                img.save(img_path, format="JPEG", quality=75)

                msg = (
                    "[GAME LOOP]: This is the current screen state. "
                    f"Resolution: {width}x{height}. You are playing a game. "
                    "Calculate the exact pixel X and Y coordinates of your next move, "
                    "and output a control_computer tool call to click that spot."
                )
                app_state.global_sync_queue.put({"type": "system_trigger", "text": msg, "image_path": img_path})
            except Exception as e:
                print(f"Game loop screenshot failed: {e}")
