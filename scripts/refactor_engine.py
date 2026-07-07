import os
import re

ENGINE_FILE = "ember_engine.py"

def refactor():
    with open(ENGINE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add helper method _call_llama_server
    helper_code = """
    def _call_llama_server(self, messages, stream=False, tools=None):
        import requests
        import json
        import base64
        
        # Format messages for OpenAI API (Vision support)
        formatted_messages = []
        for m in messages:
            msg_copy = {"role": m["role"]}
            
            if "images" in m and m["images"]:
                # Convert to OpenAI vision format
                content_arr = [{"type": "text", "text": m.get("content", "")}]
                for img_path in m["images"]:
                    try:
                        with open(img_path, "rb") as img_file:
                            b64_str = base64.b64encode(img_file.read()).decode('utf-8')
                        ext = os.path.splitext(img_path)[1][1:] or 'png'
                        content_arr.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{ext};base64,{b64_str}"}
                        })
                    except:
                        pass
                msg_copy["content"] = content_arr
            else:
                msg_copy["content"] = m.get("content", "")
                
            if "tool_calls" in m:
                msg_copy["tool_calls"] = m["tool_calls"]
            if "name" in m:
                msg_copy["name"] = m["name"]
                
            formatted_messages.append(msg_copy)

        payload = {
            "messages": formatted_messages,
            "stream": stream,
            "temperature": 0.7,
        }
        if tools:
            payload["tools"] = tools
            
        headers = {"Content-Type": "application/json"}
        try:
            if stream:
                res = requests.post(self.llama_server_url + "/chat/completions", json=payload, headers=headers, stream=True)
                res.raise_for_status()
                def generate():
                    for line in res.iter_lines():
                        if line:
                            line = line.decode('utf-8')
                            if line.startswith("data: "):
                                line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                data = json.loads(line)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta and delta["content"]:
                                        yield {"message": {"content": delta["content"]}}
                            except:
                                pass
                return generate()
            else:
                res = requests.post(self.llama_server_url + "/chat/completions", json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                if "choices" in data and len(data["choices"]) > 0:
                    msg = data["choices"][0].get("message", {})
                    # Ensure format matches what ollama returned
                    return {"message": msg}
                return {"message": {"content": ""}}
        except Exception as e:
            raise Exception(f"Llama Server error: {e}")
"""

    if "def _call_llama_server" not in content:
        # Insert it right before get_active_prompt
        content = content.replace("    def get_active_prompt(self):", helper_code + "\n    def get_active_prompt(self):")

    # 2. Update __init__ variables
    content = re.sub(
        r'self\.chat_model\s*=\s*self\.config\.get\("chat_model",.*?\)',
        r'self.llama_server_url = self.config.get("llama_server_url", "http://127.0.0.1:8080/v1")',
        content
    )
    content = re.sub(r'self\.tool_model\s*=\s*self\.config\.get\("tool_model",.*?\)\n', '', content)

    # 3. Replace ollama.chat calls
    
    # Tool models calls
    content = content.replace(
        "res = ollama.chat(model=self.tool_model, messages=messages_for_llm, stream=False, tools=tools)",
        "res = self._call_llama_server(messages=messages_for_llm, stream=False, tools=tools)"
    )
    content = content.replace(
        "res = ollama.chat(model=self.tool_model, messages=messages_for_llm, stream=False)",
        "res = self._call_llama_server(messages=messages_for_llm, stream=False)"
    )
    
    # Native tool check update (since we use llama-server, we ALWAYS support native tools)
    content = content.replace(
        "supports_native_tools = any(tm in self.tool_model.lower() for tm in native_tool_models)",
        "supports_native_tools = True"
    )
    
    # Vision models check update (Llama 3.2 11B Vision ALWAYS supports vision)
    content = content.replace(
        'vision_models = ["llava", "vision", "vl", "gemma"]\n                        if any(v in self.tool_model.lower() or v in self.chat_model.lower() for v in vision_models):',
        'if True: # Llama 3.2 11B Vision natively supports vision'
    )
    
    # Chat model stream call
    content = content.replace(
        "yield from stream_processor(ollama.chat(model=self.chat_model, messages=sanitized_messages, stream=True))",
        "yield from stream_processor(self._call_llama_server(messages=sanitized_messages, stream=True))"
    )
    
    # Generate image enhance call
    content = content.replace(
        "enhance_response = ollama.chat(model=self.model, messages=enhance_messages, keep_alive=0)",
        "enhance_response = self._call_llama_server(messages=enhance_messages, stream=False)"
    )

    with open(ENGINE_FILE, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Refactor complete.")

if __name__ == "__main__":
    refactor()
