from enum import Enum


class InteractionMode(str, Enum):
    QUICK_ANSWER = "quick_answer"
    TECHNICAL_PLAN = "technical_plan"
    COMMAND_MODE = "command_mode"
    DEBUG_MODE = "debug_mode"
    ARCHITECTURE_MODE = "architecture_mode"
    SUDO_REVIEW_MODE = "sudo_review_mode"
    SELF_IMPROVEMENT_MODE = "self_improvement_mode"


class InteractionEngine:
    """Modula a resposta da LLM para ser fluida e adaptada à intenção."""

    def __init__(self):
        pass

    def determine_mode(
        self, user_intent: str, risk_level: str = "LOW_RISK"
    ) -> InteractionMode:
        """Determina o modo de interação baseado na intenção e risco."""
        intent = user_intent.lower()

        if (
            "sudo" in intent
            or "root" in intent
            or risk_level in ["HIGH_RISK", "FORBIDDEN"]
        ):
            return InteractionMode.SUDO_REVIEW_MODE

        if (
            "melhorar nexus" in intent
            or "patch" in intent
            or "refatorar si mesmo" in intent
        ):
            return InteractionMode.SELF_IMPROVEMENT_MODE

        if "arquitetura" in intent or "design" in intent or "planejar" in intent:
            return InteractionMode.ARCHITECTURE_MODE

        if "erro" in intent or "bug" in intent or "falha" in intent:
            return InteractionMode.DEBUG_MODE

        if "execute" in intent or "rode o comando" in intent:
            return InteractionMode.COMMAND_MODE

        if "como" in intent and "fazer" in intent:
            return InteractionMode.TECHNICAL_PLAN

        return InteractionMode.QUICK_ANSWER

    def get_mode_prompt(self, mode: InteractionMode) -> str:
        """Retorna uma injeção de prompt específica para o modo selecionado."""
        prompts = {
            InteractionMode.QUICK_ANSWER: "Seja direto, curto e objetivo. Sem blocos longos de texto.",
            InteractionMode.TECHNICAL_PLAN: "Apresente um plano passo-a-passo técnico. Separe explicação de execução.",
            InteractionMode.COMMAND_MODE: "Retorne apenas os comandos seguros solicitados. Seja assertivo.",
            InteractionMode.DEBUG_MODE: "Analise o erro. Indique a causa provável e sugira a correção. Não chute.",
            InteractionMode.ARCHITECTURE_MODE: "Aja como Arquiteto de Software. Discuta trade-offs e decisões estruturais.",
            InteractionMode.SUDO_REVIEW_MODE: "[MODO REVIEW CRÍTICO] O usuário solicitou algo arriscado. Explique os riscos e monte o pedido para o SudoBroker.",
            InteractionMode.SELF_IMPROVEMENT_MODE: "[MODO SELF-IMPROVEMENT] Ative o pipeline de melhoria. Proponha patches pequenos e exija testes.",
        }
        return prompts.get(mode, prompts[InteractionMode.QUICK_ANSWER])


interaction_engine = InteractionEngine()
