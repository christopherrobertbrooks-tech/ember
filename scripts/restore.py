import json
import re

log_path = r'C:\Users\futtb\.gemini\antigravity\brain\74671746-5c78-4458-b9d7-831b13f93d3c\.system_generated\logs\transcript.jsonl'
anim_lines = {}

def extract_str(d):
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, str) and 'AnimationManager' in v and 'vrm-mixamo-retarget' in v and 'The following code has been modified' in v:
                return v
            else:
                res = extract_str(v)
                if res: return res
    elif isinstance(d, list):
        for item in d:
            res = extract_str(item)
            if res: return res
    return None

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get('type') == 'TOOL_CALL_RESULT' or data.get('type') == 'TOOL_RESPONSE' or data.get('source') == 'SYSTEM':
                text = extract_str(data)
                if text:
                    for l in text.split('\n'):
                        m = re.match(r'^(\d+): (.*)', l)
                        if m:
                            anim_lines[int(m.group(1))] = m.group(2)
        except Exception as e:
            pass

if anim_lines:
    print(f"Extracted {len(anim_lines)} lines for AnimationManager!")
    with open(r'c:\project_ember\ember-desktop-client\src\utils\AnimationManager.js', 'w', encoding='utf-8') as f:
        for i in range(1, max(anim_lines.keys()) + 1):
            f.write(anim_lines.get(i, '') + '\n')
