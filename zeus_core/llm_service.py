from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from zeus_core.observability import get_logger, increment_metric, log_event


logger = get_logger("zeus.llm")


@dataclass(frozen=True)
class LLMService:
    get_status: Callable[[], dict]
    call_llm: Callable[[list[dict]], str]

    def test_connectivity(self) -> dict:
        status = self.get_status()
        started = time.time()
        try:
            reply = self.call_llm(
                [
                    {"role": "system", "content": "Responda apenas com: ZEUS LLM OK"},
                    {"role": "user", "content": "Teste de conectividade do modelo."},
                ]
            )
        except Exception as e:
            increment_metric("llm_connectivity_total")
            increment_metric("llm_connectivity_failed")
            log_event(
                logger,
                40,
                "llm_connectivity_exception",
                provider=status.get("provider"),
                error=str(e),
            )
            return {
                "ok": False,
                "status": status,
                "error": str(e),
                "latency_ms": round((time.time() - started) * 1000),
            }

        ok = bool(reply and "Error:" not in reply and "Connection Error" not in reply)
        increment_metric("llm_connectivity_total")
        if not ok:
            increment_metric("llm_connectivity_failed")
        log_event(
            logger,
            20 if ok else 30,
            "llm_connectivity_test",
            provider=status.get("provider"),
            model=status.get("model"),
            ok=ok,
            latency_ms=round((time.time() - started) * 1000),
        )
        return {
            "ok": ok,
            "status": status,
            "reply": (reply or "")[:500],
            "latency_ms": round((time.time() - started) * 1000),
        }
