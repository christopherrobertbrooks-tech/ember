import json
import re


def extract_manual_tool_calls(text):
    """Recover tool calls if a model prints JSON instead of invoking tools."""
    if not text or not isinstance(text, str):
        return []

    cleaned = text.strip()
    blocks = re.findall(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    candidates = blocks or [cleaned]
    if "[" in cleaned and "]" in cleaned:
        candidates.append(cleaned[cleaned.find("["):cleaned.rfind("]") + 1])
    if "{" in cleaned and "}" in cleaned:
        candidates.append(cleaned[cleaned.find("{"):cleaned.rfind("}") + 1])

    found = []

    # 1. Check for specific local model toolcall formats like <|toolcall>call:name{key:<|"|>value<|"|>,...}<toolcall|>
    toolcall_matches = re.finditer(r"<\|toolcall>call:([^\{]+)\{(.*?)\}<toolcall\|>", cleaned, re.IGNORECASE)
    for match in toolcall_matches:
        raw_name = match.group(1).strip()
        args_str = match.group(2).strip()
        
        # Extract arguments using the <|"|> wrapper
        args_dict = {}
        arg_matches = re.finditer(r"([a-zA-Z0-9_]+):<\|\"\|>(.*?)<\|\"\|>", args_str)
        for am in arg_matches:
            args_dict[am.group(1)] = am.group(2)
            
        if raw_name:
            found.append({"name": raw_name, "arguments": args_dict})
            
    # 2. Check for other similar toolcall formats without the <|"|> wrappers but still in {}
    toolcall_simple_matches = re.finditer(r"<\|toolcall>call:([^\{]+)\{(.*?)\}<toolcall\|>", cleaned, re.IGNORECASE)
    for match in toolcall_simple_matches:
        raw_name = match.group(1).strip()
        # if we already found it above, skip
        if any(f["name"] == raw_name for f in found):
            continue
        # very naive fallback if <|"|> wasn't used
        if "<|\"|>" not in match.group(2):
            try:
                # Try to parse the inner string as JSON if it is JSON-like, otherwise ignore or handle custom
                # Usually if it doesn't have <|"|>, it might just be raw JSON
                inner = "{" + match.group(2) + "}"
                args_dict = json.loads(inner)
                found.append({"name": raw_name, "arguments": args_dict})
            except Exception:
                pass

    def collect(value):
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            if "function" in value and isinstance(value["function"], dict):
                fn = value["function"]
                name = fn.get("name")
                args = fn.get("arguments", {})
                if name:
                    found.append({"name": name, "arguments": args})
            elif "name" in value:
                name = value.get("name")
                args = value.get("arguments")
                if args is None:
                    args = {k: v for k, v in value.items() if k not in {"name", "content"}}
                if name:
                    found.append({"name": name, "arguments": args})

    for candidate in candidates:
        candidate = candidate.strip()
        if not (candidate.startswith("[") or candidate.startswith("{")):
            continue
        try:
            collect(json.loads(candidate))
        except Exception:
            continue

    deduped = []
    seen = set()
    for call in found:
        key = json.dumps(call, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            deduped.append(call)
    return deduped
