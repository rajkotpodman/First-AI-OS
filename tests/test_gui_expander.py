#!/usr/bin/env python3
"""
test_gui_expander.py - Unit tests for Dynamic GUI Expander Subsystem
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gui_expander import GUIExpander

class TestGUIExpanderTriggers(unittest.TestCase):
    """Test user natural language trigger matching for GUI expander."""

    def setUp(self):
        self.expander = GUIExpander()

    def test_gui_enable_triggers(self):
        positive_triggers = [
            "Give me GUI",
            "Open desktop",
            "start gui",
            "switch to desktop",
            "launch wayland",
            "I need a browser",
            "open browser",
            "gui start",
            "gui --enable",
            "chromium https://github.com",
            "firefox"
        ]
        for phrase in positive_triggers:
            self.assertTrue(self.expander.is_gui_trigger(phrase), f"Failed to match trigger: '{phrase}'")

    def test_non_gui_triggers(self):
        negative_triggers = [
            "ls -la",
            "Build a REST API in Python",
            "git status",
            "what is my memory usage?",
            "docker ps"
        ]
        for phrase in negative_triggers:
            self.assertFalse(self.expander.is_gui_trigger(phrase), f"Falsely matched non-GUI phrase: '{phrase}'")

    def test_gui_disable_triggers(self):
        disable_phrases = [
            "Exit GUI",
            "close desktop",
            "stop wayland",
            "disable gui",
            "gui --disable",
            "gui stop"
        ]
        for phrase in disable_phrases:
            self.assertTrue(self.expander.is_gui_disable_trigger(phrase), f"Failed to match disable: '{phrase}'")

class TestGUIConfigDeployment(unittest.TestCase):
    """Test template copying and configuration file generation in user home directory."""

    def setUp(self):
        self.tmp_home = tempfile.TemporaryDirectory()
        self.expander = GUIExpander()

    def tearDown(self):
        self.tmp_home.cleanup()

    @patch("pathlib.Path.home")
    def test_deploy_configurations(self, mock_home):
        mock_home.return_value = Path(self.tmp_home.name)

        success = self.expander.deploy_user_configurations()
        self.assertTrue(success)

        home = Path(self.tmp_home.name)
        sway_cfg = home / ".config" / "sway" / "config"
        waybar_cfg = home / ".config" / "waybar" / "config"
        waybar_style = home / ".config" / "waybar" / "style.css"
        foot_cfg = home / ".config" / "foot" / "foot.ini"

        self.assertTrue(sway_cfg.exists(), "sway/config not generated")
        self.assertTrue(waybar_cfg.exists(), "waybar/config not generated")
        self.assertTrue(waybar_style.exists(), "waybar/style.css not generated")
        self.assertTrue(foot_cfg.exists(), "foot/foot.ini not generated")

        # Verify content
        sway_content = sway_cfg.read_text(encoding="utf-8")
        self.assertIn("set $term foot", sway_content)
        self.assertIn("swaybar_command waybar", sway_content)

class TestGUIPackageVerification(unittest.TestCase):
    """Test package presence detection."""

    @patch("shutil.which")
    def test_verify_packages_installed(self, mock_which):
        mock_which.return_value = "/usr/bin/tool"
        expander = GUIExpander()
        installed, missing = expander.verify_packages()
        self.assertTrue(installed)
        self.assertEqual(len(missing), 0)

    @patch("shutil.which", return_value=None)
    def test_verify_packages_missing(self, mock_which):
        expander = GUIExpander()
        installed, missing = expander.verify_packages()
        self.assertFalse(installed)
        self.assertIn("sway", missing)
        self.assertIn("waybar", missing)
        self.assertIn("foot", missing)

if __name__ == "__main__":
    unittest.main()
