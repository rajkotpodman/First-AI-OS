#!/usr/bin/env python3
"""
test_personal_memory.py - Unit tests for Long-Term User Memory & Adaptive Personal Profile Engine
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from personal_memory import (
    SimpleEmbeddingEngine,
    MemoryRecord,
    PersonalMemoryEngine
)


class TestPersonalMemory(unittest.TestCase):
    """Test suite for memory storage, vector similarity, extraction, and prompt injection."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_memory.db")
        self.engine = PersonalMemoryEngine(db_path=self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_embedding_engine_properties(self):
        vec = SimpleEmbeddingEngine.get_embedding("user prefers typescript")
        self.assertEqual(len(vec), 64)
        # Check non-zero
        self.assertGreater(sum(abs(x) for x in vec), 0)

        # Similar phrases should have high cosine similarity
        vec1 = SimpleEmbeddingEngine.get_embedding("user prefers typescript over javascript")
        vec2 = SimpleEmbeddingEngine.get_embedding("i prefer typescript for web development")
        vec3 = SimpleEmbeddingEngine.get_embedding("the weather is sunny today")

        sim_related = SimpleEmbeddingEngine.cosine_similarity(vec1, vec2)
        sim_unrelated = SimpleEmbeddingEngine.cosine_similarity(vec1, vec3)
        self.assertGreater(sim_related, sim_unrelated)

    def test_store_and_list_memories(self):
        id1 = self.engine.store_memory("user_preferences", "User prefers TypeScript over JavaScript")
        id2 = self.engine.store_memory("system_rules", "Always run unit tests before git commit")
        self.assertGreater(id1, 0)
        self.assertGreater(id2, 0)

        all_mem = self.engine.list_memories()
        self.assertEqual(len(all_mem), 2)

        pref_only = self.engine.list_memories(category="user_preferences")
        self.assertEqual(len(pref_only), 1)
        self.assertEqual(pref_only[0].content, "User prefers TypeScript over JavaScript")

    def test_semantic_query_retrieval(self):
        self.engine.store_memory("user_preferences", "User prefers Python 3.11 with FastAPI")
        self.engine.store_memory("user_preferences", "Preferred indentation is 4 spaces")
        self.engine.store_memory("project_context", "Database PostgreSQL runs on port 5433")

        # Query about python backend
        results = self.engine.query_memories("build a python fastapi server")
        self.assertTrue(len(results) > 0)
        # Top match should be the Python 3.11 with FastAPI preference
        self.assertIn("FastAPI", results[0].content)

    def test_system_prompt_context_injection(self):
        self.engine.store_memory("user_preferences", "User prefers tabs over spaces")
        self.engine.store_memory("project_context", "Root workspace is /workspace/backend")

        context_snippet = self.engine.get_system_prompt_context("write a new python file")
        self.assertIn("ADAPTIVE USER PREFERENCES", context_snippet)
        self.assertIn("tabs over spaces", context_snippet)

    def test_automatic_memory_extraction(self):
        user_interaction = "I prefer TypeScript over JavaScript, and always use 4 spaces"
        extracted = self.engine.extract_memories_from_text(user_interaction)
        self.assertTrue(len(extracted) >= 2)

        # Check stored in database automatically
        stored = self.engine.list_memories()
        self.assertTrue(any("TypeScript" in m.content for m in stored))

    def test_forget_and_clear_memory(self):
        mem_id = self.engine.store_memory("user_preferences", "Temporary memory fact")
        self.assertEqual(len(self.engine.list_memories()), 1)

        ok = self.engine.forget_memory(mem_id)
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.list_memories()), 0)

        # Test clear all
        self.engine.store_memory("user_preferences", "Fact A")
        self.engine.store_memory("user_preferences", "Fact B")
        cleared_count = self.engine.clear_all_memories()
        self.assertEqual(cleared_count, 2)
        self.assertEqual(len(self.engine.list_memories()), 0)


if __name__ == "__main__":
    unittest.main()
