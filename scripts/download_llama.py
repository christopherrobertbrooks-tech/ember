import requests
import zipfile
import os
import io

def download_llama():
    print("Fetching latest release info from llama.cpp...")
    api_url = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        target_asset = None
        for asset in data.get('assets', []):
            name = asset['name'].lower()
            if 'win' in name and 'cuda' in name and 'x64' in name and name.endswith('.zip') and 'cudart' not in name:
                target_asset = asset
                break
                
        if not target_asset:
            # Fallback to older cu11 or just any cuda if cu12.2 isn't exactly matched
            for asset in data.get('assets', []):
                name = asset['name'].lower()
                if 'win' in name and ('cuda' in name or 'cu12' in name) and name.endswith('.zip'):
                    target_asset = asset
                    break

        if not target_asset:
            print("Could not find a Windows CUDA release in the latest assets.")
            return

        download_url = target_asset['browser_download_url']
        print(f"Downloading {target_asset['name']}...")
        
        zip_resp = requests.get(download_url, stream=True)
        zip_resp.raise_for_status()
        
        print("Extracting...")
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as z:
            z.extractall("llama_cpp_bin")
            
        print("Done! llama-server.exe should be in the llama_cpp_bin folder.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    download_llama()
