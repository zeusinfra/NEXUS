import psutil
import os
from datetime import datetime

def run():
    """
    Skill: System Guardian
    Monitora a saúde do sistema de forma orgânica e identifica gargalos.
    """
    report = []
    report.append(f"🛡️ [SYSTEM GUARDIAN] Auditoria de Ciclo de Vida - {datetime.now().strftime('%H:%M:%S')}")
    
    # 1. CPU & RAM
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    report.append(f"📊 Carga: CPU {cpu}% | RAM {ram}%")
    
    # 2. Diagnóstico de Pressão
    if ram > 80:
        report.append("⚠️ [ALERTA] Pressão de RAM detectada. Identificando culpados...")
        procs = sorted(psutil.process_iter(['name', 'memory_percent']), 
                       key=lambda x: x.info['memory_percent'], reverse=True)[:3]
        for p in procs:
            report.append(f"   - {p.info['name']}: {p.info['memory_percent']:.1f}%")
            
    # 3. Disco (Raiz)
    disk = psutil.disk_usage('/')
    report.append(f"💾 Disco: {disk.percent}% ocupado ({disk.free / (1024**3):.1f}GB livres)")
    
    # 4. Sinapse de Saúde
    status = "OPTIMAL" if ram < 70 and cpu < 50 else "STRESSED"
    report.append(f"✨ Estado Vital: {status}")
    
    return "\n".join(report)
