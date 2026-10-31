#!/usr/bin/env python3
"""
test_system_indexer.py - Unit tests for System Indexer & Context Retrieval Engine
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from system_indexer import SystemIndexer, GitignoreMatcher, CodeASTExtractor

class TestCodeASTExtractor(unittest.TestCase):
    """Test AST symbol extraction across multiple programming languages."""

    def test_python_ast_extraction(self):
        code = '''
import os
from math import sqrt

class DataProcessor:
    """Processes analytical data."""
    def __init__(self, name):
        self.name = name

    def execute(self, items):
        return [i * 2 for i in items]

def helper_func(x, y):
    return x + y
'''
        symbols = CodeASTExtractor.extract_symbols(Path("test.py"), "python", code)
        names = [s["symbol_name"] for s in symbols]

        self.assertIn("DataProcessor", names)
        self.assertIn("DataProcessor.__init__", names)
        self.assertIn("DataProcessor.execute", names)
        self.assertIn("helper_func", names)
        self.assertIn("os", names)
        self.assertIn("math.sqrt", names)

    def test_javascript_symbol_extraction(self):
        code = '''
import express from 'express';

class Server {
    start() {}
}

export function handleRequest(req, res) {
    return res.json({status: "ok"});
}
'''
        symbols = CodeASTExtractor.extract_symbols(Path("app.js"), "javascript", code)
        names = [s["symbol_name"] for s in symbols]
        self.assertIn("Server", names)
        self.assertIn("handleRequest", names)
        self.assertIn("express", names)

    def test_rust_symbol_extraction(self):
        code = '''
pub struct Config {
    pub port: u16,
}

pub fn init_server(cfg: Config) {
}
'''
        symbols = CodeASTExtractor.extract_symbols(Path("main.rs"), "rust", code)
        names = [s["symbol_name"] for s in symbols]
        self.assertIn("Config", names)
        self.assertIn("init_server", names)

class TestSystemIndexerOperations(unittest.TestCase):
    """Test directory scanning, incremental indexing, and SQLite search queries."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_file = Path(self.tmp_dir.name) / "test_index.sqlite"
        self.indexer = SystemIndexer(db_path=str(self.db_file))

        # Create dummy project
        self.proj_dir = Path(self.tmp_dir.name) / "my_project"
        self.proj_dir.mkdir()
        (self.proj_dir / ".gitignore").write_text("*.log\nsecret.txt\n", encoding="utf-8")
        (self.proj_dir / "app.py").write_text("def run_app():\n    return 'running'\n", encoding="utf-8")
        (self.proj_dir / "test.log").write_text("should be ignored", encoding="utf-8")

    def tearDown(self):
        self.indexer.close()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_scan_and_query_symbols(self):
        res = self.indexer.scan_directory(str(self.proj_dir))
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["files_indexed"], 1)

        # Lookup symbol
        syms = self.indexer.find_symbol("run_app")
        self.assertEqual(len(syms), 1)
        self.assertEqual(syms[0]["symbol_name"], "run_app")
        self.assertEqual(syms[0]["symbol_type"], "function")

    def test_code_search(self):
        self.indexer.scan_directory(str(self.proj_dir))
        matches = self.indexer.search_code("run_app")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["line_number"], 1)
        self.assertIn("def run_app():", matches[0]["snippet"])

    def test_ascii_project_tree(self):
        tree = self.indexer.get_project_tree(str(self.proj_dir))
        self.assertIn("my_project/", tree)
        self.assertIn("app.py", tree)
        self.assertNotIn("test.log", tree)  # .gitignore honored

if __name__ == "__main__":
    unittest.main()
