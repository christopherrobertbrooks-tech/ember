import threading
import time
import os
import subprocess
import glob

class MonitorAgent(threading.Thread):
    def __init__(self, event_queue, downloads_folder=None):
        super().__init__(daemon=True)
        self.event_queue = event_queue
        
        if downloads_folder and os.path.exists(downloads_folder):
            self.downloads_folder = downloads_folder
        else:
            self.downloads_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
            
        self.known_files = set(self._get_downloaded_files())
        self.last_temp_alert = 0
        
    def _get_downloaded_files(self):
        if not os.path.exists(self.downloads_folder):
            return []
        # Return files only, ignore directories
        return [f for f in glob.glob(os.path.join(self.downloads_folder, '*')) if os.path.isfile(f)]

    def _check_gpu(self):
        try:
            # Requires nvidia-smi to be in PATH
            output = subprocess.check_output(
                ['nvidia-smi', '--query-gpu=temperature.gpu,fan.speed,memory.used', '--format=csv,noheader,nounits'],
                stderr=subprocess.STDOUT, text=True
            ).strip().split(', ')
            
            if len(output) >= 3:
                temp = int(output[0])
                fan = output[1] # Could be "[Not Supported]" depending on laptop
                memory_used = int(output[2])
                
                # If GPU temp > 85C, alert (but debounce to avoid spamming)
                if temp > 85 and (time.time() - self.last_temp_alert > 300):
                    self.last_temp_alert = time.time()
                    if self.event_queue:
                        self.event_queue.put(("system_trigger", f"[SYSTEM NOTIFICATION] [URGENT] [SYSTEM MONITOR] The user's GPU temperature just spiked to {temp}°C! Mention this to them quickly, ask if they are rendering something heavy."))
        except FileNotFoundError:
            pass # nvidia-smi not available, likely not an NVIDIA GPU or not in PATH
        except Exception as e:
            print(f"[MonitorAgent] GPU Check Error: {e}")

    def _check_downloads(self):
        try:
            current_files = set(self._get_downloaded_files())
            new_files = current_files - self.known_files
            
            for file_path in new_files:
                filename = os.path.basename(file_path)
                # Ignore temp download files
                if not filename.endswith('.crdownload') and not filename.endswith('.part') and not filename.endswith('.tmp'):
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    if size_mb > 1.0: # Only alert for files larger than 1MB to avoid spam
                        if self.event_queue:
                            self.event_queue.put(("system_trigger", f"[SYSTEM NOTIFICATION] [SYSTEM MONITOR] The user just finished downloading a file named '{filename}' ({size_mb:.1f} MB). You can casually mention this!"))
            
            # Update known files, including any that were deleted
            self.known_files = current_files
        except Exception as e:
            print(f"[MonitorAgent] Download Check Error: {e}")

    def run(self):
        print(f"[MonitorAgent] Starting system monitor agent...")
        print(f"[MonitorAgent] Downloads path: {self.downloads_folder}")
        print(f"[MonitorAgent] Known files at launch: {len(self.known_files)}")
        print(f"[MonitorAgent] GPU monitoring: enabled (nvidia-smi)")
        print(f"[MonitorAgent] Poll interval: 10s")
        while True:
            self._check_gpu()
            self._check_downloads()
            time.sleep(10) # Poll every 10 seconds
