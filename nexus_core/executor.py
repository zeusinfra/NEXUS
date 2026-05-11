from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional

from nexus_core.actions import get_actions
from nexus_core.planner import create_plan, replan
from nexus_core.tools import ToolError


BroadcastFn = Callable[[dict], Awaitable[None]]


class PlanExecutor:
    def __init__(self, *, max_replans: int = 2):
        self.max_replans = max_replans
        self._actions = get_actions()

    async def _broadcast(self, broadcast: Optional[BroadcastFn], payload: dict) -> None:
        if not broadcast:
            return
        try:
            await broadcast(payload)
        except Exception:
            return

    async def _run_tool(self, tool: str, parameters: dict) -> dict:
        handler = self._actions.get(tool)
        if not handler:
            raise ToolError(f"Tool desconhecida: {tool}")
        if asyncio.iscoroutinefunction(handler):
            return await handler(parameters)
        return handler(parameters)

    async def execute_goal(
        self,
        goal: str,
        *,
        context: str = "",
        broadcast: Optional[BroadcastFn] = None,
    ) -> Dict[str, Any]:
        plan = await asyncio.to_thread(create_plan, goal, context=context)
        attempts = 0
        completed = []
        results: Dict[int, dict] = {}

        while True:
            steps = plan.get("steps") or []
            if not isinstance(steps, list):
                raise ToolError("Plano inválido (steps).")

            for step in steps:
                step_no = step.get("step")
                tool = step.get("tool")
                params = step.get("parameters") or {}
                desc = step.get("description") or ""

                await self._broadcast(
                    broadcast,
                    {
                        "type": "TOOL_LOG",
                        "stage": "step_start",
                        "tool": tool,
                        "step": step_no,
                        "description": desc,
                        "args": params,
                    },
                )

                try:
                    out = await self._run_tool(str(tool), dict(params))
                    results[int(step_no)] = {"ok": True, "tool": tool, "output": out}
                    completed.append(step)
                    await self._broadcast(
                        broadcast,
                        {
                            "type": "TOOL_LOG",
                            "stage": "step_done",
                            "tool": tool,
                            "step": step_no,
                            "result": out,
                        },
                    )
                except Exception as e:
                    err = str(e)
                    results[int(step_no) if step_no else -1] = {
                        "ok": False,
                        "tool": tool,
                        "error": err,
                    }
                    await self._broadcast(
                        broadcast,
                        {
                            "type": "TOOL_LOG",
                            "stage": "step_failed",
                            "tool": tool,
                            "step": step_no,
                            "error": err,
                        },
                    )

                    if attempts >= self.max_replans:
                        return {
                            "ok": False,
                            "goal": goal,
                            "plan": plan,
                            "completed_steps": completed,
                            "results": results,
                            "error": err,
                        }

                    attempts += 1
                    plan = await asyncio.to_thread(
                        replan,
                        goal,
                        completed_steps=completed,
                        failed_step=step,
                        error=err,
                    )
                    completed = []
                    results = {}
                    break
            else:
                return {
                    "ok": True,
                    "goal": goal,
                    "plan": plan,
                    "results": results,
                }
