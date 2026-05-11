import re
from zeus_core.events.event_bus import event_bus, EventType


class ResponseSanitizer:
    """Higieniza as respostas da LLM para evitar repetição do prompt, concatenação de histórico e formato ruim."""

    def __init__(self):
        self.max_repeated_blocks = 2

    async def sanitize(self, response: str) -> str:
        if not response:
            return ""

        original_len = len(response)

        # 1. Remove echo of System Prompt or Roles
        response = re.sub(
            r"--- OBJETIVO ATUAL ---.*?(?=---|$)", "", response, flags=re.DOTALL
        )
        response = re.sub(
            r"--- HISTÓRICO RECENTE.*?(?=---|$)", "", response, flags=re.DOTALL
        )
        response = re.sub(
            r"^(USER|ASSISTANT|SYSTEM):\s*",
            "",
            response,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        # 2. Detect repetition (very basic heuristic)
        paragraphs = response.split("\n\n")
        unique_paragraphs = []
        seen = set()

        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue
            if p_clean in seen:
                await event_bus.publish_async(
                    EventType.RESPONSE_DUPLICATED, {"content_preview": p_clean[:50]}
                )
                continue
            seen.add(p_clean)
            unique_paragraphs.append(p)

        sanitized = "\n\n".join(unique_paragraphs).strip()

        # If it stripped too much, it might be a valid code block with repeated empty lines, but keeping it simple.
        if len(sanitized) < original_len * 0.5 and original_len > 1000:
            # Fallback if we accidentally destroyed the response
            pass

        return sanitized


response_sanitizer = ResponseSanitizer()
