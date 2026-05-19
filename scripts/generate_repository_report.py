from __future__ import annotations

import argparse
import os
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT_DESCRIPTIONS = {
    ".github": "Automacao GitHub: workflows de CI, Dependabot, templates de issue e pull request.",
    "apps": "Superficie FastAPI e rotas de produto para status, cognicao, privacidade, GUI web e hub em tempo real.",
    "backend": "Backend Rust/Axum para eventos, aprovacoes, execucao, filesystem, gateway, LLM, storage e workers.",
    "bin": "Launchers e comandos operacionais do produto NEXUS.",
    "cognitive-python": "Ponte historica Python/Rust para experimentos cognitivos.",
    "communication": "Contrato protobuf e servicos de voz/comunicacao.",
    "config": "Exemplos de configuracao local e ambiente.",
    "configs": "Configuracoes do daemon organizacional, permissoes, identidade e unidades systemd.",
    "core-rust": "Workspace Rust de alto desempenho: sensores, memoria, seguranca, estado, politicas e bridge Python.",
    "core_modules": "Modulo legado do core v3.",
    "deploy": "Unidades systemd antigas ou alternativas para deploy.",
    "dist": "Artefatos de pacote Debian e raiz de instalacao gerada.",
    "docs": "Documentacao tecnica, instalacao, seguranca, arquitetura e fluxos.",
    "interfaces": "Interfaces alternativas, incluindo TUI Bubble Tea.",
    "memory": "Memoria persistida de exemplo/runtime local.",
    "models": "Modelos locais, especialmente voz/TTS.",
    "nexus-iced": "Interface grafica Rust/Iced conversacional premium.",
    "nexus_core": "Nucleo Python: agentes, runtime verificavel, cognicao, memoria, seguranca, modelos e integracoes.",
    "packaging": "Fonte do empacotamento Debian, scripts, desktop entry e systemd.",
    "requirements": "Dependencias Python separadas por perfil.",
    "scripts": "Automacoes de desenvolvimento, bootstrap e relatorios.",
    "skills": "Habilidades auxiliares do sistema.",
    "test_db": "Banco vetorial/teste local versionado.",
    "tests": "Testes unitarios, integracao e sistema.",
    "tools": "Ferramentas auxiliares.",
    "ui": "Ativos de UI estatica.",
    "watcher_rs": "Watcher Rust para eventos de filesystem/sistema.",
}


KEY_FILE_DESCRIPTIONS = {
    "README.md": "Entrada principal do projeto e visao de produto.",
    "Makefile": "Atalhos de build, teste e empacotamento.",
    "pyproject.toml": "Configuracao de lint, formatacao e type checking Python.",
    "pytest.ini": "Configuracao global do pytest.",
    "bin/nexus": "Launcher unificado para CLI de produto e organizacao.",
    "nexus_core/organization/runtime.py": "Runtime de execucao verificavel com planos, budgets, evidencia, replay e self-healing.",
    "nexus_core/organization/memory.py": "SQLite organizacional para tarefas, decisoes, eventos, comandos, verificacoes, planos e replays.",
    "nexus_core/organization/daemon.py": "Daemon persistente que integra memoria, blackboard, permissoes, swarm, runtime e workspace context.",
    "nexus_core/organization/security.py": "Politica, fila de aprovacao e fronteira entre proposta/aprovacao/execucao.",
    "nexus_core/organization/replay.py": "Reconstrucao de timeline de comando ou tarefa.",
    "nexus_core/organization/execution_plans.py": "Plano estruturado de execucao e etapas auditaveis.",
    "nexus_core/organization/resource_budget.py": "Orcamento de CPU/RAM/timeout/concorrencia/tokens para autonomia segura.",
    "nexus_core/organization/workspace_context.py": "Detector de traits do workspace.",
    "nexus_core/organization/self_healing.py": "Diagnostico de falhas e passos de recuperacao seguros.",
    "nexus_core/execution_protocol.py": "Ledger e protocolo evidence-first para execucao real de comandos.",
    "nexus_core/model_router.py": "Roteamento local/cloud por complexidade e risco.",
    "nexus_core/product_cli.py": "CLI de produto Linux para status, modelos e roteamento.",
    "nexus-iced/src/main.rs": "GUI Rust/Iced principal.",
    "nexus-iced/src/websocket.rs": "Cliente/eventos WebSocket da GUI.",
    "backend/src/main.rs": "Entrada do backend Rust/Axum.",
    "backend/src/execution/graph.rs": "Grafo de tarefas/execucao do backend Rust.",
    "backend/src/execution/command.rs": "Execucao de comandos no backend Rust.",
    "backend/src/execution/patch.rs": "Aplicacao/preview de patches no backend Rust.",
    "backend/src/approvals/mod.rs": "Fluxo de aprovacao do backend Rust.",
    "core-rust/nexus_synapse/src/lib.rs": "Bridge Rust/PyO3 para memoria sinaptica.",
    "core-rust/nexus_sensors/src/lib.rs": "Sensores Rust de OS/processos/filesystem.",
    "interfaces/tui-bubbletea/main.go": "TUI Bubble Tea para observabilidade operacional.",
    "packaging/scripts/build_deb.sh": "Build deterministico do pacote Debian.",
}


FLOW_SECTIONS = [
    (
        "Fluxo conversacional da GUI",
        [
            "Usuario abre `nexus-iced`.",
            "A sidebar minima organiza Conversas, Tarefas e Configuracoes.",
            "A area central mostra chat, sugestoes e mensagens NEXUS/usuario.",
            "`nexus-iced/src/websocket.rs` recebe eventos do backend ou runtime.",
            "Eventos como aprovacao, output, patch, evidencia e conclusao viram mensagens ou atividades discretas.",
            "A complexidade tecnica fica fora do primeiro plano; evidencia detalhada fica no runtime/CLI.",
        ],
    ),
    (
        "Fluxo CLI organizacional",
        [
            "`bin/nexus` chama `nexus_core.organization.__main__`.",
            "O comando carrega `NexusOrgConfig` e inicializa `OrganizationalDaemon`.",
            "O daemon sincroniza agentes, blackboard, memoria SQLite, permissoes, observer e runtime.",
            "Comandos como `workspace-context`, `execution-plans` e `replay-command` leem estado persistido.",
        ],
    ),
    (
        "Fluxo evidence-first de comando aprovado",
        [
            "Operador propoe comando via `PermissionManager.propose_command`.",
            "Politica classifica risco e cria item na approval queue.",
            "Aprovacao gera `approval_id` vinculado ao hash do comando/cwd.",
            "`RuntimeEngine.execute_approved` cria `command_id` e plano estruturado.",
            "Resource governor avalia timeout, concorrencia, CPU/RAM e token budget.",
            "Executor real captura stdout, stderr, exit code, duracao e artifacts.",
            "Verification engine valida status, exit code e executor evidence.",
            "Memory store persiste comando, eventos, verificacao, plano e etapas.",
            "Replay builder reconstrui timeline de eventos/etapas/verificacao.",
            "Se falhar, self-healing classifica a falha e registra passos de recuperacao sem aplicar patch nao aprovado.",
        ],
    ),
    (
        "Fluxo de workspace memory",
        [
            "Daemon chama `WorkspaceMemory.analyze` durante inicializacao.",
            "Detector busca `Cargo.toml`, `package.json`, markers Python, testes e paths relevantes.",
            "Tags como `rust_project`, `iced_frontend`, `axum_backend`, `uses_sqlx` e `websocket_architecture` sao persistidas.",
            "Blackboard recebe `workspace_context`; SQLite recebe entrada `scope=workspace`.",
            "Planos de execucao recebem tags do workspace para melhorar contexto e auditoria.",
        ],
    ),
    (
        "Fluxo de self-healing seguro",
        [
            "Falha de comando ou verificacao aciona `SelfHealingEngine.diagnose_failure`.",
            "Motor analisa stdout/stderr, summary e exit code.",
            "Falha e classificada como timeout, missing_command, rust_build_failure, test_failure, runtime_exception ou command_failure.",
            "O sistema registra recovery steps, incidente e evento de runtime.",
            "Nenhum patch ou rerun destrutivo ocorre sem nova aprovacao.",
        ],
    ),
    (
        "Fluxo de empacotamento Debian",
        [
            "`make deb` chama scripts em `packaging/scripts`.",
            "Arquivos sao copiados para `dist/debroot` com configuracao em `/etc/nexus` e unidade systemd.",
            "Pacote final `dist/nexus_*.deb` instala `/usr/bin/nexus`, `/usr/lib/nexus`, `/var/lib/nexus` e `/var/log/nexus`.",
            "Systemd executa `nexus org --config /etc/nexus/config.toml run`.",
        ],
    ),
    (
        "Fluxo de CI",
        [
            "Python workflow valida lint e slices de runtime/core.",
            "Rust workflow valida `core-rust`, `watcher_rs` e `nexus-iced`.",
            "Security workflow roda guardrails evidence-first, Gitleaks e Trivy.",
            "CodeQL cobre Actions, Python, Rust e Go.",
            "Templates de issue/PR exigem evidencia, replay e respeito a budgets quando runtime for alterado.",
        ],
    ),
]


@dataclass
class FileInfo:
    path: str
    root: str
    category: str
    language: str
    size: int
    lines: int | None
    description: str


def run_git_ls(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def classify(path: str) -> tuple[str, str]:
    ext = Path(path).suffix.lower()
    if path.startswith(".github/"):
        return "CI/GitHub", "YAML/Markdown"
    if path.startswith("dist/"):
        return "Artefato gerado", language_for_ext(ext)
    if path.startswith("docs/") or ext == ".md":
        return "Documentacao", "Markdown"
    if path.startswith("tests/"):
        return "Teste", language_for_ext(ext)
    if path.startswith("packaging/"):
        return "Empacotamento", language_for_ext(ext)
    if path.startswith("configs/") or path.startswith("config/"):
        return "Configuracao", language_for_ext(ext)
    if ext == ".py":
        return "Codigo Python", "Python"
    if ext == ".rs":
        return "Codigo Rust", "Rust"
    if ext == ".go":
        return "Codigo Go", "Go"
    if ext in {".toml", ".json", ".env", ".service", ".proto", ".yml", ".yaml"}:
        return "Configuracao/Contrato", language_for_ext(ext)
    if ext in {".deb", ".onnx", ".bin", ".wal", ".shm"}:
        return "Binario/artefato", language_for_ext(ext)
    if ext in {".sh"} or "/" not in path and path in {"Makefile"}:
        return "Script/automacao", language_for_ext(ext)
    return "Projeto", language_for_ext(ext)


def language_for_ext(ext: str) -> str:
    return {
        ".py": "Python",
        ".rs": "Rust",
        ".go": "Go",
        ".md": "Markdown",
        ".toml": "TOML",
        ".json": "JSON",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".sh": "Shell",
        ".service": "systemd",
        ".proto": "Protocol Buffers",
        ".lock": "Lockfile",
        ".deb": "Debian package",
        ".onnx": "ONNX",
        ".bin": "Binary",
        ".wal": "SQLite WAL",
        ".shm": "SQLite SHM",
    }.get(ext, "Texto/Binario")


def describe_file(path: str, category: str, language: str) -> str:
    if path in KEY_FILE_DESCRIPTIONS:
        return KEY_FILE_DESCRIPTIONS[path]
    name = Path(path).name
    stem = Path(path).stem.replace("_", " ").replace("-", " ")
    if path.startswith("dist/debroot/"):
        return "Arquivo copiado para a raiz Debian gerada."
    if path.startswith("tests/"):
        return f"Teste {stem} para validar comportamento do sistema."
    if path.startswith(".github/workflows/"):
        return f"Workflow CI {name}."
    if path.startswith(".github/ISSUE_TEMPLATE/"):
        return f"Template GitHub Issue {name}."
    if path.startswith("requirements/"):
        return f"Dependencias Python do perfil {stem}."
    if name == "Cargo.toml":
        return "Manifesto Cargo do crate/workspace Rust."
    if name == "Cargo.lock":
        return "Lockfile Cargo com dependencias Rust resolvidas."
    if name == "__init__.py":
        return "Inicializador de pacote Python."
    if name.endswith(".service"):
        return "Unidade systemd para daemonizacao."
    if language == "Python":
        return f"Modulo Python `{stem}`."
    if language == "Rust":
        return f"Modulo Rust `{stem}`."
    if language == "Go":
        return f"Codigo Go `{stem}`."
    return f"{category} em formato {language}."


def is_binary_path(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in {".deb", ".onnx", ".bin", ".wal", ".shm", ".png", ".jpg", ".jpeg"}


def line_count(path: Path) -> int | None:
    if is_binary_path(str(path)):
        return None
    try:
        with path.open("rb") as handle:
            data = handle.read()
        if b"\0" in data[:4096]:
            return None
        return data.decode("utf-8", errors="replace").count("\n") + (0 if data.endswith(b"\n") else 1)
    except OSError:
        return None


def collect_files(root: Path) -> list[FileInfo]:
    infos: list[FileInfo] = []
    for path in run_git_ls(root):
        file_path = root / path
        parts = path.split("/")
        top = parts[0]
        category, language = classify(path)
        try:
            size = file_path.stat().st_size
        except OSError:
            size = 0
        infos.append(
            FileInfo(
                path=path,
                root=top,
                category=category,
                language=language,
                size=size,
                lines=line_count(file_path),
                description=describe_file(path, category, language),
            )
        )
    return infos


def fmt_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        escaped = [cell.replace("|", "\\|").replace("\n", " ") for cell in row]
        out.append("| " + " | ".join(escaped) + " |")
    return "\n".join(out)


def build_markdown(root: Path, files: list[FileInfo]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    by_root: dict[str, list[FileInfo]] = defaultdict(list)
    for info in files:
        by_root[info.root].append(info)
    total_lines = sum(info.lines or 0 for info in files)
    categories = Counter(info.category for info in files)
    languages = Counter(info.language for info in files)

    lines: list[str] = []
    lines.append("# Relatorio tecnico completo do repositorio NEXUS")
    lines.append("")
    lines.append(f"Gerado em: {now}")
    lines.append(f"Raiz analisada: `{root}`")
    lines.append("")
    lines.append("## 1. Resumo executivo")
    lines.append("")
    lines.append(
        "O NEXUS e um Cognitive Operating OS local-first com interface conversacional Rust/Iced, "
        "runtime Python evidence-first, backend Rust/Axum, modulos Rust de alto desempenho, "
        "memoria organizacional SQLite, aprovacao humana, replay de execucao e empacotamento Debian."
    )
    lines.append("")
    lines.append(
        f"O inventario rastreado pelo Git possui **{len(files)} arquivos**, aproximadamente "
        f"**{total_lines:,} linhas textuais** e **{len(by_root)} entradas de raiz**."
    )
    lines.append("")
    lines.append("### Distribuicao por categoria")
    lines.append("")
    lines.append(
        markdown_table(
            ["Categoria", "Arquivos"],
            [[name, str(count)] for name, count in categories.most_common()],
        )
    )
    lines.append("")
    lines.append("### Distribuicao por linguagem/formato")
    lines.append("")
    lines.append(
        markdown_table(
            ["Linguagem/Formato", "Arquivos"],
            [[name, str(count)] for name, count in languages.most_common()],
        )
    )
    lines.append("")
    lines.append("## 2. Mapa das pastas")
    lines.append("")
    root_rows = []
    for root_name in sorted(by_root):
        items = by_root[root_name]
        root_rows.append(
            [
                root_name,
                str(len(items)),
                f"{sum(item.lines or 0 for item in items):,}",
                ROOT_DESCRIPTIONS.get(root_name, "Arquivo ou pasta de suporte do projeto."),
            ]
        )
    lines.append(markdown_table(["Pasta/raiz", "Arquivos", "Linhas", "Responsabilidade"], root_rows))
    lines.append("")
    lines.append("## 3. Fluxos principais")
    lines.append("")
    for title, steps in FLOW_SECTIONS:
        lines.append(f"### {title}")
        lines.append("")
        for index, step in enumerate(steps, start=1):
            lines.append(f"{index}. {step}")
        lines.append("")
    lines.append("## 4. Arquitetura por camada")
    lines.append("")
    layers = [
        ("Interface humana", "`nexus-iced`, `interfaces/tui-bubbletea`, `ui/static`, `apps/web_gui.py`"),
        ("Produto/CLI", "`bin/nexus`, `nexus_core/product_cli.py`, `nexus_core/organization/__main__.py`"),
        ("Runtime organizacional", "`nexus_core/organization/*`"),
        ("Execucao evidence-first", "`nexus_core/execution_protocol.py`, `nexus_core/organization/runtime.py`"),
        ("Memoria", "`nexus_core/organization/memory.py`, `nexus_core/conversation/*`, `memory/*`"),
        ("Cognicao", "`nexus_core/cognitive/*`, `nexus_core/v4/*`"),
        ("Modelos", "`nexus_core/models/*`, `nexus_core/model_router.py`, `nexus_core/llm_service.py`"),
        ("Backend Rust", "`backend/src/*`"),
        ("Rust acelerado", "`core-rust/*`, `watcher_rs/*`"),
        ("Entrega", "`packaging/*`, `dist/*`, `deploy/systemd/*`, `configs/systemd/*`"),
        ("Qualidade", "`tests/*`, `.github/workflows/*`, `.github/ISSUE_TEMPLATE/*`"),
    ]
    lines.append(markdown_table(["Camada", "Arquivos/pastas"], [[a, b] for a, b in layers]))
    lines.append("")
    lines.append("## 5. Detalhamento por pasta")
    lines.append("")
    for root_name in sorted(by_root):
        items = sorted(by_root[root_name], key=lambda item: item.path)
        lines.append(f"### {root_name}")
        lines.append("")
        lines.append(ROOT_DESCRIPTIONS.get(root_name, "Raiz de suporte ou arquivo solto do projeto."))
        lines.append("")
        lines.append(
            f"Arquivos: {len(items)}. Linhas textuais aproximadas: {sum(item.lines or 0 for item in items):,}. "
            f"Tamanho total: {fmt_size(sum(item.size for item in items))}."
        )
        lines.append("")
        category_rows = [[name, str(count)] for name, count in Counter(item.category for item in items).most_common()]
        if category_rows:
            lines.append(markdown_table(["Tipo", "Quantidade"], category_rows))
            lines.append("")
        key_items = [item for item in items if item.path in KEY_FILE_DESCRIPTIONS][:12]
        if key_items:
            lines.append("Arquivos-chave:")
            lines.append("")
            for item in key_items:
                lines.append(f"- `{item.path}`: {item.description}")
            lines.append("")
    lines.append("## 6. Inventario completo de arquivos")
    lines.append("")
    lines.append(
        "Tabela completa dos arquivos rastreados pelo Git. Linhas vazias indicam arquivo binario, lockfile ou artefato."
    )
    lines.append("")
    inventory_rows = []
    for item in sorted(files, key=lambda info: info.path):
        inventory_rows.append(
            [
                item.path,
                item.category,
                item.language,
                "" if item.lines is None else str(item.lines),
                fmt_size(item.size),
                item.description,
            ]
        )
    lines.append(
        markdown_table(
            ["Arquivo", "Categoria", "Formato", "Linhas", "Tamanho", "Descricao"],
            inventory_rows,
        )
    )
    lines.append("")
    lines.append("## 7. Observacoes finais")
    lines.append("")
    lines.append(
        "- Pastas como `.git`, `.venv`, `target`, caches locais e logs nao entram no inventario rastreado pelo Git."
    )
    lines.append(
        "- `dist/` esta rastreado e foi incluido como artefato gerado/empacotamento para mostrar a entrega Debian atual."
    )
    lines.append(
        "- O fluxo de maior criticidade e `aprovacao -> plano -> budget -> execucao -> verificacao -> replay -> memoria`."
    )
    lines.append(
        "- A interface principal deve continuar escondendo complexidade tecnica, enquanto o runtime preserva rastreabilidade completa."
    )
    lines.append("")
    return "\n".join(lines)


def build_pdf(markdown_text: str, output_path: Path) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            LongTable,
            PageBreak,
            Paragraph,
            Preformatted,
            SimpleDocTemplate,
            Spacer,
            TableStyle,
        )
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("reportlab is required to generate the PDF") from exc

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7.2, leading=9))
    styles.add(ParagraphStyle(name="Tiny", parent=styles["BodyText"], fontSize=6.2, leading=7.5))
    styles.add(ParagraphStyle(name="CodeSmall", parent=styles["Code"], fontSize=6.5, leading=8))
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1.1 * cm,
        leftMargin=1.1 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title="Relatorio tecnico completo do repositorio NEXUS",
    )
    story = []
    in_code = False
    code_lines: list[str] = []
    table_lines: list[str] = []

    def flush_code() -> None:
        nonlocal code_lines
        if code_lines:
            story.append(Preformatted("\n".join(code_lines), styles["CodeSmall"]))
            story.append(Spacer(1, 0.14 * cm))
            code_lines = []

    def flush_table() -> None:
        nonlocal table_lines
        if not table_lines:
            return
        rows = []
        for line in table_lines:
            if set(line.replace("|", "").strip()) <= {"-", ":", " "}:
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows.append(cells)
        table_lines = []
        if len(rows) < 2:
            return
        max_cols = max(len(row) for row in rows)
        normalized = [row + [""] * (max_cols - len(row)) for row in rows]
        if max_cols >= 6:
            widths = [4.1 * cm, 2.0 * cm, 1.6 * cm, 1.1 * cm, 1.3 * cm, 7.3 * cm]
        elif max_cols == 4:
            widths = [3.0 * cm, 1.7 * cm, 1.7 * cm, 10.8 * cm]
        elif max_cols == 3:
            widths = [4.2 * cm, 2.2 * cm, 10.8 * cm]
        else:
            widths = None
        pdf_rows = []
        for row in normalized:
            pdf_rows.append([Paragraph(cell.replace("`", ""), styles["Tiny"]) for cell in row])
        table = LongTable(pdf_rows, colWidths=widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1020")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#AAB2C0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 0.18 * cm))

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            flush_table()
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if line.startswith("| "):
            table_lines.append(line)
            continue
        flush_table()
        if not line:
            story.append(Spacer(1, 0.1 * cm))
            continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Title"]))
            story.append(Spacer(1, 0.25 * cm))
            continue
        if line.startswith("## "):
            story.append(PageBreak())
            story.append(Paragraph(line[3:], styles["Heading1"]))
            story.append(Spacer(1, 0.18 * cm))
            continue
        if line.startswith("### "):
            story.append(Paragraph(line[4:], styles["Heading2"]))
            story.append(Spacer(1, 0.12 * cm))
            continue
        if line.startswith("- "):
            story.append(Paragraph("• " + line[2:], styles["Small"]))
            continue
        if len(line) > 2 and line[0].isdigit() and ". " in line[:5]:
            story.append(Paragraph(line, styles["Small"]))
            continue
        story.append(Paragraph(line.replace("`", ""), styles["Small"]))
    flush_code()
    flush_table()
    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate NEXUS repository report")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--markdown", default="docs/NEXUS_REPOSITORY_REPORT.md")
    parser.add_argument("--pdf", default="docs/NEXUS_REPOSITORY_REPORT.pdf")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    files = collect_files(root)
    markdown = build_markdown(root, files)
    markdown_path = root / args.markdown
    pdf_path = root / args.pdf
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    build_pdf(markdown, pdf_path)
    print(f"Generated {markdown_path}")
    print(f"Generated {pdf_path}")


if __name__ == "__main__":
    main()
