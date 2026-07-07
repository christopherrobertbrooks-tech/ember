import requests
import os

def download_kobold():
    print("Fetching latest release info from KoboldCPP...")
    api_url = "https://api.github.com/repos/LostRuins/koboldcpp/releases/latest"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        target_asset = None
        for asset in data.get('assets', []):
            name = asset['name'].lower()
            if name == 'koboldcpp.exe':
                target_asset = asset
                break

        if not target_asset:
            print("Could not find koboldcpp.exe in the latest release.")
            return

        download_url = target_asset['browser_download_url']
        print(f"Downloading {target_asset['name']}...")
        
        exe_resp = requests.get(download_url, stream=True)
        exe_resp.raise_for_status()
        
        with open("koboldcpp.exe", "wb") as f:
            for chunk in exe_resp.iter_content(chunk_size=8192):
                f.write(chunk)
            
        print("Done! koboldcpp.exe downloaded.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    download_kobold()
