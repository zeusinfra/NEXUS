import os
import tempfile
import unittest
from unittest.mock import patch

from zeus_core.actions import cmd_control
from zeus_core.command_policy import validate_command
from zeus_core.tools import ToolError


class CommandPolicyTests(unittest.TestCase):
    def setUp(self):
        self._log_patcher = patch("zeus_core.command_policy.log_event")
        self._log_patcher.start()

    def tearDown(self):
        self._log_patcher.stop()

    def test_cmd_control_allows_allowlisted_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "ZEUS_PROJECT_ROOT": tmp,
                "ZEUS_CMD_ALLOWLIST": "python3",
            }
            with patch.dict(os.environ, env, clear=False):
                result = cmd_control({"command": "python3 --version", "timeout_s": 5})

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["category"], "read")
        self.assertIn("Python", result["stdout"] or result["stderr"])

    def test_cmd_control_rejects_command_outside_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "ZEUS_PROJECT_ROOT": tmp,
                "ZEUS_CMD_ALLOWLIST": "python3",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(ToolError, "allowlist"):
                    cmd_control({"command": "git status"})

    def test_cmd_control_blocks_rm_even_if_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "ZEUS_PROJECT_ROOT": tmp,
                "ZEUS_CMD_ALLOWLIST": "rm",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(ToolError, "bloqueado"):
                    cmd_control({"command": "rm something"})

    def test_cmd_control_rejects_shell_control_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "ZEUS_PROJECT_ROOT": tmp,
                "ZEUS_CMD_ALLOWLIST": "python3",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(ToolError, "shell bloqueado"):
                    cmd_control({"command": "python3 --version && git status"})

    def test_write_command_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "ZEUS_PROJECT_ROOT": tmp,
                "ZEUS_CMD_ALLOWLIST": "mkdir",
            }
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(ToolError, "confirmação"):
                    cmd_control({"command": "mkdir out"})

    def test_write_command_runs_when_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "ZEUS_PROJECT_ROOT": tmp,
                "ZEUS_CMD_ALLOWLIST": "mkdir",
            }
            with patch.dict(os.environ, env, clear=False):
                result = cmd_control({"command": "mkdir out", "confirmed": True})

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["category"], "write")
        self.assertTrue(result["requires_confirmation"])

    def test_command_policy_audits_allowed_and_rejected_decisions(self):
        self._log_patcher.stop()
        with patch("zeus_core.command_policy.log_event") as log_event:
            with patch.dict(os.environ, {"ZEUS_CMD_ALLOWLIST": "python3"}, clear=False):
                validate_command("python3 --version", ["python3", "--version"], confirmed=False)
                with self.assertRaises(ToolError):
                    validate_command("git status", ["git", "status"], confirmed=False)

        events = [call.args[2] for call in log_event.call_args_list]
        self.assertIn("command_policy_allowed", events)
        self.assertIn("command_policy_rejected", events)
        self._log_patcher.start()

    def test_interpreter_execution_flags_require_confirmation(self):
        with patch.dict(os.environ, {"ZEUS_CMD_ALLOWLIST": "python3,node"}, clear=False):
            with self.assertRaisesRegex(ToolError, "confirmação"):
                validate_command("python3 -c print(1)", ["python3", "-c", "print(1)"], confirmed=False)
            with self.assertRaisesRegex(ToolError, "confirmação"):
                validate_command("python3 script.py", ["python3", "script.py"], confirmed=False)
            with self.assertRaisesRegex(ToolError, "confirmação"):
                validate_command("node -e console.log(1)", ["node", "-e", "console.log(1)"], confirmed=False)

            py_decision = validate_command("python3 -c print(1)", ["python3", "-c", "print(1)"], confirmed=True)
            self.assertEqual(py_decision.category, "exec")


if __name__ == "__main__":
    unittest.main()
