#!/usr/bin/env python3
"""
test_project_architect.py - Unit tests for Autonomous Project Architect Engine
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from project_architect import BlueprintValidator, ProjectArchitect

class TestBlueprintValidator(unittest.TestCase):
    """Test blueprint extraction and path traversal prevention."""

    def test_parse_valid_blueprint(self):
        raw = """Here is the blueprint:
```json
{
  "project_name": "micro_auth_api",
  "description": "Auth service with JWT",
  "runtime": "python",
  "files": [
    {"path": "main.py", "content": "print('hello')", "description": "Entrypoint"}
  ]
}
```
"""
        bp = BlueprintValidator.parse_blueprint(raw)
        self.assertIsNotNone(bp)
        self.assertEqual(bp["project_name"], "micro_auth_api")
        self.assertEqual(len(bp["files"]), 1)

    def test_sanitize_path_traversal(self):
        base = Path("/workspace/projects/demo").resolve()
        # Valid path
        safe = BlueprintValidator.sanitize_path(base, "app/routes/users.py")
        self.assertIsNotNone(safe)
        self.assertTrue(safe.is_relative_to(base))

        # Traversal attack
        unsafe = BlueprintValidator.sanitize_path(base, "../../etc/shadow")
        self.assertIsNone(unsafe)

class TestProjectScaffolder(unittest.TestCase):
    """Test directory tree creation and file scaffolding."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.architect = ProjectArchitect(projects_root=self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_scaffold_project_files(self):
        blueprint = {
            "project_name": "test_service",
            "runtime": "python",
            "files": [
                {"path": "src/app.py", "content": "def main(): pass", "description": "App"},
                {"path": "config/settings.json", "content": '{"port": 8080}', "description": "Config"},
                {"path": "README.md", "content": "# Test Service", "description": "Docs"}
            ]
        }

        success, proj_path, created = self.architect.scaffold_project(blueprint)
        self.assertTrue(success)
        self.assertTrue((proj_path / "src" / "app.py").exists())
        self.assertTrue((proj_path / "config" / "settings.json").exists())
        self.assertTrue((proj_path / "README.md").exists())
        self.assertTrue((proj_path / ".gitignore").exists())
        self.assertTrue((proj_path / ".ai_blueprint.json").exists())

        # Verify content
        app_content = (proj_path / "src" / "app.py").read_text(encoding="utf-8")
        self.assertEqual(app_content, "def main(): pass")

class TestProjectArchitectBuildLifecycle(unittest.TestCase):
    """Test the complete build lifecycle with mock router."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_build_project_pipeline(self):
        mock_router = MagicMock()
        mock_blueprint = {
            "project_name": "demo_pipeline",
            "runtime": "python",
            "files": [
                {"path": "hello.py", "content": "print('hello')", "description": "Entry"}
            ],
            "test_command": "true"
        }
        mock_router.query.return_value = (True, f"```json\n{json.dumps(mock_blueprint)}\n```")

        architect = ProjectArchitect(
            projects_root=self.tmp_dir.name,
            router=mock_router,
            resolver=None,
            sandbox=None
        )

        result = architect.build_project("Build demo pipeline", run_verification=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["project_name"], "demo_pipeline")
        self.assertTrue(Path(result["project_path"]).exists())

if __name__ == "__main__":
    import json
    unittest.main()
