import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus_core.agent import Agent
from nexus_core.execution_protocol import read_execution_result


class ScriptedAgent(Agent):
    def __init__(self, responses):
        super().__init__(max_steps=3)
        self._responses = list(responses)

    async def _call_llm_stream(self, messages):
        response = self._responses.pop(0)
        for chunk in response:
            yield chunk


class AgentFeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_answer_emits_progress_events(self):
        events = []

        async def broadcast(payload):
            events.append(payload)

        agent = ScriptedAgent(["Resposta final."])
        reply = await agent.run("ping", broadcast=broadcast)

        self.assertEqual(reply, "Resposta final.")
        stages = [
            event.get("stage")
            for event in events
            if event.get("type") == "AGENT_PROGRESS"
        ]
        self.assertIn("started", stages)
        self.assertIn("step_started", stages)
        self.assertIn("completed", stages)

    async def test_tool_call_emits_tool_progress_events(self):
        events = []

        async def broadcast(payload):
            events.append(payload)

        agent = ScriptedAgent(
            [
                '<tool_call>{"name":"system_capabilities","args":{}}</tool_call>',
                "Capacidades verificadas.",
            ]
        )
        reply = await agent.run("ver capacidades", broadcast=broadcast)

        self.assertEqual(reply, "Capacidades verificadas.")
        stages = [
            event.get("stage")
            for event in events
            if event.get("type") == "AGENT_PROGRESS"
        ]
        self.assertIn("tool_running", stages)
        self.assertIn("tool_done", stages)
        self.assertIn("completed", stages)

    async def test_direct_fake_completion_is_guarded(self):
        agent = ScriptedAgent(["feito"])
        reply = await agent.run("rode um comando")

        self.assertEqual(
            reply,
            "Ainda não executei. Preciso criar uma proposta de comando para aprovação.",
        )

    async def test_cmd_control_requires_ledger_approval_before_result(self):
        events = []

        async def broadcast(payload):
            events.append(payload)

        with (
            self.subTest("proposal then approval"),
            tempfile.TemporaryDirectory() as tmp,
        ):
            root = Path(tmp)
            with patch.dict(
                "os.environ",
                {
                    "NEXUS_CMD_ALLOWLIST": "python3",
                    "NEXUS_EXECUTION_LEDGER_PATH": str(root / "ledger.jsonl"),
                    "NEXUS_EXECUTION_ARTIFACT_DIR": str(root / "executions"),
                    "NEXUS_PROJECT_ROOT": str(root),
                },
                clear=False,
            ):
                agent = ScriptedAgent(
                    [
                        '<tool_call>{"name":"cmd_control","args":{"command":"python3 --version","timeout_s":5}}</tool_call>',
                        "feito",
                    ]
                )
                first = await agent.run(
                    "ver python", client_key="agent-test", broadcast=broadcast
                )
                self.assertIn("proposal_id", first)

                pending = [
                    e for e in events if e.get("type") == "EXECUTION_PENDING_APPROVAL"
                ][0]
                proposal_id = pending["proposal_id"]

                second = await agent.run(
                    "sim", client_key="agent-test", broadcast=broadcast
                )
                self.assertEqual(second, "feito")
                result = read_execution_result(proposal_id)

        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(result["verified_by_executor"])


if __name__ == "__main__":
    unittest.main()
