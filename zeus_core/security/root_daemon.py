import asyncio
import json
import os
import subprocess
from typing import Dict, Any, Callable

SOCKET_PATH = "/tmp/zeus_root_daemon.sock"

# ==========================================
# SECURE METHODS (ALLOWLIST)
# ==========================================

def _run_shell(cmd: list) -> Dict[str, Any]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def get_system_health(**kwargs) -> Dict[str, Any]:
    return _run_shell(["uptime"])

async def get_service_status(service_name: str, **kwargs) -> Dict[str, Any]:
    if not service_name.isalnum() and "_" not in service_name and "-" not in service_name:
        return {"status": "error", "message": "Invalid service name"}
    return _run_shell(["systemctl", "status", service_name])

async def restart_zeus_service(**kwargs) -> Dict[str, Any]:
    return _run_shell(["systemctl", "restart", "zeus"])

async def reload_zeus_service(**kwargs) -> Dict[str, Any]:
    return _run_shell(["systemctl", "reload", "zeus"])

async def apt_update(**kwargs) -> Dict[str, Any]:
    return _run_shell(["apt-get", "update"])

async def list_upgradable_packages(**kwargs) -> Dict[str, Any]:
    return _run_shell(["apt", "list", "--upgradable"])

async def read_limited_journal(service_name: str, **kwargs) -> Dict[str, Any]:
    if not service_name.isalnum() and "_" not in service_name and "-" not in service_name:
        return {"status": "error", "message": "Invalid service name"}
    return _run_shell(["journalctl", "-u", service_name, "-n", "50", "--no-pager"])

async def execute_safe_command(command: str, **kwargs) -> Dict[str, Any]:
    """Fallback method for specific allowed read-only or low-risk commands sent by the broker."""
    # This acts as an extra layer of validation on top of SudoBroker.
    # We strictly enforce only certain prefixes here.
    ALLOWED_PREFIXES = ["systemctl status", "journalctl", "df", "free", "uptime", "ps", "lsblk", "lscpu", "apt update"]
    if not any(command.startswith(p) for p in ALLOWED_PREFIXES):
        return {"status": "error", "message": "Command rejected by RootDaemon strict policy."}
    
    # Split using shlex for safety, but for simplicity here we just use shell=True (DANGEROUS if not controlled).
    # Since we are strictly validating prefixes and it's from our broker, we use it carefully.
    # In a production environment, use shlex.split() and avoid shell=True.
    import shlex
    try:
        args = shlex.split(command)
        return _run_shell(args)
    except Exception as e:
         return {"status": "error", "message": str(e)}

# Registry
DISPATCH_TABLE: Dict[str, Callable] = {
    "get_system_health": get_system_health,
    "get_service_status": get_service_status,
    "restart_zeus_service": restart_zeus_service,
    "reload_zeus_service": reload_zeus_service,
    "apt_update": apt_update,
    "list_upgradable_packages": list_upgradable_packages,
    "read_limited_journal": read_limited_journal,
    "execute_safe_command": execute_safe_command
}

# ==========================================
# SERVER
# ==========================================

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        data = await reader.readline()
        if not data:
            return
            
        payload = json.loads(data.decode().strip())
        action = payload.get("action")
        kwargs = payload.get("kwargs", {})
        
        if action in DISPATCH_TABLE:
            handler = DISPATCH_TABLE[action]
            response = await handler(**kwargs)
        else:
            response = {"status": "error", "message": f"Unknown action: {action}"}
            
        writer.write(json.dumps(response).encode() + b'\n')
        await writer.drain()
    except Exception as e:
        error_resp = {"status": "error", "message": f"Daemon error: {str(e)}"}
        writer.write(json.dumps(error_resp).encode() + b'\n')
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    # Remove socket se existir
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
        
    server = await asyncio.start_unix_server(handle_client, path=SOCKET_PATH)
    
    # Define permissões restritas no socket (Apenas o usuário root/zeus pode ler/escrever)
    # Na prática, se rodar como root, zeus precisa estar no grupo certo ou socket precisa de chmod 660 + chown.
    os.chmod(SOCKET_PATH, 0o666) # Temporário: permitir qualquer local user testar. Em prod: 0o660
    
    print(f"RootDaemon listening on {SOCKET_PATH}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    # Ensure this is run as root
    # if os.geteuid() != 0:
    #     print("RootDaemon must be run as root!")
    #     exit(1)
    asyncio.run(main())
