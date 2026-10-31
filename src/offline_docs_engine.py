#!/usr/bin/env python3
"""
offline_docs_engine.py - High-Performance Offline Documentation & Vector/FTS Search Engine
Author: Search Engine Architect & Developer Tooling Specialist

Provides instant full-text search (SQLite FTS5) across offline developer
documentation (DevDocs, Manpages, API specs for Python, Node.js, Rust, Linux CLI, SQLite)
without requiring internet access. Includes symbol signature lookup, code snippet
extraction, and automatic excerpt injection for AI agent error diagnosis.
"""

import os
import sys
import re
import json
import sqlite3
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any

# Default storage locations
DEFAULT_LINUX_STORAGE = "/var/db/offline_docs"
FALLBACK_STORAGE = os.path.expanduser("~/.aios/offline_docs")
LOCAL_DEV_STORAGE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "offline_docs"))


def resolve_docs_storage_dir(preferred_path: Optional[str] = None) -> Path:
    """
    Resolves a writable directory for offline documentation and the SQLite FTS5 database.
    Order of preference:
      1. Explicit preferred_path
      2. DEFAULT_LINUX_STORAGE (/var/db/offline_docs)
      3. FALLBACK_STORAGE (~/.aios/offline_docs)
      4. LOCAL_DEV_STORAGE (./data/offline_docs)
    """
    candidates = [
        preferred_path,
        DEFAULT_LINUX_STORAGE,
        FALLBACK_STORAGE,
        LOCAL_DEV_STORAGE
    ]

    for candidate in candidates:
        if not candidate:
            continue
        try:
            p = Path(candidate).resolve()
            p.mkdir(parents=True, exist_ok=True)
            # Test write permissions
            probe = p / ".perm_check"
            probe.touch()
            probe.unlink()
            return p
        except (PermissionError, OSError):
            continue

    # Absolute fallback
    cwd_fallback = Path("./offline_docs_db").resolve()
    cwd_fallback.mkdir(parents=True, exist_ok=True)
    return cwd_fallback


@dataclass
class DocSearchResult:
    symbol: str
    title: str
    language: str
    category: str
    path: str
    signature: str
    snippet: str
    excerpt: str
    rank: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocSignatureResult:
    symbol: str
    language: str
    signature: str
    parameters: List[str]
    return_type: str
    summary: str
    code_example: str
    doc_path: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OfflineDocsEngine:
    """
    Core search engine utilizing SQLite FTS5 for sub-millisecond offline
    API documentation querying, symbol lookup, and prompt context injection.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = resolve_docs_storage_dir(storage_dir)
        self.db_path = self.storage_dir / "docs_fts.db"
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high read concurrency
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_database(self):
        """Initializes SQLite FTS5 virtual tables and metadata tables."""
        with self._get_connection() as conn:
            # Metadata tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS docsets_meta (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    language TEXT NOT NULL,
                    version TEXT,
                    entry_count INTEGER DEFAULT 0,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Detailed documents table (for direct primary key retrieval)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS doc_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    docset_id INTEGER,
                    symbol TEXT NOT NULL,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    category TEXT,
                    path TEXT,
                    signature TEXT,
                    parameters_json TEXT,
                    return_type TEXT,
                    code_snippets_json TEXT,
                    content TEXT NOT NULL,
                    summary TEXT,
                    FOREIGN KEY(docset_id) REFERENCES docsets_meta(id)
                );
            """)

            # Create standard indices on metadata
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_symbol ON doc_entries(symbol);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_language ON doc_entries(language);")

            # SQLite FTS5 Virtual Table for full-text and BM25 ranking
            # FTS5 supports fast full text indexing with prefix matching
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                    symbol,
                    title,
                    language,
                    category,
                    signature,
                    content,
                    summary,
                    content='doc_entries',
                    content_rowid='id',
                    tokenize='porter unicode61'
                );
            """)

            # Triggers to keep FTS index synchronized with doc_entries
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS doc_entries_ai AFTER INSERT ON doc_entries BEGIN
                    INSERT INTO docs_fts(rowid, symbol, title, language, category, signature, content, summary)
                    VALUES (new.id, new.symbol, new.title, new.language, new.category, new.signature, new.content, new.summary);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS doc_entries_ad AFTER DELETE ON doc_entries BEGIN
                    INSERT INTO docs_fts(docs_fts, rowid, symbol, title, language, category, signature, content, summary)
                    VALUES('delete', old.id, old.symbol, old.title, old.language, old.category, old.signature, old.content, old.summary);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS doc_entries_au AFTER UPDATE ON doc_entries BEGIN
                    INSERT INTO docs_fts(docs_fts, rowid, symbol, title, language, category, signature, content, summary)
                    VALUES('delete', old.id, old.symbol, old.title, old.language, old.category, old.signature, old.content, old.summary);
                    INSERT INTO docs_fts(rowid, symbol, title, language, category, signature, content, summary)
                    VALUES (new.id, new.symbol, new.title, new.language, new.category, new.signature, new.content, new.summary);
                END;
            """)
            conn.commit()

    def is_empty(self) -> bool:
        """Checks if the documentation index contains any entries."""
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT COUNT(*) as count FROM doc_entries;").fetchone()
                return (row["count"] == 0) if row else True
        except Exception:
            return True

    def index_document(self,
                       symbol: str,
                       title: str,
                       language: str,
                       content: str,
                       signature: str = "",
                       parameters: Optional[List[str]] = None,
                       return_type: str = "",
                       code_snippets: Optional[List[str]] = None,
                       summary: str = "",
                       category: str = "api",
                       path: str = "",
                       docset_name: Optional[str] = None) -> int:
        """
        Inserts or updates a documentation entry in the FTS5 database.
        """
        params_json = json.dumps(parameters or [])
        snippets_json = json.dumps(code_snippets or [])
        lang_normalized = language.strip().lower()

        if not summary and content:
            # Generate clean 1-sentence summary
            first_p = content.strip().split("\n\n")[0].replace("\n", " ")
            summary = (first_p[:200] + "...") if len(first_p) > 200 else first_p

        with self._get_connection() as conn:
            # Register or update docset
            ds_name = docset_name or f"{lang_normalized}_docs"
            conn.execute("""
                INSERT INTO docsets_meta (name, language, entry_count)
                VALUES (?, ?, 1)
                ON CONFLICT(name) DO UPDATE SET entry_count = entry_count + 1;
            """, (ds_name, lang_normalized))

            docset_id_row = conn.execute("SELECT id FROM docsets_meta WHERE name = ?", (ds_name,)).fetchone()
            docset_id = docset_id_row["id"] if docset_id_row else None

            # Insert entry
            cursor = conn.execute("""
                INSERT INTO doc_entries (
                    docset_id, symbol, title, language, category, path,
                    signature, parameters_json, return_type, code_snippets_json,
                    content, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                docset_id, symbol.strip(), title.strip(), lang_normalized,
                category.strip(), path.strip(), signature.strip(),
                params_json, return_type.strip(), snippets_json,
                content.strip(), summary.strip()
            ))
            conn.commit()
            return cursor.lastrowid

    def bulk_index_documents(self, documents: List[Dict[str, Any]], docset_name: str, language: str) -> int:
        """High-speed batch insertion for large documentation sets."""
        lang_normalized = language.strip().lower()
        inserted_count = 0

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO docsets_meta (name, language, entry_count)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET entry_count = entry_count + ?;
            """, (docset_name, lang_normalized, len(documents), len(documents)))

            docset_id_row = conn.execute("SELECT id FROM docsets_meta WHERE name = ?", (docset_name,)).fetchone()
            docset_id = docset_id_row["id"] if docset_id_row else None

            rows = []
            for doc in documents:
                sym = doc.get("symbol", "").strip()
                title = doc.get("title", sym).strip()
                if not sym and not title:
                    continue
                content = doc.get("content", "").strip()
                summary = doc.get("summary", "")
                if not summary and content:
                    first_p = content.strip().split("\n\n")[0].replace("\n", " ")
                    summary = (first_p[:200] + "...") if len(first_p) > 200 else first_p

                rows.append((
                    docset_id,
                    sym,
                    title,
                    lang_normalized,
                    doc.get("category", "api").strip(),
                    doc.get("path", "").strip(),
                    doc.get("signature", "").strip(),
                    json.dumps(doc.get("parameters", [])),
                    doc.get("return_type", "").strip(),
                    json.dumps(doc.get("code_snippets", [])),
                    content,
                    summary
                ))

            conn.executemany("""
                INSERT INTO doc_entries (
                    docset_id, symbol, title, language, category, path,
                    signature, parameters_json, return_type, code_snippets_json,
                    content, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, rows)
            conn.commit()
            inserted_count = len(rows)

        return inserted_count

    def search_docs(self,
                    query: str,
                    language: Optional[str] = None,
                    limit: int = 5,
                    category: Optional[str] = None) -> List[DocSearchResult]:
        """
        Fast keyword & full-text search across documentation using FTS5 BM25 ranking.
        Supports fuzzy phrase queries, exact symbol matches, and language filters.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        # Sanitize query for FTS5 syntax
        # Preserve alphanumeric, underscore, dot, colon, dash
        tokens = re.findall(r"[a-zA-Z0-9_\.\:\-]+", cleaned_query)
        if not tokens:
            return []

        # Construct FTS5 query: match exact tokens and prefix matches
        fts_clauses = []
        for t in tokens:
            if len(t) >= 2:
                fts_clauses.append(f'"{t}"*')
            else:
                fts_clauses.append(f'"{t}"')
        fts_query = " OR ".join(fts_clauses)

        params: List[Any] = [fts_query]
        where_filters = []

        if language:
            where_filters.append("e.language = ?")
            params.append(language.strip().lower())

        if category:
            where_filters.append("e.category = ?")
            params.append(category.strip().lower())

        filter_sql = (" AND " + " AND ".join(where_filters)) if where_filters else ""

        sql = f"""
            SELECT
                e.symbol,
                e.title,
                e.language,
                e.category,
                e.path,
                e.signature,
                e.code_snippets_json,
                e.summary,
                snippet(docs_fts, 5, '<b>', '</b>', '...', 25) AS excerpt,
                bm25(docs_fts, 5.0, 3.0, 1.0, 1.0, 4.0, 1.0, 2.0) AS rank
            FROM docs_fts
            JOIN doc_entries e ON docs_fts.rowid = e.id
            WHERE docs_fts MATCH ? {filter_sql}
            ORDER BY rank
            LIMIT ?;
        """
        params.append(limit)

        results: List[DocSearchResult] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(sql, params)
                for row in cursor.fetchall():
                    snippets = json.loads(row["code_snippets_json"] or "[]")
                    best_snippet = snippets[0] if snippets else ""
                    # Clean excerpt HTML tags if needed, or format
                    excerpt = row["excerpt"] or row["summary"]

                    results.append(DocSearchResult(
                        symbol=row["symbol"],
                        title=row["title"],
                        language=row["language"],
                        category=row["category"],
                        path=row["path"] or "",
                        signature=row["signature"] or "",
                        snippet=best_snippet,
                        excerpt=excerpt,
                        rank=float(row["rank"])
                    ))
        except sqlite3.OperationalError:
            # Fallback to standard LIKE search if FTS syntax error
            results = self._fallback_like_search(cleaned_query, language, limit)

        # Exact match boost: if top result doesn't exact-match symbol, check exact match
        exact_symbol = self.get_symbol_details(cleaned_query, language)
        if exact_symbol and not any(r.symbol.lower() == cleaned_query.lower() for r in results):
            results.insert(0, DocSearchResult(
                symbol=exact_symbol["symbol"],
                title=exact_symbol["title"],
                language=exact_symbol["language"],
                category=exact_symbol["category"],
                path=exact_symbol["path"],
                signature=exact_symbol["signature"],
                snippet=exact_symbol.get("code_snippets", [""])[0] if exact_symbol.get("code_snippets") else "",
                excerpt=exact_symbol["summary"],
                rank=-99.0
            ))
            results = results[:limit]

        return results

    def _fallback_like_search(self, query: str, language: Optional[str], limit: int) -> List[DocSearchResult]:
        """Simple SQL LIKE fallback in case of complex symbol characters in FTS."""
        like_pattern = f"%{query}%"
        params: List[Any] = [like_pattern, like_pattern, like_pattern]
        where_lang = ""
        if language:
            where_lang = "AND language = ?"
            params.append(language.strip().lower())
        params.append(limit)

        results = []
        with self._get_connection() as conn:
            sql = f"""
                SELECT symbol, title, language, category, path, signature, code_snippets_json, summary
                FROM doc_entries
                WHERE (symbol LIKE ? OR title LIKE ? OR content LIKE ?) {where_lang}
                LIMIT ?;
            """
            cursor = conn.execute(sql, params)
            for row in cursor.fetchall():
                snippets = json.loads(row["code_snippets_json"] or "[]")
                best_snippet = snippets[0] if snippets else ""
                results.append(DocSearchResult(
                    symbol=row["symbol"],
                    title=row["title"],
                    language=row["language"],
                    category=row["category"],
                    path=row["path"] or "",
                    signature=row["signature"] or "",
                    snippet=best_snippet,
                    excerpt=row["summary"],
                    rank=0.0
                ))
        return results

    def get_api_signature(self, symbol: str, language: Optional[str] = None) -> Optional[DocSignatureResult]:
        """
        Retrieves precise API signature, parameter list, return type,
        and usage example for a specific symbol or function.
        """
        details = self.get_symbol_details(symbol, language)
        if not details:
            return None

        snippets = details.get("code_snippets", [])
        code_example = snippets[0] if snippets else ""

        return DocSignatureResult(
            symbol=details["symbol"],
            language=details["language"],
            signature=details.get("signature") or f"{details['symbol']}()",
            parameters=details.get("parameters", []),
            return_type=details.get("return_type", ""),
            summary=details.get("summary", ""),
            code_example=code_example,
            doc_path=details.get("path", "")
        )

    def get_symbol_details(self, symbol: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Finds full documentation entry for an exact or near-exact symbol."""
        cleaned = symbol.strip()
        params: List[Any] = [cleaned]
        lang_filter = ""
        if language:
            lang_filter = "AND language = ?"
            params.append(language.strip().lower())

        with self._get_connection() as conn:
            # 1. Exact symbol match
            row = conn.execute(f"""
                SELECT * FROM doc_entries
                WHERE symbol = ? COLLATE NOCASE {lang_filter}
                ORDER BY length(symbol) ASC LIMIT 1;
            """, params).fetchone()

            if not row:
                # 2. Check prefix/suffix (e.g. os.path.join -> path.join or join)
                parts = cleaned.split(".")
                last_part = parts[-1]
                if last_part != cleaned:
                    row = conn.execute(f"""
                        SELECT * FROM doc_entries
                        WHERE (symbol = ? OR symbol LIKE ?) COLLATE NOCASE {lang_filter}
                        LIMIT 1;
                    """, [last_part, f"%.{last_part}"] + ([language.strip().lower()] if language else [])).fetchone()

            if row:
                return {
                    "id": row["id"],
                    "symbol": row["symbol"],
                    "title": row["title"],
                    "language": row["language"],
                    "category": row["category"],
                    "path": row["path"],
                    "signature": row["signature"],
                    "parameters": json.loads(row["parameters_json"] or "[]"),
                    "return_type": row["return_type"],
                    "code_snippets": json.loads(row["code_snippets_json"] or "[]"),
                    "content": row["content"],
                    "summary": row["summary"]
                }
        return None

    def get_doc_context_for_error(self,
                                  error_message: str,
                                  failed_code: Optional[str] = None,
                                  language: Optional[str] = None,
                                  max_results: int = 3) -> str:
        """
        AI Agent Context Injector:
        Analyzes an error message, stack trace, or unknown method name,
        extracts the suspicious identifiers/modules, queries the local offline
        database, and formats a clean documentation excerpt ready to be injected
        into the LLM prompt.
        """
        extracted_symbols: List[str] = []

        # Common error patterns:
        # Python: AttributeError: module 'os' has no attribute 'xyz'
        attr_match = re.search(r"AttributeError:\s+(?:module\s+['\"]?(\w+)['\"]?\s+has\s+no\s+attribute|'(\w+)'\s+object\s+has\s+no\s+attribute)\s+['\"]?(\w+)['\"]?", error_message)
        if attr_match:
            mod_or_obj = attr_match.group(1) or attr_match.group(2)
            attr = attr_match.group(3)
            if mod_or_obj and attr:
                extracted_symbols.append(f"{mod_or_obj}.{attr}")
            if attr:
                extracted_symbols.append(attr)

        # NameError: name 'foo' is not defined
        name_match = re.search(r"NameError:\s+name\s+['\"](\w+)['\"]\s+is\s+not\s+defined", error_message)
        if name_match:
            extracted_symbols.append(name_match.group(1))

        # ModuleNotFoundError: No module named 'xyz'
        mod_match = re.search(r"ModuleNotFoundError:\s+No\s+module\s+named\s+['\"]([\w\.]+)['\"]", error_message)
        if mod_match:
            extracted_symbols.append(mod_match.group(1))

        # TypeError: method() takes X positional arguments but Y were given
        type_match = re.search(r"TypeError:\s+(\w+)\(\)\s+(?:takes|missing|got)", error_message)
        if type_match:
            extracted_symbols.append(type_match.group(1))

        # Node.js: TypeError: obj.xyz is not a function / ReferenceError: xyz is not defined
        node_fn_match = re.search(r"TypeError:\s+(?:[a-zA-Z0-9_\.]+\.)?(\w+)\s+is\s+not\s+a\s+function", error_message)
        if node_fn_match:
            extracted_symbols.append(node_fn_match.group(1))

        node_ref_match = re.search(r"ReferenceError:\s+(\w+)\s+is\s+not\s+defined", error_message)
        if node_ref_match:
            extracted_symbols.append(node_ref_match.group(1))

        # Rust: cannot find function `xyz` in ... / no method named `xyz` found for ...
        rust_fn_match = re.search(r"(?:cannot\s+find\s+function|no\s+method\s+named)\s+`(\w+)`", error_message)
        if rust_fn_match:
            extracted_symbols.append(rust_fn_match.group(1))

        # Fallback: scan words in error message that look like identifiers
        words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_\.]{2,30}\b", error_message)
        for w in words:
            if w.lower() not in {"error", "exception", "failed", "traceback", "file", "line", "none", "true", "false", "module"}:
                if w not in extracted_symbols:
                    extracted_symbols.append(w)

        # Detect language if not passed
        inferred_lang = language
        if not inferred_lang:
            if "Traceback (most recent call last)" in error_message or "Error:" in error_message:
                inferred_lang = "python"
            elif "ReferenceError" in error_message or "TypeError" in error_message and "at " in error_message:
                inferred_lang = "node"
            elif "cannot find function" in error_message or "--> src/" in error_message:
                inferred_lang = "rust"

        matched_docs: List[DocSearchResult] = []
        seen_symbols = set()

        for sym in extracted_symbols:
            results = self.search_docs(sym, language=inferred_lang, limit=2)
            for r in results:
                if r.symbol not in seen_symbols:
                    seen_symbols.add(r.symbol)
                    matched_docs.append(r)
                if len(matched_docs) >= max_results:
                    break
            if len(matched_docs) >= max_results:
                break

        if not matched_docs:
            return ""

        # Format context injection block
        lines = [
            "### [OFFLINE DOCUMENTATION CONTEXT - OFFICIAL API SPECIFICATIONS]",
            "The following verified offline API excerpts are relevant to the diagnosed issue:"
        ]
        for d in matched_docs:
            lines.append(f"\n#### Symbol: `{d.symbol}` ({d.language.upper()})")
            if d.signature:
                lines.append(f"**Signature:** `{d.signature}`")
            lines.append(f"**Summary:** {d.excerpt}")
            if d.snippet:
                lines.append(f"**Official Example:**\n```{d.language}\n{d.snippet}\n```")

        lines.append("\nUse the official signatures and behavior above to correct the code without hallucinating APIs.\n")
        return "\n".join(lines)

    def list_supported_languages(self) -> List[Dict[str, Any]]:
        """Returns statistics of all indexed programming languages and docsets."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT language, count(*) as total_symbols, group_concat(DISTINCT category) as categories
                FROM doc_entries
                GROUP BY language
                ORDER BY total_symbols DESC;
            """).fetchall()
            return [
                {
                    "language": r["language"],
                    "total_symbols": r["total_symbols"],
                    "categories": r["categories"].split(",") if r["categories"] else []
                }
                for r in rows
            ]

    def get_stats(self) -> Dict[str, Any]:
        """Returns database storage and index statistics."""
        with self._get_connection() as conn:
            entry_count = conn.execute("SELECT count(*) as count FROM doc_entries;").fetchone()["count"]
            docsets = conn.execute("SELECT count(*) as count FROM docsets_meta;").fetchone()["count"]
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "db_path": str(self.db_path),
                "storage_dir": str(self.storage_dir),
                "total_entries": entry_count,
                "total_docsets": docsets,
                "db_size_bytes": db_size,
                "db_size_mb": round(db_size / (1024 * 1024), 2)
            }


# ==============================================================================
# Direct module test
# ==============================================================================
if __name__ == "__main__":
    engine = OfflineDocsEngine()
    print(f"Offline Docs Engine initialized at: {engine.db_path}")
    print(f"Stats: {engine.get_stats()}")
