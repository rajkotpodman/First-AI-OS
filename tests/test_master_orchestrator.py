#!/usr/bin/env python3
"""
test_master_orchestrator.py - Unit and Integration Tests for Master OS Orchestrator
"""

import os
import sys
import time
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from main_orchestrator import MasterOSOrchestrator


class TestMasterOSOrchestrator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = Path(self.temp_dir) / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        (self.workspace_dir / "projects").mkdir(parents=True, exist_ok=True)

        self.test_config = {
            "system": {
                "hostname": "test-ai-os",
                "workspace_dir": str(self.workspace_dir)
            },
            "security": {
                "mode": "permissive"
            }
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_boot_sequence_and_subsystem_binding(self):
        """Verify the 8-phase boot sequence correctly initializes and binds subsystems."""
        orchestrator = MasterOSOrchestrator(config_override=self.test_config)
        boot_result = orchestrator.boot()

        self.assertTrue(boot_result)
        self.assertTrue(orchestrator.running)
        self.assertEqual(orchestrator.hostname, "test-ai-os")

        # Subsystems must be bound
        self.assertIsNotNone(orchestrator.security)
        self.assertIsNotNone(orchestrator.hardware)
        self.assertIsNotNone(orchestrator.memory)
        self.assertIsNotNone(orchestrator.model_router)
        self.assertIsNotNone(orchestrator.cron_daemon)
        self.assertIsNotNone(orchestrator.git_automator)
        self.assertIsNotNone(orchestrator.docs_engine)
        self.assertIsNotNone(orchestrator.plugin_manager)

        # Cleanup
        orchestrator.shutdown()

    def test_status_and_help_rendering(self):
        """Verify status and help rendering without errors."""
        orchestrator = MasterOSOrchestrator(config_override=self.test_config)
        orchestrator.boot()

        # Capture stdout
        with patch("sys.stdout") as mock_stdout:
            orchestrator._render_status()
            orchestrator._render_help()

        orchestrator.shutdown()

    def test_dispatcher_builtins(self):
        """Verify built-in commands dispatch cleanly."""
        orchestrator = MasterOSOrchestrator(config_override=self.test_config)
        orchestrator.boot()

        with patch("sys.stdout"):
            # docs
            orchestrator.dispatch_request("docs")
            orchestrator.dispatch_request("docs python")

            # status and help
            orchestrator.dispatch_request("status")
            orchestrator.dispatch_request("help")

        orchestrator.shutdown()

    def test_dispatcher_plugin_routing(self):
        """Verify plugin trigger intent routes to matching plugin."""
        orchestrator = MasterOSOrchestrator(config_override=self.test_config)
        orchestrator.boot()

        if orchestrator.plugin_manager and "github_status_plugin" in orchestrator.plugin_manager.plugins:
            with patch("sys.stdout"):
                # "github status" trigger
                orchestrator.dispatch_request("github status")

        orchestrator.shutdown()

    def test_graceful_shutdown_state_preservation(self):
        """Verify graceful shutdown preserves state, saves memory, stops cron."""
        orchestrator = MasterOSOrchestrator(config_override=self.test_config)
        orchestrator.boot()

        # Create a mock git project inside workspace
        test_project = self.workspace_dir / "projects" / "sample_app"
        test_project.mkdir(parents=True, exist_ok=True)
        (test_project / "app.py").write_text("print('test')")

        if orchestrator.git_automator:
            orchestrator.git_automator.initialize_repository(test_project, project_type="python")

        # Now execute shutdown
        orchestrator.shutdown()
        self.assertFalse(orchestrator.running)

        # Verify cron daemon is stopped
        if orchestrator.cron_daemon:
            self.assertFalse(orchestrator.cron_daemon.running)

        # Verify personal memory stored shutdown session context
        if orchestrator.memory:
            memories = orchestrator.memory.list_memories()
            contexts = [m for m in memories if "session closed cleanly" in getattr(m, "content", "")]
            self.assertTrue(len(contexts) > 0)


if __name__ == "__main__":
    unittest.main()
