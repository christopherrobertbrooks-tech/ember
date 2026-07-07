import threading
import time
import os
import json
from ddgs import DDGS
import requests
from tools.research_library import make_report_path, record_report

class ResearcherAgent(threading.Thread):
    def __init__(self, topic, event_queue, llama_server_url="http://127.0.0.1:11434/v1", model=None):
        super().__init__(daemon=True)
        self.topic = topic
        self.event_queue = event_queue
        self.llama_server_url = llama_server_url
        self.output_dir = "research"
        os.makedirs(self.output_dir, exist_ok=True)

        # Read model from config if not explicitly provided
        if model:
            self.model = model
        else:
            try:
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ember_config.json")
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.model = config.get("model", "llama3.2")
            except Exception:
                self.model = "llama3.2"

    def _call_llm(self, prompt):
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.model,
            "messages": [{"role": "system", "content": "You are a professional research assistant."},
                         {"role": "user", "content": prompt}]
        }
        try:
            response = requests.post(self.llama_server_url + "/chat/completions", headers=headers, json=data, timeout=120)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                print(f"[ResearcherAgent] LLM returned status {response.status_code}: {response.text[:300]}")
        except Exception as e:
            print(f"[ResearcherAgent] Error calling LLM: {e}")
        return "Failed to generate report."

    def run(self):
        try:
            # Step 1: Gather raw info
            print(f"[ResearcherAgent] Starting research on: {self.topic}")
            print(f"[ResearcherAgent] Using model: {self.model} at {self.llama_server_url}")
            
            refine_prompt = (
                f"I need to search the web for the following topic or request: '{self.topic}'. "
                "Please rewrite this into a concise, highly effective web search query string. "
                "Reply with ONLY the exact search query itself, no quotes, no introductory text."
            )
            search_query = self._call_llm(refine_prompt).strip().strip('"').strip("'")
            
            # Fallback in case the LLM yaps or returns something too long
            if not search_query or len(search_query) > 100 or "\n" in search_query:
                search_query = self.topic
                
            print(f"[ResearcherAgent] Refined query: {search_query}")
            results = DDGS().text(search_query, max_results=10)
            source_rows = []
            for r in results:
                source_rows.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "href": r.get("href") or r.get("url", ""),
                })
            raw_text = "\n".join([
                f"- {r['title']}: {r['body']}\n  Source: {r['href']}"
                for r in source_rows
            ])
            
            # Step 2: Write the full report
            report_prompt = (
                f"Write a comprehensive, detailed research report on '{self.topic}' based on the following search results:\n"
                f"{raw_text}\n\n"
                "Format the report in markdown with headings and bullet points. "
                "Include a Sources section with the source URLs when available. "
                "If the topic is mechanical, electrical, automotive, or repair-related, include: "
                "overview, parts involved, likely diagrams/photos to look for, troubleshooting notes, safety notes, "
                "and a practical next-steps checklist."
            )
            full_report = self._call_llm(report_prompt)
            
            filepath = make_report_path(self.topic)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(full_report)
                
            # Step 3: Write a 1-2 sentence summary
            summary_prompt = f"Write a brief 1-2 sentence summary of this report:\n{full_report[:1500]}"
            summary = self._call_llm(summary_prompt)
            entry = record_report(self.topic, filepath, summary=summary, sources=source_rows)
            
            # Step 4: Drop it in the event queue
            message = (
                f"[SYSTEM NOTIFICATION] [RESEARCHER AGENT] I have finished researching '{self.topic}'. "
                f"Summary: {summary}. Research ID: {entry['id']}. "
                f"I saved the full detailed report at {filepath}. "
                "If Chris asks for details later, use list_research_reports, find_research_report, "
                "read_research_report, or find_research_images."
            )
            if self.event_queue:
                self.event_queue.put({"type": "system_trigger", "text": message})
                
            print(f"[ResearcherAgent] Finished research on: {self.topic}")
        except Exception as e:
            print(f"[ResearcherAgent] Fatal error: {e}")
            if self.event_queue:
                self.event_queue.put({"type": "system_trigger", "text": f"[SYSTEM NOTIFICATION] [RESEARCHER AGENT] I failed to research '{self.topic}' due to an error: {e}"})
