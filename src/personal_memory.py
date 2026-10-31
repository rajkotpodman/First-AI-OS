#!/usr/bin/env python3
"""
personal_memory.py - Long-Term User Memory & Adaptive Personal Profile Engine
Author: Memory Systems Architect and AI Knowledge Graph Engineer

Stores user preferences, coding style, project conventions, and operational patterns
across OS restarts using SQLite and vector similarity. Dynamically injects relevant
context into AI system prompts without exceeding token limits.
"""

import os
import sys
import re
import json
import math
import time
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MEMORY_DIR = os.path.expanduser("~/.ai_memory")
DEFAULT_DB_FILE = os.path.join(DEFAULT_MEMORY_DIR, "memory.db")


# ==============================================================================
# Vector & Similarity Math Utilities
# ==============================================================================
class SimpleEmbeddingEngine:
    """
    Computes fast, deterministic local term-frequency / n-gram semantic vector
    embeddings (dimension 64) for SQLite vector similarity without external deps.
    """

    DIMENSION = 64

    @classmethod
    def get_embedding(cls, text: str) -> List[float]:
        clean = text.lower().strip()
        tokens = re.findall(r"\w+", clean)
        vector = [0.0] * cls.DIMENSION

        if not tokens:
            return vector

        # Hashed feature projection
        for t in tokens:
            h = hash(t)
            idx = abs(h) % cls.DIMENSION
            sign = 1.0 if (h // cls.DIMENSION) % 2 == 0 else -1.0
            vector[idx] += sign

        # Add 3-gram character shingles for typo and morphological tolerance
        for i in range(max(0, len(clean) - 2)):
            shingle = clean[i:i + 3]
            h = hash(shingle)
            idx = abs(h) % cls.DIMENSION
            vector[idx] += 0.5

        # L2 Normalization
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 1e-6:
            vector = [x / norm for x in vector]

        return vector

    @classmethod
    def cosine_similarity(cls, vec_a: List[float], vec_b: List[float]) -> float:
        if len(vec_a) != len(vec_b) or not vec_a or not vec_b:
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a < 1e-6 or norm_b < 1e-6:
            return 0.0
        return dot_product / (norm_a * norm_b)


# ==============================================================================
# Data Structures
# ==============================================================================
@dataclass
class MemoryRecord:
    id: int
    category: str  # user_preferences, project_context, system_rules, frequent_commands
    content: str
    confidence: float = 1.0
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    similarity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Personal Memory Engine
# ==============================================================================
class PersonalMemoryEngine:
    """
    Manages long-term vector & KV storage, automatic interaction memory extraction,
    and adaptive context retrieval for AI shell sessions.
    """

    CATEGORIES = [
        "user_preferences",
        "project_context",
        "system_rules",
        "frequent_commands"
    ]

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_FILE
        self._ensure_storage()
        self._init_db()

    def _ensure_storage(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception:
                self.db_path = os.path.join(tempfile.gettempdir(), "ai_memory.db")

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL UNIQUE,
                embedding TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS kv_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_category ON memories(category);")
            conn.commit()

    # --------------------------------------------------------------------------
    # 1. Memory CRUD Operations
    # --------------------------------------------------------------------------
    def store_memory(self, category: str, content: str, confidence: float = 1.0) -> int:
        """Stores or updates a memory record with its calculated vector embedding."""
        clean_content = content.strip()
        if not clean_content:
            return -1

        category = category if category in self.CATEGORIES else "user_preferences"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        vec = SimpleEmbeddingEngine.get_embedding(clean_content)
        vec_json = json.dumps(vec)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO memories (category, content, embedding, confidence, created_at, updated_at, access_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(content) DO UPDATE SET
                confidence = excluded.confidence,
                updated_at = excluded.updated_at;
            """, (category, clean_content, vec_json, confidence, now, now))
            conn.commit()
            return cursor.lastrowid

    def list_memories(self, category: Optional[str] = None) -> List[MemoryRecord]:
        """Lists memories optionally filtered by category."""
        query = "SELECT id, category, content, confidence, created_at, updated_at, access_count FROM memories"
        params = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY id DESC"

        records = []
        with self._get_connection() as conn:
            for row in conn.execute(query, params):
                records.append(MemoryRecord(
                    id=row["id"],
                    category=row["category"],
                    content=row["content"],
                    confidence=row["confidence"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    access_count=row["access_count"]
                ))
        return records

    def forget_memory(self, memory_id: int) -> bool:
        """Deletes a memory record by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all_memories(self) -> int:
        """Wipes all stored memories."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM memories")
            cursor.execute("DELETE FROM kv_profile")
            conn.commit()
            return count

    # --------------------------------------------------------------------------
    # 2. Semantic Search & Context Retrieval
    # --------------------------------------------------------------------------
    def query_memories(self, query: str, top_k: int = 5, min_similarity: float = 0.2) -> List[MemoryRecord]:
        """Queries stored memories using cosine vector similarity ranking."""
        query_vec = SimpleEmbeddingEngine.get_embedding(query)
        scored_records = []

        with self._get_connection() as conn:
            rows = conn.execute("SELECT id, category, content, embedding, confidence, created_at, updated_at, access_count FROM memories").fetchall()
            for r in rows:
                try:
                    stored_vec = json.loads(r["embedding"])
                    sim = SimpleEmbeddingEngine.cosine_similarity(query_vec, stored_vec)
                    if sim >= min_similarity:
                        scored_records.append((sim, MemoryRecord(
                            id=r["id"],
                            category=r["category"],
                            content=r["content"],
                            confidence=r["confidence"],
                            created_at=r["created_at"],
                            updated_at=r["updated_at"],
                            access_count=r["access_count"],
                            similarity=round(sim, 4)
                        )))
                except Exception:
                    pass

        # Sort descending by similarity
        scored_records.sort(key=lambda x: x[0], reverse=True)
        top_results = [rec for _, rec in scored_records[:top_k]]

        # Increment access count
        if top_results:
            with self._get_connection() as conn:
                for rec in top_results:
                    conn.execute("UPDATE memories SET access_count = access_count + 1 WHERE id = ?", (rec.id,))
                conn.commit()

        return top_results

    def get_system_prompt_context(self, user_query: str, max_tokens: int = 300) -> str:
        """
        Retrieves relevant user preferences and injects them as a concise system prompt
        block without blowing token limits.
        """
        relevant = self.query_memories(user_query, top_k=4, min_similarity=0.25)
        if not relevant:
            # Fallback: check if there are high-confidence global user preferences
            general_prefs = self.list_memories(category="user_preferences")[:2]
            if not general_prefs:
                return ""
            relevant = general_prefs

        lines = ["[ADAPTIVE USER PREFERENCES & CONVENTIONS]"]
        char_budget = max_tokens * 4
        current_len = 0

        for r in relevant:
            entry = f"- [{r.category.upper()}] {r.content}"
            if current_len + len(entry) < char_budget:
                lines.append(entry)
                current_len += len(entry)

        return "\n".join(lines) if len(lines) > 1 else ""

    # --------------------------------------------------------------------------
    # 3. Automatic Interaction Memory Extraction
    # --------------------------------------------------------------------------
    def extract_memories_from_text(self, text: str) -> List[Tuple[str, str]]:
        """
        Parses user prompts or interaction strings to extract long-term preferences,
        coding conventions, project rules, and frequent commands.
        """
        extracted = []
        clean = text.strip()

        # Rule 1: Preference patterns (e.g. "I prefer TypeScript over JavaScript", "prefer python 3.11")
        pref_matches = re.findall(r"(?:i\s+prefer|always\s+use|use|prefer)\s+([a-zA-Z0-9_\-\.\s]+(?:\s+over\s+[a-zA-Z0-9_\-\.\s]+)?)", clean, re.IGNORECASE)
        for m in pref_matches:
            fact = f"User preference: {m.strip()}"
            extracted.append(("user_preferences", fact))

        # Rule 2: Indentation / formatting preferences
        if re.search(r"\b(tabs|spaces|2\s+spaces|4\s+spaces)\b", clean, re.IGNORECASE):
            match = re.search(r"\b(?:use\s+)?(tabs|spaces|2\s+spaces|4\s+spaces)\b", clean, re.IGNORECASE)
            if match:
                extracted.append(("user_preferences", f"Preferred indentation style: {match.group(1)}"))

        # Rule 3: System rules (e.g. "never delete", "always test before commit")
        rule_matches = re.findall(r"\b(never\s+[a-zA-Z0-9_\-\.\s]+|always\s+[a-zA-Z0-9_\-\.\s]+)", clean, re.IGNORECASE)
        for r_m in rule_matches:
            if len(r_m.split()) >= 3:
                extracted.append(("system_rules", f"Enforced rule: {r_m.strip()}"))

        # Rule 4: Project context / paths
        if "/workspace/" in clean or "repo" in clean.lower():
            for token in clean.split():
                if token.startswith("/workspace/") or token.startswith("./"):
                    clean_token = token.strip(".,;'\"")
                    extracted.append(("project_context", f"Active project path: {clean_token}"))

        # Store all extracted facts
        for cat, fact in extracted:
            self.store_memory(cat, fact)

        return extracted


# ==============================================================================
# CLI Entrypoint & Management Tool
# ==============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI OS Long-Term Personal Memory & Profile Manager")
    parser.add_argument("action", choices=["list", "add", "search", "forget", "clear", "stats"], nargs="?", default="list")
    parser.add_argument("arg1", nargs="?", help="Argument (category for add, query for search, id for forget)")
    parser.add_argument("arg2", nargs="?", help="Content for add")
    parser.add_argument("--category", help="Filter listing by category")

    args = parser.parse_args()
    engine = PersonalMemoryEngine()

    if args.action == "list":
        records = engine.list_memories(category=args.category)
        print(f"\nPersonal Memories in {engine.db_path} ({len(records)} total):")
        print("=" * 75)
        for r in records:
            print(f"[{r.id}] [{r.category.upper()}] (Accessed: {r.access_count}x)")
            print(f"    {r.content}")
        print()

    elif args.action == "add":
        if not args.arg1 or not args.arg2:
            print("Usage: ai-memory add <category> <content>")
            print(f"Available categories: {PersonalMemoryEngine.CATEGORIES}")
            sys.exit(1)
        mem_id = engine.store_memory(args.arg1, args.arg2)
        print(f"[OK] Stored memory #{mem_id} under '{args.arg1}': {args.arg2}")

    elif args.action == "search":
        if not args.arg1:
            print("Usage: ai-memory search <query_text>")
            sys.exit(1)
        results = engine.query_memories(args.arg1)
        print(f"\nSemantic Memory Search for: '{args.arg1}'")
        print("=" * 60)
        for r in results:
            print(f"Score: {r.similarity:.4f} | [{r.category}] #{r.id}")
            print(f"  {r.content}")
        print()

    elif args.action == "forget":
        if not args.arg1:
            print("Usage: ai-memory forget <id>")
            sys.exit(1)
        try:
            target_id = int(args.arg1)
            ok = engine.forget_memory(target_id)
            print(f"{'[OK] Memory removed' if ok else '[✗] Memory ID not found'}")
        except ValueError:
            print("[✗] Error: ID must be an integer.")

    elif args.action == "clear":
        count = engine.clear_all_memories()
        print(f"[OK] Cleared {count} memories from memory store.")

    elif args.action == "stats":
        all_mem = engine.list_memories()
        stats = {}
        for m in all_mem:
            stats[m.category] = stats.get(m.category, 0) + 1
        print(f"\nAI Memory Knowledge Base Statistics ({len(all_mem)} total facts):")
        print("=" * 50)
        for cat, cnt in stats.items():
            print(f"  - {cat:<22}: {cnt}")
        print()


if __name__ == "__main__":
    main()
