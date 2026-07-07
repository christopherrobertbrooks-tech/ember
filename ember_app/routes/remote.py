import asyncio
import platform
import subprocess

import psutil
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ember_app.auth import get_api_key
from ember_app.state import get_state
from tools.permission_gate import describe_permission_error, guard


router = APIRouter()


class RemoteActionRequest(BaseModel):
    action: str


@router.get("/system_info")
async def api_system_info(api_key: str = Depends(get_api_key)):
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        gpu_info = [{"name": gpu.name, "vram": int(gpu.memoryTotal), "vendor": "NVIDIA"} for gpu in gpus]
    except ImportError:
        gpu_info = []

    fan_info = []
    temp_info = []
    try:
        import wmi
        for ns in ["root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"]:
            try:
                w_sensors = wmi.WMI(namespace=ns)
                for sensor in w_sensors.Sensor():
                    if sensor.SensorType == "Fan":
                        fan_info.append({"name": sensor.Name, "value": float(sensor.Value)})
                    elif sensor.SensorType == "Temperature":
                        temp_info.append({"name": sensor.Name, "value": float(sensor.Value)})
                if fan_info or temp_info:
                    break
            except Exception:
                pass
    except Exception:
        pass

    return {
        "cpuLoad": psutil.cpu_percent(interval=0.1),
        "memUsed": psutil.virtual_memory().used,
        "memTotal": psutil.virtual_memory().total,
        "gpus": gpu_info,
        "fans": fan_info,
        "temperatures": temp_info,
    }


@router.post("/remote_action")
async def api_remote_action(request: RemoteActionRequest, api_key: str = Depends(get_api_key)):
    action = request.action
    try:
        category = "system_power" if action in {"lock", "sleep"} else "keyboard_mouse"
        guard(category, "remote_action", source="api", payload={"action": action})

        media_actions = {
            "play_pause": "playpause",
            "next_track": "next",
            "prev_track": "previous",
            "vol_up": "volume_up",
            "vol_down": "volume_down",
            "mute": "mute",
        }
        if action in media_actions:
            tool_payload = {"tool": "manage_media", "args": {"action": media_actions[action]}}
        elif action == "lock":
            tool_payload = {"tool": "lock_computer", "args": {}}
        elif action == "sleep":
            raise HTTPException(status_code=400, detail="Sleep is not supported for client remote actions yet.")
        else:
            return {"status": "error", "message": "Unknown action"}

        import requests

        client_url = get_state().engine.config.get("companion_client_url", "http://localhost:8002")
        res = requests.post(f"{client_url}/execute", json=tool_payload, timeout=10)
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Client worker error: {res.status_code}")
        data = res.json()
        if data.get("status") != "success":
            raise HTTPException(status_code=500, detail=data.get("output", "Client action failed"))
        return {"status": "ok", "message": data.get("output", "Client action completed.")}
    except Exception as e:
        raise HTTPException(status_code=403, detail=describe_permission_error(e))


@router.websocket("/ws/terminal")
async def ws_terminal(websocket: WebSocket):
    await websocket.accept()
    try:
        guard("terminal", "ws_terminal", source="api", payload={})
    except Exception:
        await websocket.send_text("Permission required before opening a terminal session.")
        await websocket.close(code=1008)
        return

    shell = "powershell.exe" if platform.system() == "Windows" else "bash"
    process = subprocess.Popen(
        shell,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
        universal_newlines=False,
    )

    async def read_stdout():
        try:
            while True:
                data = await asyncio.to_thread(process.stdout.read, 1024)
                if not data:
                    break
                await websocket.send_text(data.decode("utf-8", errors="replace"))
        except Exception:
            pass

    task = asyncio.create_task(read_stdout())
    try:
        while True:
            data = await websocket.receive_text()
            if process.poll() is not None:
                break
            await asyncio.to_thread(process.stdin.write, data.encode("utf-8"))
            await asyncio.to_thread(process.stdin.flush)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            process.terminate()
            task.cancel()
        except Exception:
            pass
