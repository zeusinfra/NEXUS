import unittest

from zeus_core.agent import Agent


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
        stages = [event.get("stage") for event in events if event.get("type") == "AGENT_PROGRESS"]
        self.assertIn("started", stages)
        self.assertIn("step_started", stages)
        self.assertIn("completed", stages)

    async def test_tool_call_emits_tool_progress_events(self):
        events = []

        async def broadcast(payload):
            events.append(payload)

        agent = ScriptedAgent([
            '<tool_call>{"name":"system_capabilities","args":{}}</tool_call>',
            "Capacidades verificadas.",
        ])
        reply = await agent.run("ver capacidades", broadcast=broadcast)

        self.assertEqual(reply, "Capacidades verificadas.")
        stages = [event.get("stage") for event in events if event.get("type") == "AGENT_PROGRESS"]
        self.assertIn("tool_running", stages)
        self.assertIn("tool_done", stages)
        self.assertIn("completed", stages)


if __name__ == "__main__":
    unittest.main()
