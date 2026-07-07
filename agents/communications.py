import threading
import time
import os

class CommunicationsAgent(threading.Thread):
    def __init__(self, event_queue):
        super().__init__(daemon=True)
        self.event_queue = event_queue
        self.known_email_ids = set()
        
    def run(self):
        print("[CommunicationsAgent] Starting inbox monitoring agent...")
        # Lazy import to avoid loading Google API on engine startup if not needed
        try:
            from email_agent import EmailAgent
            agent = EmailAgent()
            
            # Initial poll just to populate known emails without alerting
            if agent.authenticate():
                print("[CommunicationsAgent] Authenticated with Gmail API successfully.")
                emails = agent.get_unread_emails(max_results=10)
                if isinstance(emails, list):
                    for em in emails:
                        self.known_email_ids.add(em.get('id'))
                    print(f"[CommunicationsAgent] Indexed {len(self.known_email_ids)} existing unread emails. Polling every 60s.")
                else:
                    print(f"[CommunicationsAgent] Initial email fetch returned non-list: {emails}")
            else:
                print("[CommunicationsAgent] Gmail authentication failed. Agent will not poll.")
                return
        except Exception as e:
            print(f"[CommunicationsAgent] Initialization error: {e}")
            return
            
        while True:
            time.sleep(60) # Poll every 60 seconds
            try:
                if not agent.authenticate():
                    print("[CommunicationsAgent] Re-authentication failed, skipping this cycle.")
                    continue
                    
                emails = agent.get_unread_emails(max_results=5)
                if isinstance(emails, str): # Error string returned
                    print(f"[CommunicationsAgent] Email fetch error: {emails}")
                    continue
                    
                for em in emails:
                    email_id = em.get('id')
                    if email_id and email_id not in self.known_email_ids:
                        self.known_email_ids.add(email_id)
                        
                        sender = em.get('sender', 'Unknown')
                        subject = em.get('subject', 'No Subject')
                        snippet = em.get('snippet', '')
                        
                        print(f"[CommunicationsAgent] New email detected from '{sender}': '{subject}'")
                        message = f"[COMMUNICATIONS AGENT] The user just received a new email from '{sender}' with the subject '{subject}'. A snippet says: '{snippet[:100]}...'. Mention this to them!"
                        if self.event_queue:
                            self.event_queue.put(("system_trigger", message))
            except Exception as e:
                print(f"[CommunicationsAgent] Polling error: {e}")
