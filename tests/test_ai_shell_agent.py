#!/usr/bin/env python3
"""
test_ai_shell_agent.py - Unit tests for AI Shell Agent and Command Interpreter
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ai_shell_agent import (
    ActionParser,
    SafetyGuardrail,
    SystemContextEngine,
    AIShellAgent,
    AIRouter
)

class TestActionParser(unittest.TestCase):
    """Test JSON action parsing with various LLM response formats."""

    def test_clean_json_array(self):
        raw = '[{"action": "execute_shell", "command": "ls -la", "description": "List files"}]'
        actions = ActionParser.parse_actions(raw)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["action"], "execute_shell")
        self.assertEqual(actions[0]["command"], "ls -la")

    def test_markdown_code_fenced_json(self):
        raw = """Here is the plan:
```json
[
  {"action": "install_dep", "packages": ["requests"], "package_manager": "pip", "description": "Install requests"},
  {"action": "create_file", "path": "test.py", "content": "print('hello')", "description": "Create test script"}
]
```
I hope this helps!"""
        actions = ActionParser.parse_actions(raw)
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["action"], "install_dep")
        self.assertEqual(actions[1]["action"], "create_file")

    def test_unstructured_text_fallback(self):
        raw = "I am a helpful assistant. To do this, run python -V."
        actions = ActionParser.parse_actions(raw)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["action"], "message")
        self.assertIn("helpful assistant", actions[0]["content"])

class TestSafetyGuardrail(unittest.TestCase):
    """Test detection of destructive commands."""

    def setUp(self):
        patterns = [
            r"^rm\s+(-[a-zA-Z]*r[a-zA-Z]*f*|-f[a-zA-Z]*r[a-zA-Z]*)\s+.*(/|\*).*",
            r".*mkfs(\.[a-z0-9]+)?\s+.*",
            r".*dd\s+.*of=/dev/.*",
            r".*(shutdown|poweroff|reboot).*",
            r".*chmod\s+(-R\s+)?777\s+.*"
        ]
        self.guard = SafetyGuardrail(patterns)

    def test_destructive_commands(self):
        dangerous = [
            "rm -rf /",
            "rm -rf /home/user",
            "mkfs.ext4 /dev/sda1",
            "dd if=/dev/zero of=/dev/sdb bs=1M",
            "reboot",
            "chmod -R 777 /var"
        ]
        for cmd in dangerous:
            is_bad, reason = self.guard.is_destructive(cmd)
            self.assertTrue(is_bad, f"Failed to flag dangerous command: {cmd}")

    def test_safe_commands(self):
        safe = [
            "ls -la",
            "git commit -m 'Initial commit'",
            "mkdir -p /workspace/my_project",
            "cat /proc/cpuinfo",
            "python script.py"
        ]
        for cmd in safe:
            is_bad, reason = self.guard.is_destructive(cmd)
            self.assertFalse(is_bad, f"Falsely flagged safe command: {cmd}")

class TestCommandClassification(unittest.TestCase):
    """Test POSIX shell vs Natural Language classification."""

    def setUp(self):
        self.agent = AIShellAgent()

    def test_standard_shell_commands(self):
        shell_cmds = [
            "ls",
            "cd /workspace",
            "cat file.txt | grep error",
            "git status",
            "docker ps -a",
            "!build_script.sh"
        ]
        for cmd in shell_cmds:
            self.assertTrue(self.agent.is_standard_shell_command(cmd), f"Failed to identify shell cmd: {cmd}")

    def test_natural_language_queries(self):
        nl_queries = [
            "Build a full REST API for user authentication in Python",
            "Why is the docker service not starting?",
            "Create a clean web scraper using beautifulsoup",
            "How do I set up persistent storage in Alpine?"
        ]
        for q in nl_queries:
            self.assertFalse(self.agent.is_standard_shell_command(q), f"Incorrectly treated NL as shell: {q}")

class TestSystemContextEngine(unittest.TestCase):
    """Test OS state snapshot and prompt formatting."""

    def test_context_snapshot(self):
        ctx = SystemContextEngine.format_for_prompt()
        self.assertIn("[SYSTEM CONTEXT]", ctx)
        self.assertIn("CWD:", ctx)
        self.assertIn("Memory:", ctx)
        self.assertIn("Disk:", ctx)

if __name__ == "__main__":
    unittest.main()
