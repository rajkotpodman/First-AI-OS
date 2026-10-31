#!/usr/bin/env python3
"""
test_dependency_resolver.py - Comprehensive Unit Tests for Dependency Resolver Engine
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from dependency_resolver import (
    ErrorPatternDetector,
    ProjectManifestScanner,
    DependencyLogger,
    DependencyResolver,
    PackageManagerAdapter,
    COMMAND_TO_SYSTEM_PKG
)

class TestErrorPatternDetector(unittest.TestCase):
    """Test pattern recognition across stderr/stdout streams."""

    def test_command_not_found_patterns(self):
        cases = [
            ("/bin/sh: jq: not found", [("command", "jq")]),
            ("bash: git: command not found", [("command", "git")]),
            ("curl: command not found", [("command", "curl")]),
            ("'ffmpeg' is not recognized as an internal or external command", [("command", "ffmpeg")]),
        ]
        for error_text, expected in cases:
            results = ErrorPatternDetector.identify_missing(error_text)
            self.assertEqual(results, expected, f"Failed matching: {error_text}")

    def test_python_module_not_found_patterns(self):
        cases = [
            ("ModuleNotFoundError: No module named 'requests'", [("python_module", "requests")]),
            ("ModuleNotFoundError: No module named 'yaml'", [("python_module", "PyYAML")]),
            ("ModuleNotFoundError: No module named 'PIL.Image'", [("python_module", "Pillow")]),
            ("ImportError: cannot import name 'FastAPI' from 'fastapi'", [("python_module", "fastapi")]),
        ]
        for error_text, expected in cases:
            results = ErrorPatternDetector.identify_missing(error_text)
            self.assertEqual(results, expected, f"Failed matching: {error_text}")

    def test_node_module_not_found_patterns(self):
        cases = [
            ("Error: Cannot find module 'express'", [("node_module", "express")]),
            ("Cannot find module '@types/node'", [("node_module", "@types/node")]),
        ]
        for error_text, expected in cases:
            results = ErrorPatternDetector.identify_missing(error_text)
            self.assertEqual(results, expected, f"Failed matching: {error_text}")

    def test_c_header_not_found(self):
        error_text = "fatal error: openssl/ssl.h: No such file or directory"
        results = ErrorPatternDetector.identify_missing(error_text)
        self.assertEqual(results, [("c_header", "openssl/ssl")])

class TestProjectManifestScanner(unittest.TestCase):
    """Test project source file scanning capabilities."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_manifest_parsing(self):
        # Create mock requirements.txt
        (self.base_path / "requirements.txt").write_text("fastapi>=0.100\nuvicorn\n# comment\n", encoding="utf-8")
        # Create mock package.json
        (self.base_path / "package.json").write_text('{"name": "test-app"}', encoding="utf-8")
        # Create mock Makefile
        (self.base_path / "Makefile").write_text("all:\n\techo build\n", encoding="utf-8")

        manifest = ProjectManifestScanner.scan_directory(str(self.base_path))
        self.assertIn("fastapi>=0.100", manifest["pip"])
        self.assertIn("uvicorn", manifest["pip"])
        self.assertIn("install", manifest["npm"])
        self.assertIn("make", manifest["system"])

class TestDependencyLogger(unittest.TestCase):
    """Test logging mechanism and permission fallback."""

    def test_logger_writes(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            log_file = tmp.name

        try:
            logger = DependencyLogger(log_file)
            logger.log("INFO", "Test message", {"code": 200})

            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[INFO] Test message", content)
            self.assertIn("'code': 200", content)
        finally:
            if os.path.exists(log_file):
                os.remove(log_file)

class TestDependencyResolverAutoHealing(unittest.TestCase):
    """Test auto-healing execution loop with mocked package manager."""

    @patch.object(PackageManagerAdapter, "install_system_package", return_value=True)
    @patch.object(DependencyResolver, "verify_binary_in_path", return_value=True)
    def test_auto_heal_intercept_command(self, mock_verify, mock_install):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            log_file = tmp.name

        try:
            resolver = DependencyResolver(log_path=log_file)
            healed, msg = resolver.intercept_and_heal(
                exit_code=127,
                stderr="/bin/sh: jq: not found",
                stdout="",
                original_cmd="jq . config.json"
            )
            self.assertTrue(healed)
            mock_install.assert_called_with("jq")
            mock_verify.assert_called_with("jq")
        finally:
            if os.path.exists(log_file):
                os.remove(log_file)

    @patch.object(PackageManagerAdapter, "install_pip_package", return_value=True)
    def test_auto_heal_intercept_python_module(self, mock_pip_install):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            log_file = tmp.name

        try:
            resolver = DependencyResolver(log_path=log_file)
            healed, msg = resolver.intercept_and_heal(
                exit_code=1,
                stderr="ModuleNotFoundError: No module named 'yaml'",
                stdout="",
                original_cmd="python app.py"
            )
            self.assertTrue(healed)
            mock_pip_install.assert_called_with("PyYAML")
        finally:
            if os.path.exists(log_file):
                os.remove(log_file)

if __name__ == "__main__":
    unittest.main()
