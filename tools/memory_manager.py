import sqlite3
import os
import json
import time
import uuid
import requests

DB_FILE = "ember_memory.db"
CONFIG_FILE = "ember_config.json"

class EmberMemoryManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # 1. Table for key facts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS long_term_facts (
                id TEXT PRIMARY KEY,
                fact_text TEXT,
                category TEXT,
                created_at REAL
            )
        """)
        # 2. Table for relationship/affinity score
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationship_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at REAL
            )
        """)
        # Initialize affinity score if not exists
        cursor.execute("SELECT value FROM relationship_state WHERE key = 'affinity_score'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO relationship_state (key, value, updated_at) VALUES ('affinity_score', '50', ?)", (time.time(),))
            
        # 3. Table for daily diary
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_diary (
                date TEXT PRIMARY KEY,
                summary TEXT,
                mood TEXT,
                created_at REAL
            )
        """)
        
        # 4. Table to track last processed message count for each session
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_sessions (
                session_id TEXT PRIMARY KEY,
                last_msg_count INTEGER,
                updated_at REAL
            )
        """)
        self.conn.commit()

    def get_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    # --- Memory Consolidation Logic ---
    def consolidate_memories(self):
        print("[EmberMemory] Running memory consolidation check...")
        config = self.get_config()
        llama_url = config.get("llama_server_url", "http://127.0.0.1:11434/v1")
        model = config.get("model", "pixtral-12b")

        # Get latest active session from phidata
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT session_id, memory FROM ember_sessions ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                print("[EmberMemory] No chat session history found in SQLite database.")
                return False
                
            session_id, memory_json = row
            try:
                parsed_memory = json.loads(memory_json)
            except Exception as e:
                print(f"[EmberMemory] Failed to parse memory JSON: {e}")
                return False

            # Retrieve runs / messages
            messages = []
            if isinstance(parsed_memory, dict) and "runs" in parsed_memory:
                for run in parsed_memory["runs"]:
                    if "messages" in run:
                        for m in run["messages"]:
                            role = m.get("role")
                            content = m.get("content")
                            if role in ["user", "assistant"] and content:
                                messages.append({"role": role, "content": content})
            elif isinstance(parsed_memory, list):
                for m in parsed_memory:
                    role = m.get("role")
                    content = m.get("content")
                    if role in ["user", "assistant"] and content:
                        messages.append({"role": role, "content": content})

            if not messages:
                print("[EmberMemory] No dialogue messages found to process.")
                return False

            # Check how many messages we have already processed for this session
            cursor.execute("SELECT last_msg_count FROM processed_sessions WHERE session_id = ?", (session_id,))
            last_row = cursor.fetchone()
            last_count = last_row[0] if last_row else 0

            # Only run if there are new messages (let's say at least 4 new messages)
            new_msg_count = len(messages) - last_count
            if new_msg_count < 4:
                print(f"[EmberMemory] Only {new_msg_count} new messages since last check. Skipping consolidation.")
                return False

            # Extract recent new messages
            new_messages = messages[last_count:]
            print(f"[EmberMemory] Found {len(new_messages)} new messages. Consolidating...")

            # Format dialogue context for LLM
            dialogue_text = ""
            for m in new_messages:
                speaker = "Chris" if m["role"] == "user" else "Ember"
                dialogue_text += f"{speaker}: {m['content']}\n"

            # Prompt LLM to extract facts
            system_prompt = (
                "You are the memory manager for E.M.B.E.R. (an AI companion). "
                "Your job is to read recent dialogue and extract any facts, preferences, plans, projects, "
                "or details about the user (Chris) mentioned in this segment. "
                "Write each fact as a simple, concise one-sentence statement starting with 'Chris' "
                "(e.g., 'Chris is studying Python', 'Chris prefers coffee over tea', 'Chris has a meeting at 2 PM'). "
                "Only extract actual facts. Do not invent details. "
                "If no concrete facts or preferences are mentioned, reply with 'NONE'."
            )
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Recent dialogue:\n{dialogue_text}\n\nExtract facts:"}
                ],
                "temperature": 0.1,
                "stream": False
            }

            headers = {"Content-Type": "application/json"}
            chat_completions_url = f"{llama_url.rstrip('/')}/chat/completions"
            response = requests.post(chat_completions_url, json=payload, headers=headers, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                print(f"[EmberMemory] Extracted text: {content}")
                
                if content and content.upper() != "NONE":
                    lines = content.split("\n")
                    added_count = 0
                    for line in lines:
                        cleaned = line.strip().lstrip("-*•").strip()
                        if cleaned and len(cleaned) > 10 and cleaned.lower().startswith("chris"):
                            self.add_fact(cleaned, category="consolidated")
                            added_count += 1
                    print(f"[EmberMemory] Successfully consolidated {added_count} new facts.")
                
                # Update processed messages count
                cursor.execute(
                    "INSERT OR REPLACE INTO processed_sessions (session_id, last_msg_count, updated_at) VALUES (?, ?, ?)",
                    (session_id, len(messages), time.time())
                )
                self.conn.commit()
                return True
            else:
                print(f"[EmberMemory] LLM request failed with status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[EmberMemory] Memory consolidation error: {e}")
            return False

    def generate_daily_diary(self):
        print("[EmberMemory] Generating daily companion log...")
        config = self.get_config()
        llama_url = config.get("llama_server_url", "http://127.0.0.1:11434/v1")
        model = config.get("model", "pixtral-12b")

        cursor = self.conn.cursor()
        try:
            # Query the latest 40 messages
            cursor.execute("SELECT memory FROM ember_sessions ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return False
            
            parsed_memory = json.loads(row[0])
            messages = []
            if isinstance(parsed_memory, dict) and "runs" in parsed_memory:
                for run in parsed_memory["runs"]:
                    if "messages" in run:
                        for m in run["messages"]:
                            role = m.get("role")
                            content = m.get("content")
                            if role in ["user", "assistant"] and content:
                                messages.append({"role": role, "content": content})
                                
            if not messages:
                return False
                
            dialogue_text = ""
            for m in messages[-30:]:
                speaker = "Chris" if m["role"] == "user" else "Ember"
                dialogue_text += f"{speaker}: {m['content']}\n"

            # Generate diary summary
            date_str = time.strftime("%Y-%m-%d")
            
            system_prompt = (
                "You are E.M.B.E.R. (Emotive Multimodal Behavioral Emulation Routine). "
                "Read the dialogue logs of your interactions with Chris today, and write a secret, "
                "concise private diary entry about today. Be factual, calm, and supportive. "
                "Summarize what you worked on together, what he did, and any useful follow-up context. "
                "Also decide what your mood is for today (e.g. Focused, Impressed, Tired, Encouraged).\n\n"
                "Format your output EXACTLY as a JSON object with keys 'summary' and 'mood'. "
                "Do not include any extra text, markdown formatting, or code blocks."
            )
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Today's dialogue:\n{dialogue_text}"}
                ],
                "temperature": 0.7,
                "stream": False
            }

            chat_completions_url = f"{llama_url.rstrip('/')}/chat/completions"
            response = requests.post(chat_completions_url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                # Clean up any potential markdown wrapper
                if content.startswith("```"):
                    lines = content.split("\n")
                    if lines[0].startswith("```json"):
                        content = "\n".join(lines[1:-1])
                    else:
                        content = "\n".join(lines[1:-1])
                        
                diary_data = json.loads(content)
                summary = diary_data.get("summary", "")
                mood = diary_data.get("mood", "Neutral")
                
                self.add_diary_entry(date_str, summary, mood)
                print(f"[EmberMemory] Daily diary saved. Mood: {mood}")
                return True
            return False
        except Exception as e:
            print(f"[EmberMemory] Failed to generate daily diary: {e}")
            return False

    # --- Facts Management ---
    def add_fact(self, fact_text, category="general"):
        cursor = self.conn.cursor()
        fact_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO long_term_facts (id, fact_text, category, created_at) VALUES (?, ?, ?, ?)",
            (fact_id, fact_text, category, time.time())
        )
        self.conn.commit()
        return fact_id

    def get_all_facts(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT fact_text, category FROM long_term_facts ORDER BY created_at DESC")
        return cursor.fetchall()

    def get_facts_summary(self):
        facts = self.get_all_facts()
        if not facts:
            return ""
        
        summary_lines = []
        for text, cat in facts:
            summary_lines.append(f"- {text}")
        return "\n".join(summary_lines)

    # --- Relationship State Management ---
    def get_affinity_score(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM relationship_state WHERE key = 'affinity_score'")
        row = cursor.fetchone()
        return int(row[0]) if row else 50

    def set_affinity_score(self, score):
        cursor = self.conn.cursor()
        score = max(0, min(100, int(score))) # clamp between 0 and 100
        cursor.execute(
            "INSERT OR REPLACE INTO relationship_state (key, value, updated_at) VALUES ('affinity_score', ?, ?)",
            (str(score), time.time())
        )
        self.conn.commit()

    def update_affinity_by_delta(self, delta):
        current = self.get_affinity_score()
        self.set_affinity_score(current + delta)
        return self.get_affinity_score()

    # --- Daily Diary Management ---
    def add_diary_entry(self, date_str, summary, mood):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO daily_diary (date, summary, mood, created_at) VALUES (?, ?, ?, ?)",
            (date_str, summary, mood, time.time())
        )
        self.conn.commit()

    def get_diary_entries(self, limit=10):
        cursor = self.conn.cursor()
        cursor.execute("SELECT date, summary, mood FROM daily_diary ORDER BY created_at DESC LIMIT ?", (limit,))
        return cursor.fetchall()
