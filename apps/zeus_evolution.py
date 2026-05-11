import os
import datetime
import sys
from zeus_core.core_system import (
    Blackboard,
    LibrarianAgent,
    StrategistAgent,
    OperatorAgent,
    CriticAgent,
)

CORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
LOG_FILE = os.path.join(CORE_PATH, "06 - Log de Evolução.md")


class ZeusBrain:
    def __init__(self, vector_memory=None):
        self.context = ""
        self.dna = ""
        # FUSÃO: Agentes Especializados + Blackboard
        self.blackboard = Blackboard()
        self.librarian = LibrarianAgent(CORE_PATH, vector_memory)
        self.strategist = StrategistAgent()
        self.operator = OperatorAgent()
        self.critic = CriticAgent()

    def load_memories(self):
        """Carga inicial básica de DNA."""
        dna_path = os.path.join(CORE_PATH, "07 - DNA.md")
        if os.path.exists(dna_path):
            with open(dna_path, "r", encoding="utf-8") as f:
                self.dna = f.read()
        self.print_neon("Neural DNA Synchronized.\n", "green")

    def print_neon(self, text, color="cyan"):
        """Imprime texto com cores ANSI para estética tech."""
        colors = {
            "cyan": "\033[96m",
            "purple": "\033[95m",
            "green": "\033[92m",
            "red": "\033[91m",
            "end": "\033[0m",
            "bold": "\033[1m",
        }
        sys.stdout.write(f"{colors.get(color, '')}{text}{colors['end']}")
        sys.stdout.flush()

    def cognitive_loop(self, thought):
        """Loop de Fusão: Librarian -> Strategist -> Operator -> Critic."""
        self.print_neon("\n[SINE-WAVE COGNITIVE CYCLE START]\n", "purple")

        # 1. Librarian (RAG Lite)
        self.print_neon("→ Librarian: Filtering Context...", "bold")
        fragment = self.librarian.get_relevant_context(thought)
        self.blackboard.update("context_fragment", fragment)

        # 2. Strategist (Planning)
        self.print_neon("→ Strategist: Mapping Strategy...", "bold")
        plan = self.strategist.plan(self.blackboard, thought)
        self.print_neon(f" {plan}\n", "cyan")

        # 3. Operator (Dry-run)
        self.print_neon("→ Operator: Generating Command Proposal (DRY-RUN)...", "bold")
        result = self.operator.execute(self.blackboard)
        self.print_neon(f" {result['commands']}\n", "cyan")

        # 4. Critic (Analysis)
        self.print_neon("→ Critic: Reviewing Proposal...", "bold")
        metric = self.critic.analyze(self.blackboard)
        self.print_neon(f" Review: {metric}\n", "green")

        # Sincronização Final
        full_evolution = (
            f"Thought: {thought}\n"
            f"Plan: {plan}\n"
            f"Proposed Commands (DRY-RUN): {result['commands']}\n"
            f"Execution Mode: {result['mode']}\n"
            f"Review: {metric}"
        )
        self.write_to_log(full_evolution)

        self.print_neon("\n[SINE-WAVE COGNITIVE CYCLE END]\n", "purple")

    def write_to_log(self, content):
        today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n### 🌀 Evolução Autônoma [{today}]\n> [!BRAIN] Pensamento Processado\n{content}\n\n---\n"

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
        self.print_neon(f"✔ Log de Evolução sincronizado: {LOG_FILE}\n", "green")


if __name__ == "__main__":
    zeus = ZeusBrain()

    os.system("clear")
    zeus.print_neon("╔════════════════════════════════════════════╗\n", "cyan")
    zeus.print_neon("║      ZEUS COGNITIVE OPERATING SYSTEM       ║\n", "cyan")
    zeus.print_neon("╚════════════════════════════════════════════╝\n\n", "cyan")

    zeus.print_neon("Initializing Neural Context...\n", "bold")
    zeus.load_memories()
    zeus.print_neon("Brain DNA Loaded. Synapses Ready.\n\n", "green")

    thought = input("⌨ INPUT THOUGHT (Enter para Auditoria Geral) > ")
    if not thought.strip():
        zeus.print_neon("Iniciando Auditoria Geral Autônoma...\n", "purple")
        thought = "Realize uma auditoria geral de todos os meus módulos core e do meu DNA de sistema. Sugira a próxima fase de evolução e registre no log."

    zeus.cognitive_loop(thought)
