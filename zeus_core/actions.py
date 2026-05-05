from __future__ import annotations

import fnmatch
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from zeus_core.command_policy import validate_command
from zeus_core.tools import ToolError, get_time, read_file, write_file
from zeus_core.vision import (
    analyze_image_with_llm,
    analyze_with_ocr_fallback,
    capture_screen,
    image_to_base64,
    is_tesseract_available,
    ocr_image,
)
from zeus_core.browser_control import browser_control
from zeus_core.integrations.linear import create_linear_issue, get_active_issues
from zeus_core.integrations.notion import create_notion_page, search_notion
from zeus_core.integrations.obsidian import read_note, write_obsidian_insight
from zeus_core.integrations.filesystem_mirror import FilesystemMirror
from zeus_core.diagnostics import get_system_diagnostics


def _project_root() -> Path:
    env_root = os.getenv("ZEUS_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _resolve_project_path(path: str) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ToolError("Caminho inválido.")

    root = _project_root()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()

    try:
        candidate.relative_to(root)
    except Exception as e:
        raise ToolError(f"Acesso negado fora do projeto: {candidate}") from e

    return candidate


def cmd_control(parameters: dict) -> dict:
    command = (parameters or {}).get("command") or (parameters or {}).get("task") or ""
    timeout_s = int((parameters or {}).get("timeout_s") or 30)
    confirmed = bool((parameters or {}).get("confirmed"))
    command = str(command).strip()
    if not command:
        raise ToolError("cmd_control requer 'command' (ou 'task').")

    tokens = shlex.split(command)
    decision = validate_command(command, tokens, confirmed=confirmed)

    root = _project_root()
    try:
        completed = subprocess.run(
            tokens,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as e:
        raise ToolError(f"Comando não encontrado: {tokens[0] if tokens else command}") from e
    except subprocess.TimeoutExpired as e:
        raise ToolError(f"Timeout ao executar comando após {timeout_s}s.") from e

    return {
        "command": command,
        "category": decision.category,
        "requires_confirmation": decision.requires_confirmation,
        "cwd": str(root),
        "exit_code": completed.returncode,
        "stdout": (completed.stdout or "")[:50_000],
        "stderr": (completed.stderr or "")[:50_000],
    }


def file_controller(parameters: dict) -> dict:
    p = parameters or {}
    action = str(p.get("action") or "").strip().lower()
    path = str(p.get("path") or ".").strip()

    if not action:
        raise ToolError("file_controller requer 'action'.")

    target = _resolve_project_path(path)

    if action == "list":
        if not target.exists():
            raise ToolError(f"Pasta não encontrada: {target}")
        if not target.is_dir():
            raise ToolError(f"Não é uma pasta: {target}")
        items = []
        for child in sorted(target.iterdir(), key=lambda x: x.name.lower()):
            try:
                kind = "dir" if child.is_dir() else "file"
                size = child.stat().st_size if child.is_file() else None
            except Exception:
                kind = "unknown"
                size = None
            items.append({"name": child.name, "type": kind, "size": size})
        return {"path": str(target), "items": items}

    if action == "read":
        max_bytes = int(p.get("max_bytes") or 200_000)
        return read_file(str(target), max_bytes=max_bytes)

    if action in {"write", "create_file"}:
        content = p.get("content", "")
        if not isinstance(content, str):
            raise ToolError("Conteúdo inválido (esperado string).")
        mode = str(p.get("mode") or "overwrite").strip().lower()
        return write_file(str(target), content, mode=mode)

    if action == "create_folder":
        target.mkdir(parents=True, exist_ok=True)
        return {"path": str(target), "created": True}

    if action == "delete":
        recursive = bool(p.get("recursive", False))
        if not target.exists():
            return {"path": str(target), "deleted": False, "reason": "not_found"}
        if target.is_dir():
            if not recursive:
                raise ToolError("Para deletar pasta, use recursive=true.")
            shutil.rmtree(target)
            return {"path": str(target), "deleted": True, "type": "dir"}
        target.unlink()
        return {"path": str(target), "deleted": True, "type": "file"}

    if action in {"move", "copy"}:
        destination = p.get("destination")
        if not destination:
            raise ToolError("Ação requer 'destination'.")
        dest = _resolve_project_path(str(destination))
        dest.parent.mkdir(parents=True, exist_ok=True)
        if action == "move":
            shutil.move(str(target), str(dest))
            return {"from": str(target), "to": str(dest), "moved": True}
        if target.is_dir():
            shutil.copytree(str(target), str(dest), dirs_exist_ok=True)
        else:
            shutil.copy2(str(target), str(dest))
        return {"from": str(target), "to": str(dest), "copied": True}

    if action == "rename":
        new_name = p.get("new_name")
        if not new_name or not isinstance(new_name, str):
            raise ToolError("rename requer 'new_name'.")
        dest = target.with_name(new_name)
        dest = _resolve_project_path(str(dest))
        target.rename(dest)
        return {"from": str(target), "to": str(dest), "renamed": True}

    if action == "find":
        pattern = str(p.get("name") or p.get("pattern") or "").strip()
        glob = str(p.get("glob") or "*").strip()
        max_results = int(p.get("max_results") or 50)
        if not pattern and not glob:
            raise ToolError("find requer 'name/pattern' e/ou 'glob'.")
        if not target.exists() or not target.is_dir():
            raise ToolError("find requer 'path' como diretório existente.")

        results = []
        needle = pattern.lower()
        for child in target.rglob("*"):
            if len(results) >= max_results:
                break
            rel = str(child.relative_to(target))
            if glob and not fnmatch.fnmatch(child.name, glob):
                continue
            if needle and needle not in child.name.lower() and needle not in rel.lower():
                continue
            results.append({"path": str(child), "type": "dir" if child.is_dir() else "file"})
        return {"path": str(target), "results": results, "truncated": len(results) >= max_results}

    if action == "disk_usage":
        if not target.exists():
            raise ToolError(f"Caminho não encontrado: {target}")
        if target.is_file():
            return {"path": str(target), "bytes": target.stat().st_size}
        total = 0
        for child in target.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except Exception:
                    pass
        return {"path": str(target), "bytes": total}

    raise ToolError(f"Ação desconhecida em file_controller: {action}")


def screen_process(parameters: dict) -> dict:
    p = parameters or {}
    angle = str(p.get("angle") or "screen").strip().lower()
    question = str(p.get("text") or p.get("question") or "").strip()
    include_b64 = bool(p.get("include_b64", False))
    do_ocr = bool(p.get("ocr", False))
    ocr_lang = str(p.get("ocr_lang") or "por").strip()
    do_llm = bool(p.get("llm", False))
    auto = bool(p.get("auto", True))

    if angle not in {"screen"}:
        raise ToolError("angle suportado nesta versão: 'screen'.")

    cap = capture_screen()
    out = {"capture": cap, "question": question}

    if do_ocr:
        try:
            out["ocr"] = ocr_image(cap["path"], lang=ocr_lang)
        except Exception as e:
            out["ocr_error"] = str(e)

    if include_b64:
        try:
            out["image_b64"] = image_to_base64(cap["path"])
        except Exception as e:
            out["image_b64_error"] = str(e)

    # Análise: (1) LLM multimodal quando solicitado/auto, (2) fallback OCR quando possível
    if question:
        analysis = {}
        if do_llm or auto:
            try:
                analysis["llm"] = analyze_image_with_llm(cap["path"], question=question)
                analysis["mode"] = "llm"
            except Exception as e:
                analysis["llm_error"] = str(e)

        if analysis.get("mode") != "llm" and (do_ocr or auto):
            try:
                analysis["ocr_fallback"] = analyze_with_ocr_fallback(cap["path"], question=question, ocr_lang=ocr_lang)
                analysis["mode"] = analysis.get("mode") or "ocr"
            except Exception as e:
                analysis["ocr_fallback_error"] = str(e)

        if analysis:
            out["analysis"] = analysis

    return out


def install_tesseract(parameters: dict) -> dict:
    """
    Retorna instruções seguras (não executa) para instalar tesseract no sistema.
    """
    os_release = ""
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            os_release = f.read()
    except Exception:
        os_release = ""

    distro_id = ""
    for line in os_release.splitlines():
        if line.startswith("ID="):
            distro_id = line.split("=", 1)[1].strip().strip('"')
            break

    lang = str((parameters or {}).get("lang") or "por").strip().lower()
    if not re.fullmatch(r"[a-z]{3}", lang):
        lang = "por"

    common = {
        "note": "Execute manualmente no seu terminal (requer privilégios de admin).",
        "already_available": is_tesseract_available(),
        "lang": lang,
    }

    instructions = []
    instructions.append("Ubuntu/Debian:")
    instructions.append(f"  sudo apt update && sudo apt install -y tesseract-ocr tesseract-ocr-{lang}")
    instructions.append("Fedora:")
    instructions.append(f"  sudo dnf install -y tesseract tesseract-langpack-{lang}")
    instructions.append("Arch:")
    instructions.append(f"  sudo pacman -S tesseract tesseract-data-{lang}")
    instructions.append("macOS (Homebrew):")
    instructions.append("  brew install tesseract")
    instructions.append("Windows (Chocolatey):")
    instructions.append("  choco install tesseract")

    return {**common, "distro_id": distro_id or None, "instructions": "\n".join(instructions)}


def obsidian_read_note(parameters: dict) -> dict:
    path = str((parameters or {}).get("path") or "").strip()
    if not path:
        raise ToolError("obsidian_read_note requer 'path'.")
    note = read_note(path)
    return {
        "title": note["title"],
        "tags": note["tags"],
        "internal_links": note["internal_links"],
        "path": note["path"],
        "content": note["content"][:4000],
        "truncated": len(note["content"]) > 4000,
    }


def obsidian_write_insight(parameters: dict) -> dict:
    title = str((parameters or {}).get("title") or "ZEUS Insight").strip()
    content = str((parameters or {}).get("content") or "").strip()
    if not content:
        raise ToolError("obsidian_write_insight requer 'content'.")
    path = write_obsidian_insight(title, content)
    return {"path": path, "written": True}


def obsidian_mirror_filesystem(parameters: dict) -> dict:
    from apps.web_gui import memory_manager
    path = str((parameters or {}).get("path") or ".").strip()
    max_depth = int((parameters or {}).get("max_depth") or 3)
    
    # Resolvendo o caminho. Se for ".", usa o root do projeto.
    # Se for absoluto, verifica se existe.
    root = _project_root()
    target = Path(path).expanduser()
    if not target.is_absolute():
        target = (root / target).resolve()
    
    if not target.exists():
        raise ToolError(f"Caminho não encontrado: {target}")

    mirror = FilesystemMirror(memory_manager=memory_manager)
    result = mirror.mirror_path(str(target), max_depth=max_depth)
    return {"status": "success", "message": result}


def notion_create_page(parameters: dict) -> dict:
    title = str((parameters or {}).get("title") or "ZEUS Note").strip()
    content = str((parameters or {}).get("content") or "").strip()
    tags = list((parameters or {}).get("tags") or [])
    response = create_notion_page(title, content, tags, "ZEUS Agent")
    return {"ok": "error" not in response, "response": response}


def notion_search(parameters: dict) -> dict:
    query = str((parameters or {}).get("query") or "").strip()
    if not query:
        raise ToolError("notion_search requer 'query'.")
    results = search_notion(query)
    return {"count": len(results), "results": results[:5]}


def linear_create_issue(parameters: dict) -> dict:
    title = str((parameters or {}).get("title") or "ZEUS Task").strip()
    description = str((parameters or {}).get("description") or "").strip()
    labels = list((parameters or {}).get("labels") or [])
    priority = str((parameters or {}).get("priority") or "medium").strip()
    response = create_linear_issue(title, description, labels, priority, "ZEUS Agent")
    return {"ok": "error" not in response, "response": response}


def linear_current_context(parameters: dict) -> dict:
    issues = get_active_issues()
    return {"count": len(issues), "issues": issues[:10]}


def get_actions() -> Dict[str, Any]:
    return {
        "get_time": lambda params: get_time(),
        "file_controller": file_controller,
        "cmd_control": cmd_control,
        "screen_process": screen_process,
        "install_tesseract": install_tesseract,
        "browser_control": browser_control,
        "obsidian_read_note": obsidian_read_note,
        "obsidian_write_insight": obsidian_write_insight,
        "obsidian_mirror_filesystem": obsidian_mirror_filesystem,
        "notion_create_page": notion_create_page,
        "notion_search": notion_search,
        "linear_create_issue": linear_create_issue,
        "linear_current_context": linear_current_context,
        "system_diagnostics": lambda params: get_system_diagnostics(),
    }
