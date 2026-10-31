#!/usr/bin/env python3
"""
test_system_updater.py - Unit tests for Automated System Maintenance & Version Rollback Engine
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from system_updater import (
    SystemUpdater,
    SnapshotManifest,
    HealthCheckReport
)


class TestSystemUpdater(unittest.TestCase):
    """Test suite for snapshot backup, syntax linting, health checks, and rollback."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_root = os.path.join(self.tmp_dir.name, "ai_os_repo")
        self.backup_dir = os.path.join(self.tmp_dir.name, "backups")
        self.log_file = os.path.join(self.tmp_dir.name, "updates.log")

        # Create mock repository structure
        os.makedirs(os.path.join(self.repo_root, "src"), exist_ok=True)
        os.makedirs(os.path.join(self.repo_root, "configs"), exist_ok=True)

        # Write sample valid python file
        self.sample_py = os.path.join(self.repo_root, "src", "sample_module.py")
        with open(self.sample_py, "w", encoding="utf-8") as f:
            f.write("def sample_function():\n    return 'v1.0'\n")

        self.updater = SystemUpdater(
            repo_root=self.repo_root,
            backup_dir=self.backup_dir,
            log_path=self.log_file
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_snapshot_creation_and_listing(self):
        ok, snap_path = self.updater.create_snapshot(label="test_v1")
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(snap_path))

        snapshots = self.updater.list_snapshots()
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["label"], "test_v1")

    def test_syntax_verification_valid_and_invalid(self):
        # 1. Valid syntax
        valid_ok, errors = self.updater.verify_syntax()
        self.assertTrue(valid_ok)
        self.assertEqual(errors, [])

        # 2. Corrupt syntax
        with open(self.sample_py, "w", encoding="utf-8") as f:
            f.write("def broken_syntax(:\n    return False\n")

        invalid_ok, errors = self.updater.verify_syntax()
        self.assertFalse(invalid_ok)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("SyntaxError" in e for e in errors))

    def test_restore_snapshot(self):
        # Create initial snapshot with v1
        self.updater.create_snapshot(label="v1_stable")

        # Modify file to v2
        with open(self.sample_py, "w", encoding="utf-8") as f:
            f.write("def sample_function():\n    return 'v2.0_modified'\n")

        # Verify modified
        with open(self.sample_py, "r", encoding="utf-8") as f:
            self.assertIn("v2.0_modified", f.read())

        # Trigger rollback
        restore_ok, msg = self.updater.restore_snapshot()
        self.assertTrue(restore_ok)

        # Verify reverted to v1
        with open(self.sample_py, "r", encoding="utf-8") as f:
            self.assertIn("v1.0", f.read())

    def test_apply_update_with_guard_success(self):
        def _safe_update():
            with open(self.sample_py, "w", encoding="utf-8") as f:
                f.write("def sample_function():\n    return 'v2.0_safe'\n")
            return True

        ok, msg = self.updater.apply_update_with_guard(_safe_update, label="safe_update")
        self.assertTrue(ok)
        with open(self.sample_py, "r", encoding="utf-8") as f:
            self.assertIn("v2.0_safe", f.read())

    def test_apply_update_with_guard_automatic_rollback_on_syntax_error(self):
        # Initial v1
        with open(self.sample_py, "w", encoding="utf-8") as f:
            f.write("def sample_function():\n    return 'v1.0_stable'\n")

        def _bad_update():
            # Writes broken python syntax
            with open(self.sample_py, "w", encoding="utf-8") as f:
                f.write("this is completely invalid python code !!! syntax error")
            return True

        ok, msg = self.updater.apply_update_with_guard(_bad_update, label="bad_update")
        self.assertFalse(ok)
        self.assertIn("Automatic rollback executed", msg)

        # Verify automatic rollback restored v1.0_stable!
        with open(self.sample_py, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("v1.0_stable", content)

    def test_health_check_report(self):
        report = self.updater.health_check()
        self.assertIsInstance(report, HealthCheckReport)
        self.assertTrue(report.syntax_valid)
        self.assertIsInstance(report.to_dict(), dict)


if __name__ == "__main__":
    unittest.main()
