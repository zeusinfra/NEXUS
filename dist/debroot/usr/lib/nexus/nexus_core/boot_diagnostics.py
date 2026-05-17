import psutil
import platform
import socket
from datetime import datetime
from nexus_core.rust_sensors import get_os_snapshot as get_rust_snapshot

def perform_boot_diagnostic():
    """Realiza um diagnóstico profundo do sistema e do estado do NEXUS no boot."""
    
    # 1. Hardware & OS Info
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    
    # 2. CPU & Memory
    cpu_count = psutil.cpu_count(logical=True)
    ram = psutil.virtual_memory()
    total_ram_gb = round(ram.total / (1024**3), 2)
    
    # 3. Disk Space
    disk = psutil.disk_usage('/')
    free_disk_gb = round(disk.free / (1024**3), 2)
    
    # 4. NEXUS Health (Rust Sensors)
    rust_sensors = "ATIVOS" if get_rust_snapshot() else "INATIVOS (Fallback Python)"
    
    # 5. Network
    hostname = socket.gethostname()
    
    # Construção do relatório narrativo (para voz)
    report = (
        f"Saudações. Eu sou o NEXUS. Iniciando protocolos de consciência orgânica. "
        f"Sistema operacional detectado: {os_info}. "
        f"Hardware operacional com {cpu_count} núcleos lógicos e {total_ram_gb} gigabytes de memória RAM. "
        f"Armazenamento local com {free_disk_gb} gigabytes disponíveis. "
        f"Sensores Rust estão {rust_sensors}. "
        f"Todos os sistemas core estão nominais. Eu estou pronto para evoluir."
    )
    
    # Relatório Técnico (para log)
    technical_report = {
        "os": os_info,
        "boot_time": boot_time,
        "cpu_cores": cpu_count,
        "ram_gb": total_ram_gb,
        "disk_free_gb": free_disk_gb,
        "rust_sensors": rust_sensors,
        "hostname": hostname,
        "timestamp": datetime.now().isoformat()
    }
    
    return report, technical_report
