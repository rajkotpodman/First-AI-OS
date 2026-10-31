#!/usr/bin/env python3
"""
test_cron_and_plugins.py - Verification Test Suite for:
1. Autonomous Task Scheduler & Background Cron Daemon (ai_cron_daemon.py, ai_schedule.py)
2. AI OS Modular Plugin Subsystem & Security Sandbox (plugin_manager.py, github_status_plugin)
3. Integration with ai_shell_agent.py
"""

import os
import sys
import json
import shutil
import unittest
import tempfile
from pathlib import Path
from datetime import datetime

# Add src to sys.path
TEST_DIR = Path(__file__).parent.resolve()
SRC_DIR = (TEST_DIR.parent / "src").resolve()
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ai_cron_daemon import (
    AICronDaemon, ScheduleParser, NotificationHub, TaskExecutors, ScheduledTask
)
from plugin_manager import (
    PluginManager, ManifestValidator, PluginContext, PluginManifest, SandboxedRunner
)
from ai_shell_agent import AIShellAgent


class TestCronDaemon(unittest.TestCase):
    """Test suite for task scheduler daemon & schedule parser."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="aios_test_cron_")
        self.tasks_file = os.path.join(self.temp_dir, "tasks.json")
        self.log_file = os.path.join(self.temp_dir, "ai_cron.log")
        self.notif_file = os.path.join(self.temp_dir, "notifications.json")
        self.daemon = AICronDaemon(
            tasks_file=self.tasks_file,
            log_file=self.log_file,
            notifications_file=self.notif_file
        )

    def tearDown(self):
        if hasattr(self.daemon, "close"):
            self.daemon.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_schedule_parser_natural_language(self):
        # Every 30 minutes
        cron30 = ScheduleParser.natural_to_cron("Every 30 minutes")
        self.assertEqual(cron30, "*/30 * * * *")

        # Every day at 2 AM
        cron2am = ScheduleParser.natural_to_cron("Every day at 2 AM")
        self.assertEqual(cron2am, "0 2 * * *")

        # Daily at midnight
        cron_midnight = ScheduleParser.natural_to_cron("Daily at midnight")
        self.assertEqual(cron_midnight, "0 0 * * *")

        # Weekdays at 8:00
        cron_weekdays = ScheduleParser.natural_to_cron("Every weekday at 8:00")
        self.assertEqual(cron_weekdays, "0 8 * * 1-5")

        # Sub-minute
        cron_submin = ScheduleParser.natural_to_cron("Every 10 seconds")
        self.assertEqual(cron_submin, "@every 10s")

    def test_next_run_calculation(self):
        now = datetime(2026, 10, 28, 10, 0, 0)
        # Next 30-min run
        next_run = ScheduleParser.calculate_next_run("*/30 * * * *", from_dt=now)
        self.assertEqual(next_run, datetime(2026, 10, 28, 10, 30, 0))

        # Next daily 2 AM run
        next_daily = ScheduleParser.calculate_next_run("0 2 * * *", from_dt=now)
        self.assertEqual(next_daily, datetime(2026, 10, 29, 2, 0, 0))

    def test_default_tasks_and_add_remove(self):
        tasks = self.daemon.load_tasks()
        self.assertGreaterEqual(len(tasks), 3)

        # Add custom task
        new_task = self.daemon.add_task(
            name="Test Custom Command",
            schedule_input="Every 5 minutes",
            task_type="custom_command",
            config={"command": f'"{sys.executable}" -c "print(42)"'}
        )
        self.assertEqual(new_task.schedule, "*/5 * * * *")

        reloaded = self.daemon.load_tasks()
        self.assertTrue(any(t.id == new_task.id for t in reloaded))

        # Remove task
        ok = self.daemon.remove_task(new_task.id)
        self.assertTrue(ok)
        self.assertFalse(any(t.id == new_task.id for t in self.daemon.load_tasks()))

    def test_task_execution_and_notifications(self):
        # Create custom command task
        test_task = ScheduledTask(
            id="test_notif",
            name="Notification Test",
            schedule="* * * * *",
            natural_schedule="Every minute",
            task_type="custom_command",
            enabled=True,
            config={"command": f'"{sys.executable}" -c "print(\\"Daemon Task Success\\")"'}
        )
        success, output = self.daemon.execute_task(test_task)
        self.assertTrue(success)
        self.assertIn("Daemon Task Success", output)

        # Verify notification was queued
        notifications = self.daemon.notifications.get_all()
        self.assertTrue(len(notifications) > 0)
        self.assertEqual(notifications[0]["level"], "success")
        self.assertIn("Notification Test", notifications[0]["title"])


class TestPluginSubsystem(unittest.TestCase):
    """Test suite for plugin manager, security sandbox, and manifest validator."""

    def setUp(self):
        self.temp_plugins_dir = Path(tempfile.mkdtemp(prefix="aios_test_plugins_"))
        self.pm = PluginManager(plugin_dirs=[str(self.temp_plugins_dir)])

    def tearDown(self):
        shutil.rmtree(self.temp_plugins_dir, ignore_errors=True)

    def test_manifest_validation(self):
        valid_manifest = {
            "name": "sample_tool",
            "version": "1.0.0",
            "description": "Sample test tool",
            "author": "Tester",
            "entrypoint": "main.py",
            "triggers": ["run sample", "sample tool"],
            "permissions": ["network", "filesystem_read"]
        }
        sample_dir = self.temp_plugins_dir / "sample_tool"
        sample_dir.mkdir(parents=True)
        (sample_dir / "main.py").write_text("def execute(ctx): return 'ok'")

        ok, manifest, reason = ManifestValidator.validate(valid_manifest, sample_dir)
        self.assertTrue(ok)
        self.assertEqual(manifest.name, "sample_tool")

        # Invalid permission
        invalid_manifest = dict(valid_manifest)
        invalid_manifest["permissions"] = ["invalid_super_admin"]
        bad_ok, _, _ = ManifestValidator.validate(invalid_manifest, sample_dir)
        self.assertFalse(bad_ok)

    def test_security_sandbox_runner_permissions(self):
        # Runner with execute_command NOT granted
        runner_blocked = SandboxedRunner(allowed=False, plugin_name="blocked_plugin")
        with self.assertRaises(PermissionError):
            runner_blocked.run("echo test")

        # Runner with execute_command granted
        runner_allowed = SandboxedRunner(allowed=True, plugin_name="allowed_plugin")
        code, out, _ = runner_allowed.run(f'"{sys.executable}" -c "print(100 + 23)"')
        self.assertEqual(code, 0)
        self.assertIn("123", out)

    def test_github_status_plugin_discovery_and_execution(self):
        # Load local plugins including github_status_plugin
        local_plugins = Path(__file__).parent.parent / "plugins"
        pm = PluginManager(plugin_dirs=[str(local_plugins)])
        self.assertIn("github_status_plugin", pm.plugins)

        # Trigger intent matching
        match = pm.match_intent("please check github status for me")
        self.assertIsNotNone(match)
        plugin, trigger, confidence = match
        self.assertEqual(plugin.manifest.name, "github_status_plugin")
        self.assertGreaterEqual(confidence, 0.8)

        # Execute matching plugin
        result = pm.execute_matching_plugin("github status")
        self.assertTrue(result.success)
        self.assertIn("GitHub & Repository Status Report", result.content)


class TestShellAgentIntegration(unittest.TestCase):
    """Verifies that AIShellAgent initializes PluginManager and AICronDaemon."""

    def test_agent_subsystem_attachments(self):
        agent = AIShellAgent()
        self.assertIsNotNone(agent.plugin_manager)
        self.assertIsNotNone(agent.cron_daemon)
        self.assertTrue(len(agent.plugin_manager.plugins) > 0)


if __name__ == "__main__":
    unittest.main()
