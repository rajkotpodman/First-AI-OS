#!/usr/bin/env python3
"""
test_sandbox_runner.py - Unit tests for Secure Isolated Execution Sandbox
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from sandbox_runner import SandboxRunner, DiagnosticReport

class TestSandboxRunnerRuntimeDetection(unittest.TestCase):
    """Test project runtime and test suite detection."""

    def setUp(self):
        self.runner = SandboxRunner(engine="docker")
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_python_runtime_detection(self):
        (self.base / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
        runtime = self.runner.detect_project_runtime(str(self.base))
        self.assertEqual(runtime, "python")
        test_cmd = self.runner.detect_test_command(str(self.base), runtime)
        self.assertIn("unittest", test_cmd)

    def test_node_runtime_detection(self):
        (self.base / "package.json").write_text("{}", encoding="utf-8")
        runtime = self.runner.detect_project_runtime(str(self.base))
        self.assertEqual(runtime, "node")
        test_cmd = self.runner.detect_test_command(str(self.base), runtime)
        self.assertEqual(test_cmd, "npm test")

    def test_rust_runtime_detection(self):
        (self.base / "Cargo.toml").write_text("[package]", encoding="utf-8")
        runtime = self.runner.detect_project_runtime(str(self.base))
        self.assertEqual(runtime, "rust")
        test_cmd = self.runner.detect_test_command(str(self.base), runtime)
        self.assertEqual(test_cmd, "cargo test")

    def test_go_runtime_detection(self):
        (self.base / "go.mod").write_text("module test", encoding="utf-8")
        runtime = self.runner.detect_project_runtime(str(self.base))
        self.assertEqual(runtime, "go")
        test_cmd = self.runner.detect_test_command(str(self.base), runtime)
        self.assertEqual(test_cmd, "go test ./...")

class TestSandboxSecurityFlags(unittest.TestCase):
    """Test resource limits, caps, and seccomp security arguments."""

    def test_security_args(self):
        runner = SandboxRunner(
            engine="docker",
            cpu_limit="1.5",
            memory_limit="1g",
            pids_limit="128"
        )
        args = runner.build_security_args()

        self.assertIn("--cpus=1.5", args)
        self.assertIn("--memory=1g", args)
        self.assertIn("--pids-limit=128", args)
        self.assertIn("--security-opt=no-new-privileges:true", args)
        self.assertIn("--cap-drop=ALL", args)
        self.assertIn("--cap-add=CHOWN", args)

class TestDiagnosticParsing(unittest.TestCase):
    """Test output parser extracting diagnostics from test results."""

    def setUp(self):
        self.runner = SandboxRunner(engine="docker")

    def test_unittest_failure_parsing(self):
        stdout = ""
        stderr = """
FAIL: test_addition (test_math.TestMath)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "test_math.py", line 10, in test_addition
    self.assertEqual(1 + 1, 3)
AssertionError: 2 != 3

----------------------------------------------------------------------
Ran 4 tests in 0.005s

FAILED (failures=1)
"""
        report = self.runner._parse_output(
            passed=False,
            exit_code=1,
            duration=0.5,
            command="python3 -m unittest",
            image="python:3.11-alpine",
            container_id="test-container",
            stdout=stdout,
            stderr=stderr
        )

        self.assertFalse(report.passed)
        self.assertEqual(report.tests_run, 4)
        self.assertEqual(report.failures_count, 1)
        self.assertIn("FAILED (failures=1)", report.error_summary)
        self.assertIn("test_addition", report.failed_test_names)

    def test_pytest_summary_parsing(self):
        stdout = "==================== 2 failed, 8 passed in 1.23s ===================="
        stderr = ""

        report = self.runner._parse_output(
            passed=False,
            exit_code=1,
            duration=1.23,
            command="pytest",
            image="python:3.11-alpine",
            container_id="test-container",
            stdout=stdout,
            stderr=stderr
        )

        self.assertEqual(report.tests_run, 10)
        self.assertEqual(report.failures_count, 2)
        self.assertIn("2 failed, 8 passed", report.error_summary)

class TestSandboxExecutionMock(unittest.TestCase):
    """Test subprocess invocation with mocked engine execution."""

    @patch("shutil.which", return_value="/usr/bin/docker")
    @patch.object(SandboxRunner, "is_engine_ready", return_value=(True, "Ready"))
    @patch("subprocess.run")
    def test_run_command_mock(self, mock_subproc, mock_ready, mock_which):
        mock_subproc.return_value = MagicMock(returncode=0, stdout="Success\n", stderr="")

        runner = SandboxRunner(engine="docker")
        report = runner.run_command(
            project_dir="/workspace/demo",
            command="echo 'Hello Sandbox'",
            image="alpine:latest",
            ports={8080: 80}
        )

        self.assertTrue(mock_subproc.called)
        args_passed = mock_subproc.call_args[0][0]
        self.assertEqual(args_passed[0], "docker")
        self.assertEqual(args_passed[1], "run")
        self.assertIn("-p", args_passed)
        self.assertIn("8080:80", args_passed)
        self.assertIn("alpine:latest", args_passed)

if __name__ == "__main__":
    unittest.main()
