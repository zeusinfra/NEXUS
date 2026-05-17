import importlib.util
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
SKILLS_DIR.mkdir(exist_ok=True)

class SkillEngine:
    """Motor que permite ao NEXUS aprender e executar novas habilidades dinâmicas."""

    def __init__(self):
        self.skills = {}
        self.load_all_skills()

    def load_all_skills(self):
        """Carrega todos os scripts Python da pasta skills/."""
        for file in SKILLS_DIR.glob("*.py"):
            if file.name == "__init__.py":
                continue
            self.register_skill_from_file(file)

    def register_skill_from_file(self, file_path):
        """Importa dinamicamente um arquivo Python como uma skill."""
        skill_name = file_path.stem
        try:
            spec = importlib.util.spec_from_file_location(skill_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[skill_name] = module
            spec.loader.exec_module(module)
            self.skills[skill_name] = module
            print(f"🧬 [DNA] Nova skill assimilada: {skill_name}")
        except Exception as e:
            print(f"❌ [DNA] Erro ao carregar skill {skill_name}: {e}")

    def add_new_skill(self, name, code):
        """Adiciona uma nova skill ao sistema (Self-Coding)."""
        file_path = SKILLS_DIR / f"{name}.py"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        self.register_skill_from_file(file_path)
        return f"Habilidade '{name}' integrada ao DNA com sucesso."

    def execute_skill(self, name, *args, **kwargs):
        """Executa uma habilidade aprendida."""
        if name in self.skills:
            if hasattr(self.skills[name], "run"):
                return self.skills[name].run(*args, **kwargs)
            return f"Erro: Skill '{name}' não possui a função 'run()'."
        return f"Erro: Skill '{name}' não encontrada."

skill_engine = SkillEngine()
