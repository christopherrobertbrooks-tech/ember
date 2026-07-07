import requests
import os

def download_model():
    url = "https://huggingface.co/bartowski/Llama-3.2-11B-Vision-Instruct-GGUF/resolve/main/Llama-3.2-11B-Vision-Instruct-Q4_K_M.gguf"
    dest = os.path.join("Llama Models", "Llama-3.2-11B-Vision-Instruct-Q4_K_M.gguf")
    
    print(f"Downloading {url} to {dest}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192*1024):
                f.write(chunk)
                
        print("Download complete!")
    except Exception as e:
        print(f"Error downloading: {e}")

if __name__ == "__main__":
    download_model()
