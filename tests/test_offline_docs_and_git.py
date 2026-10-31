#!/usr/bin/env python3
"""
test_offline_docs_and_git.py - Verification Test Suite for:
1. Offline Documentation Search Module (offline_docs_engine.py, index_docs.py, ai_doc.py)
2. Autonomous Git & Version Control Subsystem (git_automator.py)
3. Integration hooks in project_architect.py and self_healer.py
"""

import os
import sys
import shutil
import unittest
import tempfile
from pathlib import Path

# Add src to sys.path
TEST_DIR = Path(__file__).parent.resolve()
SRC_DIR = (TEST_DIR.parent / "src").resolve()
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from offline_docs_engine import OfflineDocsEngine
from index_docs import DocsIndexer, MarkdownDocParser, SimpleHTMLDocParser
from git_automator import GitAutomator, GITIGNORE_TEMPLATES
from project_architect import ProjectArchitect
from self_healer import SelfHealer


class TestOfflineDocsEngine(unittest.TestCase):
    """Test suite for offline documentation search & context injection."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="aios_test_docs_")
        self.engine = OfflineDocsEngine(storage_dir=self.temp_dir)
        self.indexer = DocsIndexer(self.engine)
        self.indexer.seed_default_documentation(force=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_initialization(self):
        stats = self.engine.get_stats()
        self.assertGreaterEqual(stats["total_entries"], 20)
        self.assertGreaterEqual(stats["total_docsets"], 5)
        self.assertTrue(self.engine.db_path.exists())

    def test_search_docs_python(self):
        results = self.engine.search_docs("json.dumps", language="python", limit=3)
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertEqual(top.symbol, "json.dumps")
        self.assertEqual(top.language, "python")
        self.assertIn("indent", top.signature)

    def test_search_docs_node(self):
        results = self.engine.search_docs("readFileSync", language="node", limit=3)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].symbol, "fs.readFileSync")

    def test_get_api_signature(self):
        sig = self.engine.get_api_signature("subprocess.run", language="python")
        self.assertIsNotNone(sig)
        self.assertEqual(sig.symbol, "subprocess.run")
        self.assertIn("CompletedProcess", sig.return_type)
        self.assertTrue(len(sig.parameters) > 0)
        self.assertTrue(len(sig.code_example) > 0)

    def test_context_injection_for_error(self):
        error_msg = "AttributeError: module 'json' has no attribute 'dumps'"
        context = self.engine.get_doc_context_for_error(error_msg, language="python")
        self.assertIn("OFFLINE DOCUMENTATION CONTEXT", context)
        self.assertIn("json.dumps", context)
        self.assertIn("Official Example", context)

    def test_markdown_and_html_parsers(self):
        # Markdown
        md = "# My API\n\n```python\nprint(1)\n```\nSome description."
        parsed_md = MarkdownDocParser.parse_markdown(md)
        self.assertEqual(parsed_md["title"], "My API")
        self.assertEqual(len(parsed_md["code_snippets"]), 1)

        # HTML
        html = "<html><h1>Web Title</h1><pre><code>const a = 1;</code></pre><p>Description</p></html>"
        parser = SimpleHTMLDocParser()
        parser.feed(html)
        self.assertEqual(parser.headers[0][1], "Web Title")
        self.assertTrue(len(parser.code_chunks) > 0)


class TestGitAutomator(unittest.TestCase):
    """Test suite for autonomous Git version control & rollback system."""

    def setUp(self):
        self.temp_repo = Path(tempfile.mkdtemp(prefix="aios_test_git_"))
        self.automator = GitAutomator()

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    def test_init_repository_with_stack_gitignore(self):
        ok, msg = self.automator.init_repository(self.temp_repo, stack="python", default_branch="main")
        self.assertTrue(ok)
        self.assertTrue(self.automator.is_git_repo(self.temp_repo))

        # Verify .gitignore content
        gitignore_path = self.temp_repo / ".gitignore"
        self.assertTrue(gitignore_path.exists())
        content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn("__pycache__", content)
        self.assertIn(".pytest_cache", content)

    def test_status_and_auto_commit(self):
        self.automator.init_repository(self.temp_repo, stack="node", default_branch="main")

        # Create new source file
        src_file = self.temp_repo / "server.js"
        src_file.write_text("const http = require('http');\n")

        status = self.automator.get_status(self.temp_repo)
        self.assertFalse(status.clean)
        self.assertIn("server.js", status.untracked_files)

        # Auto commit
        ok, msg, sha = self.automator.auto_commit(self.temp_repo, task_context="Add HTTP server entrypoint")
        self.assertTrue(ok)
        self.assertTrue(len(sha) >= 7)
        self.assertTrue(msg.startswith("feat"))

        new_status = self.automator.get_status(self.temp_repo)
        self.assertTrue(new_status.clean)

    def test_checkpoint_and_rollback(self):
        self.automator.init_repository(self.temp_repo, stack="python")

        code_file = self.temp_repo / "calc.py"
        code_file.write_text("def add(a, b): return a + b\n")
        self.automator.auto_commit(self.temp_repo, custom_message="feat(calc): working add function")

        # Create checkpoint before destructive change
        cp = self.automator.create_checkpoint(self.temp_repo, reason="before_breaking_refactor")
        self.assertTrue(cp.tag_name.startswith("checkpoint-"))

        # Corrupt file
        code_file.write_text("syntax error !!! broken code")
        status = self.automator.get_status(self.temp_repo)
        self.assertFalse(status.clean)

        # Rollback
        rb_ok, rb_msg = self.automator.rollback_to_commit(self.temp_repo, cp.commit_sha, hard=True)
        self.assertTrue(rb_ok)
        self.assertEqual(code_file.read_text(), "def add(a, b): return a + b\n")

    def test_feature_branching_and_merge(self):
        self.automator.init_repository(self.temp_repo, stack="generic", default_branch="main")

        # Create feature branch
        b_ok, _ = self.automator.create_feature_branch(self.temp_repo, "ai-fix/issue-42", checkout=True)
        self.assertTrue(b_ok)

        status = self.automator.get_status(self.temp_repo)
        self.assertEqual(status.current_branch, "ai-fix/issue-42")

        # Add commit on feature branch
        (self.temp_repo / "fix.txt").write_text("resolved\n")
        self.automator.auto_commit(self.temp_repo, custom_message="fix: resolve issue 42")

        # Merge back into main
        m_ok, m_msg = self.automator.merge_branch(self.temp_repo, source_branch="ai-fix/issue-42", target_branch="main")
        self.assertTrue(m_ok)
        self.assertTrue((self.temp_repo / "fix.txt").exists())


class TestSubsystemIntegrations(unittest.TestCase):
    """Test suite verifying integration of GitAutomator & OfflineDocsEngine into project_architect & self_healer."""

    def setUp(self):
        self.temp_proj = Path(tempfile.mkdtemp(prefix="aios_test_integ_"))

    def tearDown(self):
        shutil.rmtree(self.temp_proj, ignore_errors=True)

    def test_project_architect_git_hook(self):
        architect = ProjectArchitect(projects_root=str(self.temp_proj))
        self.assertIsNotNone(architect.git_automator)

        dummy_blueprint = {
            "project_name": "sample_service",
            "runtime": "python",
            "files": [
                {"path": "main.py", "content": "print('hello')", "executable": False}
            ]
        }
        ok, p_dir, files = architect.scaffold_project(dummy_blueprint)
        self.assertTrue(ok)
        self.assertTrue((p_dir / ".gitignore").exists())

        git_ok = architect.initialize_git(p_dir, stack="python", project_name="sample_service")
        self.assertTrue(git_ok)
        self.assertTrue(architect.git_automator.is_git_repo(p_dir))

    def test_self_healer_git_and_docs_hook(self):
        healer = SelfHealer(max_retries=1)
        self.assertIsNotNone(healer.git_automator)
        self.assertIsNotNone(healer.docs_engine)

        # Initialize mock repo with passing test
        healer.git_automator.init_repository(self.temp_proj, stack="python")
        (self.temp_proj / "test_ok.py").write_text("""
import unittest
class SimpleTest(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(1, 1)
if __name__ == '__main__':
    unittest.main()
""")
        healer.git_automator.auto_commit(self.temp_proj, custom_message="feat: initial passing test")

        # Run auto_heal_project; should pass immediately without needing patch
        res = healer.auto_heal_project(str(self.temp_proj), custom_test_cmd=f'"{sys.executable}" -m unittest test_ok.py')
        self.assertTrue(res.resolved)
        self.assertEqual(res.iterations_run, 0)


if __name__ == "__main__":
    unittest.main()
