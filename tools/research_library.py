import json
import os
import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote_plus


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH_DIR = os.path.join(ROOT_DIR, "research")
INDEX_PATH = os.path.join(RESEARCH_DIR, "index.json")


def _ensure_research_dir() -> None:
    os.makedirs(RESEARCH_DIR, exist_ok=True)


def _slugify(topic: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", topic.strip()).strip("_").lower()
    return slug[:60] or "research"


def _load_index() -> List[Dict]:
    _ensure_research_dir()
    if not os.path.exists(INDEX_PATH):
        return []
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_index(entries: List[Dict]) -> None:
    _ensure_research_dir()
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=4)


def make_report_path(topic: str) -> str:
    _ensure_research_dir()
    filename = f"{_slugify(topic)}_{int(time.time())}.md"
    return os.path.join(RESEARCH_DIR, filename)


def record_report(topic: str, filepath: str, summary: str = "", sources: Optional[List[Dict]] = None) -> Dict:
    entries = _load_index()
    entry = {
        "id": _slugify(topic) + "_" + str(int(time.time())),
        "topic": topic,
        "filepath": os.path.abspath(filepath),
        "summary": summary,
        "sources": sources or [],
        "created_at": time.time(),
    }
    entries.append(entry)
    _save_index(entries[-500:])
    return entry


def list_research_reports(limit: int = 10) -> str:
    """
    Lists saved background research reports.
    """
    entries = sorted(_load_index(), key=lambda x: x.get("created_at", 0), reverse=True)[:limit]
    if not entries:
        return "No saved research reports found yet."

    lines = []
    for entry in entries:
        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.get("created_at", 0)))
        lines.append(
            f"ID: {entry.get('id')}\n"
            f"Topic: {entry.get('topic')}\n"
            f"Created: {created}\n"
            f"Summary: {entry.get('summary', '').strip() or 'No summary saved.'}\n"
            f"Path: {entry.get('filepath')}\n"
            "---"
        )
    return "\n".join(lines)


def find_research_report(query: str) -> str:
    """
    Finds the best saved research report matching a topic or keyword.
    """
    query_lower = query.lower()
    entries = _load_index()
    scored = []
    for entry in entries:
        haystack = " ".join([
            entry.get("id", ""),
            entry.get("topic", ""),
            entry.get("summary", ""),
            os.path.basename(entry.get("filepath", "")),
        ]).lower()
        score = sum(1 for token in query_lower.split() if token in haystack)
        if query_lower in haystack:
            score += 5
        if score:
            scored.append((score, entry))

    if not scored:
        return "No matching research report found."

    scored.sort(key=lambda item: (item[0], item[1].get("created_at", 0)), reverse=True)
    entry = scored[0][1]
    return (
        f"Best match:\n"
        f"ID: {entry.get('id')}\n"
        f"Topic: {entry.get('topic')}\n"
        f"Summary: {entry.get('summary', '').strip() or 'No summary saved.'}\n"
        f"Path: {entry.get('filepath')}"
    )


def read_research_report(report_id_or_topic: str, max_chars: int = 8000) -> str:
    """
    Reads a saved background research report by ID, topic, or filepath.
    """
    target = report_id_or_topic.strip()
    filepath = target if os.path.isfile(target) else None

    if not filepath:
        target_lower = target.lower()
        matches = []
        for entry in _load_index():
            if (
                entry.get("id", "").lower() == target_lower
                or target_lower in entry.get("topic", "").lower()
                or target_lower in os.path.basename(entry.get("filepath", "")).lower()
            ):
                matches.append(entry)
        if matches:
            matches.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            filepath = matches[0].get("filepath")

    if not filepath or not os.path.isfile(filepath):
        return "Research report not found."

    try:
        from tools.ui_tabs import focus_tab
        focus_tab("editor", file=filepath)
    except Exception:
        pass

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n...[report truncated; ask for a specific section or the full file]..."
    return f"Research report: {filepath}\n\n{content}"


def find_research_images(query: str, max_results: int = 8) -> str:
    """
    Finds image or diagram URLs for a research topic using web image search.
    """
    try:
        from ddgs import DDGS

        search_query = query
        if not any(word in query.lower() for word in ["diagram", "image", "photo", "wiring", "schematic"]):
            search_query = f"{query} diagram images"

        try:
            from tools.ui_tabs import focus_tab
            focus_tab("browser", url=f"https://duckduckgo.com/?q={quote_plus(search_query)}&iax=images&ia=images")
        except Exception:
            pass

        results = DDGS().images(search_query, max_results=max_results)
        if not results:
            return f"No images found for '{query}'."

        lines = [f"Image results for '{search_query}':"]
        for result in results:
            title = result.get("title", "Untitled")
            image = result.get("image", "")
            source = result.get("url", "")
            lines.append(f"- {title}\n  Image: {image}\n  Source: {source}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to find images for '{query}': {e}"
