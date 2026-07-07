import os
import time
import json
import uuid
from typing import List, Dict
import requests

INGEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ingest"))
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ember_config.json"))

try:
    import PyPDF2
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

class IngestionAgent:
    def __init__(self):
        self.config = self._load_config()
        self.chroma_url = self.config.get("chroma_server_url", "http://127.0.0.1:8001")
        print(f"[IngestionAgent] Starting ingestion agent...")
        print(f"[IngestionAgent] Watching folder: {INGEST_DIR}")
        print(f"[IngestionAgent] ChromaDB URL: {self.chroma_url}")
        print(f"[IngestionAgent] PDF support: {'enabled' if HAS_PYPDF else 'disabled (install PyPDF2)'}")
        
    def _load_config(self) -> dict:
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except:
            return {}

    def extract_text(self, filepath: str) -> str:
        text = ""
        ext = filepath.lower().split('.')[-1]
        
        if ext in ['txt', 'md', 'json', 'csv', 'py', 'js', 'html']:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    text = f.read()
            except Exception as e:
                print(f"[IngestionAgent] Error reading text file {filepath}: {e}")
        elif ext == 'pdf' and HAS_PYPDF:
            try:
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as e:
                print(f"[IngestionAgent] Error reading PDF {filepath}: {e}")
        elif ext == 'pdf' and not HAS_PYPDF:
            print("[IngestionAgent] Skipping PDF: PyPDF2 is not installed. (pip install PyPDF2)")
        
        return text

    def chunk_text(self, text: str, chunk_size=500, overlap=50) -> List[str]:
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
        return chunks

    def ingest_to_chroma(self, filename: str, chunks: List[str]):
        if not chunks:
            return
            
        print(f"[IngestionAgent] Sending {len(chunks)} chunks from {filename} to Hive Mind (ChromaDB)...")
        
        try:
            # We must use the Chroma HTTP API directly to insert, or we can use the python client if installed
            import chromadb
            client = chromadb.HttpClient(host=self.chroma_url.split("://")[1].split(":")[0], port=int(self.chroma_url.split(":")[2]))
            collection = client.get_or_create_collection(name="documents")
            
            ids = [str(uuid.uuid4()) for _ in chunks]
            metadatas = [{"source": filename} for _ in chunks]
            
            collection.add(
                documents=chunks,
                metadatas=metadatas,
                ids=ids
            )
            print(f"[IngestionAgent] Successfully ingrained '{filename}' into memory!")
        except Exception as e:
            print(f"[IngestionAgent] ChromaDB insertion failed: {e}")

    def run(self):
        # Keeps track of files we've already ingested this session
        # (In a production system, this would move them to a 'processed' folder)
        processed = set()
        
        while True:
            try:
                for file in os.listdir(INGEST_DIR):
                    if file not in processed:
                        filepath = os.path.join(INGEST_DIR, file)
                        if os.path.isfile(filepath):
                            print(f"[IngestionAgent] New file detected: {file}")
                            text = self.extract_text(filepath)
                            
                            if text.strip():
                                chunks = self.chunk_text(text)
                                self.ingest_to_chroma(file, chunks)
                            else:
                                print(f"[IngestionAgent] No extractable text found in {file}.")
                            
                            processed.add(file)
            except Exception as e:
                print(f"[IngestionAgent] Scan error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    agent = IngestionAgent()
    agent.run()
