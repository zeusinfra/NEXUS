"""
NEXUS RootDaemon — Único processo privilegiado do sistema.

Roda via systemd. Socket Unix 0660. Sem endpoint HTTP público.
Aceita comando cru livre com blocklist de segurança.

Protocolo JSON line-delimited sobre Unix socket:

Request:
    {"action": "execute", "command": "...", "reason": "...", "context": {...}}
    {"action": "backup", "paths": [...]}
    {"action": "rollback", "backup_id": "..."}
    {"action": "audit_tail", "n": 50}
    {"action": "list_backups"}

Response:
    {"status": "success|blocked|requires_approval|error", ...}
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Risk levels
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    FORBIDDEN = "FORBIDDEN"


# ---------------------------------------------------------------------------
# Blocklist — NUNCA executar automaticamente
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Destruição total do filesystem
    (re.compile(r"\brm\s+.*-r.*\s+/\s*$|rm\s+.*-r.*\s+/\*"), "rm -rf / ou /*"),
    (re.compile(r"\brm\s+--no-preserve-root"), "rm --no-preserve-root"),
    # Escrita direta em disco / formatação
    (re.compile(r"\bdd\b\s+"), "dd — escrita direta em disco"),
    (re.compile(r"\bmkfs\b"), "mkfs — formatação de disco"),
    (re.compile(r"\bshred\b"), "shred — destruição irreversível"),
    (re.compile(r"\bwipefs\b"), "wipefs — apagar filesystem signatures"),
    # Mount / umount
    (re.compile(r"\bmount\b"), "mount — montar filesystem"),
    (re.compile(r"\bumount\b"), "umount — desmontar filesystem"),
    # Alteração de usuários / grupos
    (re.compile(r"\buseradd\b|\buserdel\b|\busermod\b"), "alteração de usuários"),
    (re.compile(r"\bgroupadd\b|\bgroupdel\b|\bgroupmod\b"), "alteração de grupos"),
    (re.compile(r"\bpasswd\b"), "alteração de senha"),
    (re.compile(r"\bchpasswd\b"), "alteração de senha em lote"),
    (re.compile(r"\bvisudo\b"), "edição de sudoers"),
    (re.compile(r"/etc/sudoers"), "acesso a /etc/sudoers"),
    # Firewall sem aprovação
    (re.compile(r"\bufw\b"), "ufw — firewall"),
    (re.compile(r"\biptables\b"), "iptables — firewall"),
    (re.compile(r"\bnftables\b|\bnft\b"), "nftables — firewall"),
    # Shutdown / reboot
    (
        re.compile(r"\bshutdown\b|\breboot\b|\bpoweroff\b|\bhalt\b"),
        "interrupção do sistema",
    ),
    # Permissões perigosas
    (re.compile(r"\bchmod\b.*\b777\b.*\s+/"), "chmod 777 no root"),
    (re.compile(r"\bchown\b.*-R\b.*\s+/"), "chown -R no root"),
]

# Comandos READ_ONLY conhecidos
READ_ONLY_COMMANDS = {
    "ls",
    "pwd",
    "echo",
    "cat",
    "head",
    "tail",
    "wc",
    "file",
    "stat",
    "find",
    "rg",
    "grep",
    "awk",
    "sed",
    "df",
    "free",
    "uptime",
    "lscpu",
    "lsblk",
    "lspci",
    "lsusb",
    "ip",
    "ss",
    "hostname",
    "uname",
    "whoami",
    "id",
    "groups",
    "systemctl",
    "journalctl",
    "ps",
    "top",
    "htop",
    "neofetch",
    "dpkg",
    "apt",
    "git",
    "python3",
    "node",
    "npm",
    "cargo",
    "date",
    "cal",
    "which",
    "whereis",
    "type",
    "env",
    "printenv",
}

# Comandos de serviço permitidos explicitamente
SERVICE_COMMANDS = {"restart", "status", "stop", "start", "reload"}
NEXUS_SERVICES = {"nexus-core", "nexus-root-daemon", "nexus-gtk-chat", "nexus"}

# Subcomandos que tornam um comando read-only em escrita
WRITE_SUBCOMMANDS = {
    "apt": {
        "install",
        "remove",
        "purge",
        "upgrade",
        "dist-upgrade",
        "autoremove",
        "full-upgrade",
    },
    "dpkg": {"-i", "--install", "-r", "--remove", "-P", "--purge"},
    "systemctl": {
        "start",
        "stop",
        "restart",
        "enable",
        "disable",
        "mask",
        "unmask",
        "reload",
    },
    "git": {"push", "commit", "merge", "rebase", "reset", "checkout", "branch", "tag"},
    "pip": {"install", "uninstall"},
    "pip3": {"install", "uninstall"},
    "npm": {"install", "i", "uninstall", "link", "run", "exec", "start", "test"},
    "cargo": {"build", "run", "test", "install", "publish"},
}

# Allowlist de pacotes apt permitidos
APT_ALLOWLIST_DEFAULT = (
    "build-essential,python3-dev,python3-pip,python3-venv,git,curl,wget,"
    "htop,neofetch,ffmpeg,jq,tree,ripgrep,fd-find,bat,tmux,vim,nano,"
    "libgtk-4-dev,libadwaita-1-dev,gir1.2-adw-1,gir1.2-gtk-4.0,"
    "tesseract-ocr,tesseract-ocr-por,fonts-inter,fonts-jetbrains-mono"
)

# Caminhos permitidos para edição
ALLOWED_EDIT_PATHS_DEFAULT = (
    "/home/zeus/Documentos/ZEUS_SYSTEM,/home/zeus/Documentos/Brain,/tmp/nexus_"
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _get_socket_path() -> str:
    return os.getenv("NEXUS_DAEMON_SOCKET", "/tmp/nexus/daemon.sock")


def _get_approval_socket_path() -> str:
    return os.getenv("NEXUS_DAEMON_APPROVAL_SOCKET", "/tmp/nexus/approval.sock")


def _get_vault_path() -> str:
    return os.getenv("NEXUS_VAULT_PATH", "/home/zeus/Documentos/Brain")


def _get_autonomy_level() -> str:
    return os.getenv("NEXUS_AUTONOMY_LEVEL", "GUARDED").upper()


def _get_apt_allowlist() -> set[str]:
    raw = os.getenv("NEXUS_APT_ALLOWLIST", APT_ALLOWLIST_DEFAULT)
    return {p.strip() for p in raw.split(",") if p.strip()}


def _get_allowed_edit_paths() -> list[str]:
    raw = os.getenv("NEXUS_ALLOWED_EDIT_PATHS", ALLOWED_EDIT_PATHS_DEFAULT)
    return [p.strip() for p in raw.split(",") if p.strip()]


def _get_backup_root() -> Path:
    return Path(_get_vault_path()) / "backups" / "daemon"


def _get_audit_path() -> Path:
    return Path(_get_vault_path()) / "logs" / "daemon_audit.jsonl"


# ---------------------------------------------------------------------------
# Risk Classifier (absorvido do antigo SudoBroker)
# ---------------------------------------------------------------------------


def classify_risk(command: str) -> tuple[RiskLevel, str]:
    """Classifica o risco de um comando. Retorna (nível, motivo)."""
    cmd = command.strip()
    cmd_lower = cmd.lower()

    # 1. Blocklist — FORBIDDEN
    for pattern, reason in FORBIDDEN_PATTERNS:
        if pattern.search(cmd_lower):
            return RiskLevel.FORBIDDEN, reason

    # 2. Verificar se é edição fora dos caminhos permitidos
    # Detecta redirecionamento para arquivo ou tee
    if ">" in cmd or "tee " in cmd_lower:
        allowed_paths = _get_allowed_edit_paths()
        # Tenta extrair o path de destino
        parts = cmd.split(">")
        if len(parts) > 1:
            dest = parts[-1].strip().split()[0] if parts[-1].strip() else ""
            if dest and not any(dest.startswith(p) for p in allowed_paths):
                return (
                    RiskLevel.FORBIDDEN,
                    f"edição fora dos caminhos permitidos: {dest}",
                )

    # 3. Extrair executável base
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()

    if not tokens:
        return RiskLevel.READ_ONLY, "comando vazio"

    exe = Path(tokens[0]).name

    # 4. Verificar apt install com allowlist
    if exe in ("apt", "apt-get") and len(tokens) > 1:
        subcmd = tokens[1]
        if subcmd == "install":
            allowlist = _get_apt_allowlist()
            packages = [t for t in tokens[2:] if not t.startswith("-")]
            for pkg in packages:
                if pkg not in allowlist:
                    return RiskLevel.FORBIDDEN, f"pacote fora da allowlist: {pkg}"
            return RiskLevel.MEDIUM_RISK, "apt install (pacotes na allowlist)"
        if subcmd in ("update", "list"):
            return RiskLevel.READ_ONLY, f"apt {subcmd}"
        if subcmd in WRITE_SUBCOMMANDS.get("apt", set()):
            return RiskLevel.MEDIUM_RISK, f"apt {subcmd}"

    # 5. Verificar subcomandos de escrita
    if exe in WRITE_SUBCOMMANDS and len(tokens) > 1:
        subcmd = tokens[1]
        if subcmd in WRITE_SUBCOMMANDS[exe]:
            return RiskLevel.MEDIUM_RISK, f"{exe} {subcmd}"

    # 6. READ_ONLY conhecido
    if exe in READ_ONLY_COMMANDS:
        return RiskLevel.READ_ONLY, "comando read-only"

    # 7. Comandos com sudo
    if exe == "sudo":
        return RiskLevel.HIGH_RISK, "elevação de privilégio com sudo"

    # 8. Shell pipes/chains
    if any(tok in cmd for tok in ["|", "&&", "||", ";", "$(", "`"]):
        return RiskLevel.MEDIUM_RISK, "encadeamento de comandos"

    # 9. Default: HIGH_RISK para desconhecidos
    return RiskLevel.HIGH_RISK, "comando não classificado"


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Grava eventos de auditoria em JSONL."""

    def __init__(self):
        self._path = _get_audit_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        command: str,
        risk: RiskLevel,
        status: str,
        reason: str,
        caller: str = "unknown",
        extra: dict | None = None,
    ) -> None:
        entry = {
            "ts": datetime.datetime.now().isoformat(),
            "command": command,
            "risk": risk.value,
            "status": status,
            "reason": reason,
            "caller": caller,
        }
        if extra:
            entry.update(extra)
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[RootDaemon][AuditLogger] Erro: {e}")

    def tail(self, n: int = 50) -> list[dict]:
        """Retorna as últimas N entradas."""
        try:
            lines = self._path.read_text(encoding="utf-8").strip().splitlines()
            return [json.loads(line) for line in lines[-n:]]
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Backup Manager (integrado ao daemon)
# ---------------------------------------------------------------------------


class BackupManager:
    """Gerencia backups antes de ações de escrita."""

    def __init__(self):
        self._root = _get_backup_root()
        self._root.mkdir(parents=True, exist_ok=True)

    def create(self, paths: list[str]) -> str:
        """Cria backup dos arquivos. Retorna backup_id."""
        backup_id = (
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            + "_"
            + uuid.uuid4().hex[:6]
        )
        target_dir = self._root / backup_id
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "id": backup_id,
            "ts": datetime.datetime.now().isoformat(),
            "files": [],
        }

        for path_str in paths:
            src = Path(path_str)
            if src.exists() and src.is_file():
                try:
                    rel = src.relative_to("/")
                except ValueError:
                    rel = Path(src.name)
                dest = target_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                manifest["files"].append(
                    {
                        "original": str(src),
                        "backup": str(dest),
                        "size": src.stat().st_size,
                    }
                )

        # Salvar manifest
        (target_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return backup_id

    def restore(self, backup_id: str) -> dict:
        """Restaura backup. Retorna resultado."""
        target_dir = self._root / backup_id
        manifest_path = target_dir / "manifest.json"

        if not manifest_path.exists():
            return {"status": "error", "message": f"Backup {backup_id} não encontrado."}

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        restored = []

        for entry in manifest.get("files", []):
            backup_path = Path(entry["backup"])
            original_path = Path(entry["original"])
            if backup_path.exists():
                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, original_path)
                restored.append(str(original_path))

        return {"status": "success", "restored": restored, "backup_id": backup_id}

    def list_all(self) -> list[dict]:
        """Lista todos os backups disponíveis."""
        backups = []
        for d in sorted(self._root.iterdir(), reverse=True):
            if d.is_dir():
                manifest_path = d / "manifest.json"
                if manifest_path.exists():
                    try:
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        backups.append(
                            {
                                "id": manifest.get("id", d.name),
                                "ts": manifest.get("ts"),
                                "file_count": len(manifest.get("files", [])),
                            }
                        )
                    except Exception:
                        backups.append({"id": d.name, "ts": None, "file_count": 0})
        return backups

    def cleanup(self, max_age_days: int = 7) -> int:
        """Remove backups mais antigos que max_age_days."""
        cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        removed = 0
        for d in list(self._root.iterdir()):
            if d.is_dir():
                try:
                    mtime = datetime.datetime.fromtimestamp(d.stat().st_mtime)
                    if mtime < cutoff:
                        shutil.rmtree(d)
                        removed += 1
                except Exception:
                    pass
        return removed


# ---------------------------------------------------------------------------
# Approval System
# ---------------------------------------------------------------------------


class ApprovalManager:
    """Gerencia pedidos de aprovação pendentes."""

    def __init__(self):
        self._pending: dict[str, dict] = {}

    def create_request(
        self,
        command: str,
        reason: str,
        risk: RiskLevel,
        affected_files: list[str] | None = None,
        backup_id: str | None = None,
        rollback_plan: str | None = None,
    ) -> str:
        """Cria um pedido de aprovação. Retorna approval_id."""
        approval_id = uuid.uuid4().hex[:12]
        self._pending[approval_id] = {
            "id": approval_id,
            "command": command,
            "reason": reason,
            "risk": risk.value,
            "affected_files": affected_files or [],
            "backup_id": backup_id,
            "rollback_plan": rollback_plan or "",
            "status": "pending",
            "ts": datetime.datetime.now().isoformat(),
        }
        return approval_id

    def resolve(self, approval_id: str, allowed: bool) -> dict | None:
        """Resolve um pedido. Retorna o request ou None."""
        req = self._pending.get(approval_id)
        if req and req["status"] == "pending":
            req["status"] = "allowed" if allowed else "denied"
            req["resolved_ts"] = datetime.datetime.now().isoformat()
            return req
        return None

    def get_pending(self) -> list[dict]:
        return [r for r in self._pending.values() if r["status"] == "pending"]

    def get_all(self) -> list[dict]:
        return list(self._pending.values())


# ---------------------------------------------------------------------------
# Command Executor
# ---------------------------------------------------------------------------


def _run_command(command: str, timeout: int = 60) -> Dict[str, Any]:
    """Executa um comando e retorna resultado."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "LANG": "C.UTF-8"},
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout[-8192:] if result.stdout else "",  # Limitar output
            "stderr": result.stderr[-4096:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Comando excedeu timeout de {timeout}s"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# RootDaemon Server
# ---------------------------------------------------------------------------


class RootDaemon:
    """Daemon principal do NEXUS. Único processo com capacidades elevadas."""

    def __init__(self):
        self.socket_path = _get_socket_path()
        self.autonomy_level = _get_autonomy_level()
        self.audit = AuditLogger()
        self.backup = BackupManager()
        self.approval = ApprovalManager()

        print(f"[RootDaemon] Autonomy: {self.autonomy_level}")
        print(f"[RootDaemon] Socket: {self.socket_path}")

    # --- Action Handlers ---

    async def handle_execute(self, payload: dict) -> dict:
        """Executa um comando cru com classificação de risco."""
        command = (payload.get("command") or "").strip()
        reason = payload.get("reason", "sem motivo informado")
        context = payload.get("context") or {}
        caller = context.get("caller", "unknown")
        risk_accepted = context.get("risk_accepted", False)
        backup_paths = context.get("backup_paths") or []
        rollback_plan = context.get("rollback_plan", "")

        if not command:
            return {"status": "error", "message": "Comando vazio."}

        # 1. Classificar risco
        risk, risk_reason = classify_risk(command)

        # 2. FORBIDDEN — SEMPRE bloquear (mesmo em FULL)
        if risk == RiskLevel.FORBIDDEN:
            self.audit.log(command, risk, "BLOCKED", risk_reason, caller)
            return {
                "status": "blocked",
                "message": f"Comando PROIBIDO por política de segurança: {risk_reason}",
                "risk_level": risk.value,
            }

        # 3. HIGH_RISK — requer aprovação (exceto FULL ou risk_accepted)
        if risk == RiskLevel.HIGH_RISK:
            if self.autonomy_level != "FULL" and not risk_accepted:
                # Criar backup se paths fornecidos
                backup_id = None
                if backup_paths:
                    backup_id = self.backup.create(backup_paths)

                approval_id = self.approval.create_request(
                    command=command,
                    reason=reason,
                    risk=risk,
                    affected_files=backup_paths,
                    backup_id=backup_id,
                    rollback_plan=rollback_plan,
                )
                self.audit.log(
                    command,
                    risk,
                    "PENDING_APPROVAL",
                    risk_reason,
                    caller,
                    {"approval_id": approval_id},
                )
                return {
                    "status": "requires_approval",
                    "message": "Comando de alto risco requer aprovação humana.",
                    "risk_level": risk.value,
                    "approval_id": approval_id,
                    "risk_reason": risk_reason,
                }

        # 4. Backup automático para ações de escrita
        backup_id = None
        if backup_paths and risk in (RiskLevel.MEDIUM_RISK, RiskLevel.HIGH_RISK):
            backup_id = self.backup.create(backup_paths)

        # 5. Executar
        result = await asyncio.to_thread(_run_command, command)
        result["risk_level"] = risk.value
        result["risk_reason"] = risk_reason
        if backup_id:
            result["backup_id"] = backup_id

        # 6. Auditoria
        self.audit.log(
            command,
            risk,
            result["status"],
            reason,
            caller,
            {"backup_id": backup_id} if backup_id else None,
        )

        return result

    async def handle_backup(self, payload: dict) -> dict:
        """Cria backup de arquivos."""
        paths = payload.get("paths") or []
        if not paths:
            return {"status": "error", "message": "Nenhum path fornecido."}
        backup_id = self.backup.create(paths)
        self.audit.log(
            "backup", RiskLevel.READ_ONLY, "SUCCESS", f"Backup criado: {backup_id}"
        )
        return {"status": "success", "backup_id": backup_id}

    async def handle_rollback(self, payload: dict) -> dict:
        """Restaura backup."""
        backup_id = payload.get("backup_id", "")
        if not backup_id:
            return {"status": "error", "message": "backup_id não fornecido."}
        result = self.backup.restore(backup_id)
        self.audit.log(
            "rollback",
            RiskLevel.MEDIUM_RISK,
            result["status"],
            f"Rollback: {backup_id}",
        )
        return result

    async def handle_list_backups(self, payload: dict) -> dict:
        """Lista backups disponíveis."""
        return {"status": "success", "backups": self.backup.list_all()}

    async def handle_audit_tail(self, payload: dict) -> dict:
        """Retorna últimas entradas de auditoria."""
        n = payload.get("n", 50)
        return {"status": "success", "entries": self.audit.tail(n)}

    async def handle_approval_resolve(self, payload: dict) -> dict:
        """Resolve um pedido de aprovação e executa se aprovado."""
        approval_id = payload.get("approval_id", "")
        allowed = payload.get("allowed", False)

        req = self.approval.resolve(approval_id, allowed)
        if not req:
            return {
                "status": "error",
                "message": "Aprovação não encontrada ou já resolvida.",
            }

        if allowed:
            # Executar o comando aprovado
            self.audit.log(
                req["command"], RiskLevel.HIGH_RISK, "APPROVED", "Aprovado pelo usuário"
            )
            result = await asyncio.to_thread(_run_command, req["command"])
            result["approval_id"] = approval_id
            result["risk_level"] = req["risk"]
            self.audit.log(
                req["command"],
                RiskLevel.HIGH_RISK,
                result["status"],
                "Execução pós-aprovação",
            )
            return result
        else:
            self.audit.log(
                req["command"], RiskLevel.HIGH_RISK, "DENIED", "Negado pelo usuário"
            )
            return {
                "status": "denied",
                "message": "Comando negado pelo usuário.",
                "approval_id": approval_id,
            }

    async def handle_pending_approvals(self, payload: dict) -> dict:
        """Retorna aprovações pendentes."""
        return {"status": "success", "pending": self.approval.get_pending()}

    async def handle_batch(self, payload: dict) -> dict:
        """Executa uma lista de comandos sequencialmente (Transação)."""
        commands = payload.get("commands") or []
        reason = payload.get("reason", "Batch execution")
        context = payload.get("context") or {}

        results = []
        for cmd_entry in commands:
            # Se for apenas string, converte pra dict
            if isinstance(cmd_entry, str):
                cmd_entry = {"command": cmd_entry}

            # Executa usando o handle_execute existente
            res = await self.handle_execute(
                {
                    "command": cmd_entry.get("command"),
                    "reason": reason,
                    "context": context,
                }
            )
            results.append(res)

            # Se um falhar em modo transacional, para (opcional)
            if res.get("status") in ("failed", "blocked", "requires_approval"):
                break

        return {"status": "success", "results": results}

    async def handle_service_control(self, payload: dict) -> dict:
        """Controla serviços do NEXUS de forma segura."""
        service = payload.get("service")
        action = payload.get("service_action")

        if service not in NEXUS_SERVICES or action not in SERVICE_COMMANDS:
            return {"status": "blocked", "message": "Serviço ou ação não permitida."}

        cmd = f"systemctl --user {action} {service}"
        return await asyncio.to_thread(_run_command, cmd)

    # --- Dispatch ---

    DISPATCH = {
        "execute": "handle_execute",
        "batch": "handle_batch",
        "service_control": "handle_service_control",
        "backup": "handle_backup",
        "rollback": "handle_rollback",
        "list_backups": "handle_list_backups",
        "audit_tail": "handle_audit_tail",
        "approval_resolve": "handle_approval_resolve",
        "pending_approvals": "handle_pending_approvals",
    }

    async def dispatch(self, payload: dict) -> dict:
        action = payload.get("action", "")
        handler_name = self.DISPATCH.get(action)
        if not handler_name:
            return {"status": "error", "message": f"Ação desconhecida: {action}"}
        handler = getattr(self, handler_name)
        return await handler(payload)

    # --- Server ---

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=30.0)
            if not data:
                return

            payload = json.loads(data.decode().strip())
            response = await self.dispatch(payload)

            writer.write(json.dumps(response, ensure_ascii=False).encode() + b"\n")
            await writer.drain()
        except asyncio.TimeoutError:
            error = {"status": "error", "message": "Client timeout (30s)"}
            writer.write(json.dumps(error).encode() + b"\n")
            await writer.drain()
        except Exception as e:
            error = {"status": "error", "message": f"Daemon error: {e}"}
            try:
                writer.write(json.dumps(error).encode() + b"\n")
                await writer.drain()
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def serve(self):
        """Inicia o servidor Unix socket."""
        socket_path = Path(self.socket_path)

        # Garantir diretório
        socket_path.parent.mkdir(parents=True, exist_ok=True)

        # Remover socket antigo
        if socket_path.exists():
            socket_path.unlink()

        server = await asyncio.start_unix_server(
            self.handle_client, path=str(socket_path)
        )

        # Permissões restritas: owner + group
        os.chmod(str(socket_path), 0o660)

        print(f"[RootDaemon] ✓ Listening on {socket_path}")
        print(f"[RootDaemon] ✓ Socket permissions: 0660")
        print(f"[RootDaemon] ✓ Autonomy level: {self.autonomy_level}")
        print(f"[RootDaemon] ✓ Blocklist: {len(FORBIDDEN_PATTERNS)} patterns")

        # Limpeza periódica de backups antigos
        async def cleanup_loop():
            while True:
                await asyncio.sleep(3600)  # A cada hora
                removed = self.backup.cleanup(max_age_days=7)
                if removed:
                    print(f"[RootDaemon] Cleaned up {removed} old backups")

        asyncio.create_task(cleanup_loop())

        async with server:
            await server.serve_forever()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def main():
    daemon = RootDaemon()
    await daemon.serve()


if __name__ == "__main__":
    print("[RootDaemon] Iniciando NEXUS RootDaemon...")
    asyncio.run(main())
