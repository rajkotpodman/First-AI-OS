#!/usr/bin/env python3
"""
test_self_healer.py - Unit tests for Automated Self-Debugging & Patching Engine
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from self_healer import DiffPatcher, ErrorAnalyzer, SelfHealer

class TestDiffPatcher(unittest.TestCase):
    """Test unified diff parsing and application."""

    def test_apply_unified_diff_clean(self):
        original = """def add(a, b):
    # Broken implementation
    return a - b

def multiply(a, b):
    return a * b
"""
        patch_text = """--- a/math_ops.py
+++ b/math_ops.py
@@ -2,3 +2,3 @@
-    # Broken implementation
-    return a - b
+    # Fixed implementation
+    return a + b
"""
        ok, updated, msg = DiffPatcher.apply_unified_diff(original, patch_text)
        self.assertTrue(ok, f"Patch failed: {msg}")
        self.assertIn("return a + b", updated)
        self.assertNotIn("return a - b", updated)

    def test_extract_patch_json(self):
        response = """Here is the fix:
```json
{
  "target_file": "app/calculator.py",
  "root_cause": "Subtraction operator used instead of addition",
  "unified_diff": "--- a/app/calculator.py\\n+++ b/app/calculator.py\\n@@ -1,2 +1,2 @@\\n-old\\n+new"
}
```
"""
        data = DiffPatcher.extract_patch_from_response(response)
        self.assertEqual(data.get("target_file"), "app/calculator.py")
        self.assertIn("Subtraction operator", data.get("root_cause"))

class TestErrorAnalyzer(unittest.TestCase):
    """Test extracting file paths, lines, and stack traces."""

    def test_python_traceback_analysis(self):
        stderr = """Traceback (most recent call last):
  File "/workspace/projects/demo/app/main.py", line 42, in process_data
    result = calculate_total(items)
  File "/workspace/projects/demo/app/calculator.py", line 15, in calculate_total
    return 10 / divisor
ZeroDivisionError: division by zero
"""
        ctx = ErrorAnalyzer.analyze_failure(Path("/workspace/projects/demo"), stderr, "")
        self.assertEqual(ctx.line_number, 15)
        self.assertIn("calculator.py", str(ctx.failed_file))
        self.assertEqual(ctx.exception_type, "ZeroDivisionError")
        self.assertIn("ZeroDivisionError: division by zero", ctx.error_summary)

class TestSelfHealingSimulation(unittest.TestCase):
    """Simulates end-to-end auto-fixing of a broken Python script."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp_dir.name)

        # Create broken script
        (self.base / "calc.py").write_text("""def compute(x):
    # Bug: incorrect calculation
    return x * 10
""", encoding="utf-8")

        # Create test that expects compute(5) == 25
        (self.base / "test_calc.py").write_text("""import unittest
from calc import compute

class TestCompute(unittest.TestCase):
    def test_logic(self):
        self.assertEqual(compute(5), 25)

if __name__ == '__main__':
    unittest.main()
""", encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_simulation_auto_patch_loop(self):
        # Mock the AI Router to return the fix
        mock_router = MagicMock()
        mock_fix_response = """```json
{
  "target_file": "calc.py",
  "root_cause": "Multiplied by 10 instead of squaring or multiplying by 5",
  "new_content": "def compute(x):\\n    return x * 5\\n"
}
```"""
        mock_router.query.return_value = (True, mock_fix_response)

        healer = SelfHealer(max_retries=2, router=mock_router, sandbox=None)
        summary = healer.auto_heal_project(str(self.base))

        # Check that tests now pass
        self.assertTrue(summary.resolved)
        self.assertEqual(summary.iterations_run, 1)

        # Verify content was updated on disk
        updated_code = (self.base / "calc.py").read_text(encoding="utf-8")
        self.assertIn("return x * 5", updated_code)

        # Verify diagnostic report was written
        report_file = self.base / "debug_summary.json"
        self.assertTrue(report_file.exists())

if __name__ == "__main__":
    unittest.main()
