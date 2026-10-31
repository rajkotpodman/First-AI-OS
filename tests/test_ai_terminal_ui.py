#!/usr/bin/env python3
"""
test_ai_terminal_ui.py - Unit tests for Rich Terminal TTY UI & Interactive AI Dashboard
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ai_terminal_ui import (
    AITerminalUI,
    AIStreamStdoutWrapper
)


class TestAITerminalUI(unittest.TestCase):
    """Test suite for Terminal UI rendering, metrics, streaming, and activity spinners."""

    def setUp(self):
        self.ui = AITerminalUI(force_terminal=False)

    def test_metrics_collection(self):
        metrics = self.ui.get_system_metrics()
        self.assertIn("cpu_percent", metrics)
        self.assertIn("ram_percent", metrics)
        self.assertIn("online", metrics)
        self.assertIsInstance(metrics["cpu_percent"], (int, float))
        self.assertIsInstance(metrics["ram_percent"], (int, float))
        self.assertIsInstance(metrics["online"], bool)

    def test_render_header(self):
        # Ensure render_header runs without throwing errors
        try:
            self.ui.render_header(model="test-model", cwd="/workspace")
        except Exception as e:
            self.fail(f"render_header raised an exception: {e}")

    def test_render_status_bar(self):
        try:
            self.ui.render_status_bar(model="test-model", cwd="/workspace")
        except Exception as e:
            self.fail(f"render_status_bar raised an exception: {e}")

    def test_render_markdown_and_code(self):
        sample_md = """# Title
- Item 1
- Item 2

```python
x = 42
print(x)
```
"""
        try:
            self.ui.render_markdown(sample_md)
            self.ui.render_code_block("const a = 10;", language="javascript")
        except Exception as e:
            self.fail(f"render_markdown or render_code_block raised an exception: {e}")

    def test_render_table_and_badges(self):
        headers = ["Subsystem", "Status"]
        rows = [["Network", "Active"], ["Memory", "OK"]]
        try:
            self.ui.render_table("Test Table", headers, rows)
            self.ui.render_badge("Kernel Ready", "READY")
            self.ui.render_badge("Disk warning", "WARNING")
            self.ui.render_badge("Critical error", "ERROR")
        except Exception as e:
            self.fail(f"render_table or render_badge raised an exception: {e}")

    def test_stream_markdown(self):
        tokens = ["Hello ", "**World**", "!\n", "```bash\necho 123\n```"]
        res = self.ui.stream_markdown(iter(tokens))
        self.assertEqual(res, "Hello **World**!\n```bash\necho 123\n```")

    def test_activity_spinner(self):
        with self.ui.activity_spinner("Testing task", success_msg="Completed successfully"):
            pass

    def test_stream_stdout_wrapper(self):
        fake_stdout = io.StringIO()
        wrapper = AIStreamStdoutWrapper(self.ui)
        wrapper.original_stdout = fake_stdout

        wrapper.write("Token 1 ")
        wrapper.write("Token 2")
        wrapper.flush()

        self.assertEqual(wrapper.get_buffered_content(), "Token 1 Token 2")
        wrapper.clear()
        self.assertEqual(wrapper.get_buffered_content(), "")


if __name__ == "__main__":
    unittest.main()
