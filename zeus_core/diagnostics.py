import psutil
import time
import socket
import platform
import subprocess
from typing import Dict, Any

def get_system_diagnostics() -> Dict[str, Any]:
    """
    Collects comprehensive system diagnostics.
    """
    # CPU
    cpu_usage = psutil.cpu_percent(interval=0.1, percpu=True)
    cpu_avg = sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0
    
    # Try to get temperature (Linux only usually)
    cpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            cpu_temp = temps['coretemp'][0].current
        elif 'cpu_thermal' in temps:
            cpu_temp = temps['cpu_thermal'][0].current
    except Exception:
        pass

    # RAM
    ram = psutil.virtual_memory()
    
    # Disk
    disk = psutil.disk_usage('/')
    
    # Network Latency (lite check)
    latency = {}
    targets = [("Google", "8.8.8.8"), ("Local", "127.0.0.1")]
    for name, ip in targets:
        try:
            start = time.perf_counter()
            socket.create_connection((ip, 53), timeout=1)
            latency[name] = f"{round((time.perf_counter() - start) * 1000, 2)}ms"
        except Exception:
            latency[name] = "timeout"

    # OS Info
    os_info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor()
    }

    return {
        "cpu": {
            "usage_per_core": cpu_usage,
            "avg_usage": f"{round(cpu_avg, 1)}%",
            "temperature": f"{cpu_temp}°C" if cpu_temp else "N/A"
        },
        "memory": {
            "total": f"{round(ram.total / (1024**3), 2)}GB",
            "available": f"{round(ram.available / (1024**3), 2)}GB",
            "percent": f"{ram.percent}%"
        },
        "disk": {
            "total": f"{round(disk.total / (1024**3), 2)}GB",
            "used": f"{round(disk.used / (1024**3), 2)}GB",
            "free": f"{round(disk.free / (1024**3), 2)}GB",
            "percent": f"{disk.percent}%"
        },
        "network": latency,
        "os": os_info,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

if __name__ == "__main__":
    import json
    print(json.dumps(get_system_diagnostics(), indent=2))
