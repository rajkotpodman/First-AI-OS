#!/usr/bin/env python3
"""
system_indexer.py - Local System Knowledge Graph & File Indexer for AI OS
Author: Search Systems Engineer & Knowledge Graph Architect

Provides ultra-fast incremental filesystem scanning, code AST symbol extraction,
and low-token context retrieval via SQLite storage.
"""

import os
import sys
import re
import ast
import time
import sqlite3
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

DEFAULT_DB_PATH = "/var/db/system_index.sqlite"
FALLBACK_DB_PATH = os.path.expanduser("~/.aios/system_index.sqlite")

IGNORED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".pytest_cache",
    ".venv", "venv", "env", "target", "dist", "build", ".idea", ".vscode",
    ".cargo", ".rustup", "vendor"
}

CODE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c_header",
    ".hpp": "cpp_header",
    ".sh": "shell",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".toml": "toml",
    ".sql": "sql",
    ".html": "html",
    ".css": "css"
}

# ==============================================================================
# SQLite Knowledge Graph Storage
# ==============================================================================
class IndexStorage:
    """Manages SQLite tables and transactions for filesystem metadata and symbols."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = self._resolve_db_path(db_path)
        self._init_database()

    def _resolve_db_path(self, custom_path: Optional[str]) -> str:
        candidates = [custom_path, DEFAULT_DB_PATH, FALLBACK_DB_PATH]
        for c in candidates:
            if c:
                try:
                    p = Path(c).resolve()
                    p.parent.mkdir(parents=True, exist_ok=True)
                    # Verify write permissions
                    conn = sqlite3.connect(str(p))
                    conn.close()
                    return str(p)
                except (PermissionError, sqlite3.OperationalError, OSError):
                    continue
        fallback = os.path.abspath("./system_index.sqlite")
        return fallback

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_database(self):
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    extension TEXT,
                    size_bytes INTEGER,
                    mtime REAL,
                    file_type TEXT,
                    last_indexed REAL
                );

                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                    symbol_name TEXT NOT NULL,
                    symbol_type TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    signature TEXT,
                    docstring TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
                CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename);
                CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(symbol_name);
                CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(symbol_type);
                CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
            """)
            conn.commit()
        finally:
            conn.close()


# ==============================================================================
# Code Analysis & AST Extraction Engine
# ==============================================================================
class CodeASTExtractor:
    """Parses source code files to extract function signatures, classes, and imports."""

    @staticmethod
    def extract_symbols(file_path: Path, file_type: str, content: str) -> List[Dict[str, Any]]:
        if file_type == "python":
            return CodeASTExtractor._extract_python(content)
        elif file_type in ("javascript", "typescript"):
            return CodeASTExtractor._extract_js_ts(content)
        elif file_type == "rust":
            return CodeASTExtractor._extract_rust(content)
        elif file_type == "go":
            return CodeASTExtractor._extract_go(content)
        elif file_type in ("c", "cpp", "c_header", "cpp_header"):
            return CodeASTExtractor._extract_c_cpp(content)
        return []

    @staticmethod
    def _extract_python(content: str) -> List[Dict[str, Any]]:
        symbols = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return CodeASTExtractor._extract_regex_fallback(content)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                sig = f"def {node.name}({', '.join(args)})"
                doc = ast.get_docstring(node) or ""
                symbols.append({
                    "symbol_name": node.name,
                    "symbol_type": "function",
                    "line_number": node.lineno,
                    "signature": sig,
                    "docstring": doc[:200]
                })

            elif isinstance(node, ast.ClassDef):
                bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                base_str = f"({', '.join(bases)})" if bases else ""
                sig = f"class {node.name}{base_str}"
                doc = ast.get_docstring(node) or ""
                symbols.append({
                    "symbol_name": node.name,
                    "symbol_type": "class",
                    "line_number": node.lineno,
                    "signature": sig,
                    "docstring": doc[:200]
                })

                # Extract class methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_args = [a.arg for a in item.args.args]
                        m_sig = f"def {node.name}.{item.name}({', '.join(m_args)})"
                        symbols.append({
                            "symbol_name": f"{node.name}.{item.name}",
                            "symbol_type": "method",
                            "line_number": item.lineno,
                            "signature": m_sig,
                            "docstring": (ast.get_docstring(item) or "")[:200]
                        })

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    symbols.append({
                        "symbol_name": alias.name,
                        "symbol_type": "import",
                        "line_number": node.lineno,
                        "signature": f"import {alias.name}",
                        "docstring": ""
                    })

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    symbols.append({
                        "symbol_name": f"{mod}.{alias.name}",
                        "symbol_type": "import",
                        "line_number": node.lineno,
                        "signature": f"from {mod} import {alias.name}",
                        "docstring": ""
                    })

        return symbols

    @staticmethod
    def _extract_js_ts(content: str) -> List[Dict[str, Any]]:
        symbols = []
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            line_str = line.strip()
            # Function: function name(...) or const name = (...) =>
            fn_m = re.match(r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\((.*?)\)", line_str)
            if fn_m:
                symbols.append({
                    "symbol_name": fn_m.group(1),
                    "symbol_type": "function",
                    "line_number": idx,
                    "signature": f"function {fn_m.group(1)}({fn_m.group(2)})",
                    "docstring": ""
                })
                continue

            arrow_m = re.match(r"(?:export\s+)?const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>", line_str)
            if arrow_m:
                symbols.append({
                    "symbol_name": arrow_m.group(1),
                    "symbol_type": "function",
                    "line_number": idx,
                    "signature": f"const {arrow_m.group(1)} = ({arrow_m.group(2)}) =>",
                    "docstring": ""
                })
                continue

            # Class: class Name [extends Base]
            cls_m = re.match(r"(?:export\s+)?class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$]+))?", line_str)
            if cls_m:
                symbols.append({
                    "symbol_name": cls_m.group(1),
                    "symbol_type": "class",
                    "line_number": idx,
                    "signature": line_str.split("{")[0].strip(),
                    "docstring": ""
                })
                continue

            # Import: import ... from '...'
            imp_m = re.match(r"import\s+.*?\s+from\s+['\"](.*?)['\"]", line_str)
            if imp_m:
                symbols.append({
                    "symbol_name": imp_m.group(1),
                    "symbol_type": "import",
                    "line_number": idx,
                    "signature": line_str,
                    "docstring": ""
                })
        return symbols

    @staticmethod
    def _extract_rust(content: str) -> List[Dict[str, Any]]:
        symbols = []
        for idx, line in enumerate(content.splitlines(), 1):
            line_str = line.strip()
            # fn name(...)
            fn_m = re.match(r"(?:pub(?:\(crate\))?\s+)?(?:async\s+)?fn\s+([a-zA-Z0-9_]+)\s*(?:<.*?>)?\s*\((.*?)\)", line_str)
            if fn_m:
                symbols.append({
                    "symbol_name": fn_m.group(1),
                    "symbol_type": "function",
                    "line_number": idx,
                    "signature": line_str.split("{")[0].strip(),
                    "docstring": ""
                })
                continue
            # struct / enum / trait
            st_m = re.match(r"(?:pub(?:\(crate\))?\s+)?(struct|enum|trait)\s+([a-zA-Z0-9_]+)", line_str)
            if st_m:
                symbols.append({
                    "symbol_name": st_m.group(2),
                    "symbol_type": st_m.group(1),
                    "line_number": idx,
                    "signature": line_str.split("{")[0].strip(),
                    "docstring": ""
                })
        return symbols

    @staticmethod
    def _extract_go(content: str) -> List[Dict[str, Any]]:
        symbols = []
        for idx, line in enumerate(content.splitlines(), 1):
            line_str = line.strip()
            # func (r *Recv) Name(...) or func Name(...)
            fn_m = re.match(r"func\s+(?:\((?:.*?\s+)?\*?([a-zA-Z0-9_]+)\)\s+)?([a-zA-Z0-9_]+)\s*\((.*?)\)", line_str)
            if fn_m:
                recv = fn_m.group(1)
                name = fn_m.group(2)
                full_name = f"{recv}.{name}" if recv else name
                symbols.append({
                    "symbol_name": full_name,
                    "symbol_type": "function",
                    "line_number": idx,
                    "signature": line_str.split("{")[0].strip(),
                    "docstring": ""
                })
                continue
            # type Name struct / interface
            tp_m = re.match(r"type\s+([a-zA-Z0-9_]+)\s+(struct|interface)", line_str)
            if tp_m:
                symbols.append({
                    "symbol_name": tp_m.group(1),
                    "symbol_type": tp_m.group(2),
                    "line_number": idx,
                    "signature": line_str.split("{")[0].strip(),
                    "docstring": ""
                })
        return symbols

    @staticmethod
    def _extract_c_cpp(content: str) -> List[Dict[str, Any]]:
        symbols = []
        for idx, line in enumerate(content.splitlines(), 1):
            line_str = line.strip()
            # #include <...>
            if line_str.startswith("#include"):
                inc_m = re.match(r"#include\s+[<\"'](.*)[>\"']", line_str)
                if inc_m:
                    symbols.append({
                        "symbol_name": inc_m.group(1),
                        "symbol_type": "import",
                        "line_number": idx,
                        "signature": line_str,
                        "docstring": ""
                    })
                continue
            # class / struct
            cs_m = re.match(r"(class|struct)\s+([a-zA-Z0-9_]+)", line_str)
            if cs_m:
                symbols.append({
                    "symbol_name": cs_m.group(2),
                    "symbol_type": cs_m.group(1),
                    "line_number": idx,
                    "signature": line_str.split("{")[0].strip(),
                    "docstring": ""
                })
        return symbols

    @staticmethod
    def _extract_regex_fallback(content: str) -> List[Dict[str, Any]]:
        symbols = []
        for idx, line in enumerate(content.splitlines(), 1):
            m = re.match(r"^(?:async\s+)?def\s+([a-zA-Z0-9_]+)", line.strip())
            if m:
                symbols.append({
                    "symbol_name": m.group(1),
                    "symbol_type": "function",
                    "line_number": idx,
                    "signature": line.strip().rstrip(":"),
                    "docstring": ""
                })
        return symbols


# ==============================================================================
# Gitignore Pattern Matcher
# ==============================================================================
class GitignoreMatcher:
    """Parses and evaluates .gitignore rules for excluded directory branches."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> List[str]:
        patterns = []
        gi_file = self.root_dir / ".gitignore"
        if gi_file.exists():
            try:
                for line in gi_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
            except Exception:
                pass
        return patterns

    def is_ignored(self, path: Path) -> bool:
        # Check standard ignored directories
        for part in path.parts:
            if part in IGNORED_DIRS:
                return True

        # Check .gitignore patterns
        try:
            rel = str(path.relative_to(self.root_dir)).replace("\\", "/")
            for pat in self.patterns:
                pat_clean = pat.rstrip("/")
                if fnmatch.fnmatch(rel, pat_clean) or fnmatch.fnmatch(path.name, pat_clean):
                    return True
                if pat.endswith("/") and fnmatch.fnmatch(f"{rel}/", pat):
                    return True
        except ValueError:
            pass
        return False


# ==============================================================================
# Core System Indexer Engine
# ==============================================================================
class SystemIndexer:
    """
    Fast incremental filesystem indexer, AST symbol analyzer, and context search engine.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.storage = IndexStorage(db_path)

    def scan_directory(self, target_dir: str, incremental: bool = True) -> Dict[str, Any]:
        """
        Scans directory tree, records file metadata, extracts AST symbols,
        and saves into SQLite.
        """
        start_time = time.time()
        root = Path(target_dir).resolve()
        if not root.exists():
            return {"success": False, "error": f"Directory not found: {target_dir}"}

        matcher = GitignoreMatcher(root)
        files_indexed = 0
        symbols_indexed = 0
        now = time.time()

        conn = self.storage._get_connection()
        try:
            for dirpath, dirnames, filenames in os.walk(str(root)):
                # Prune ignored directories in-place
                dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not matcher.is_ignored(Path(dirpath) / d)]

                for fn in filenames:
                    file_path = Path(dirpath) / fn
                    if matcher.is_ignored(file_path):
                        continue

                    try:
                        stat = file_path.stat()
                        mtime = stat.st_mtime
                        size = stat.st_size
                        ext = file_path.suffix.lower()
                        file_type = CODE_EXTENSIONS.get(ext, "binary" if ext in (".so", ".bin", ".iso") else "text")

                        abs_str = str(file_path)

                        # Incremental check: has file been modified since last indexing?
                        cur = conn.cursor()
                        cur.execute("SELECT id, mtime FROM files WHERE path = ?", (abs_str,))
                        row = cur.fetchone()

                        if incremental and row and row["mtime"] == mtime:
                            continue  # Skip unchanged file

                        # Read text content if it's code/text
                        content = ""
                        if file_type != "binary" and size < 2 * 1024 * 1024:  # Limit 2MB for AST
                            try:
                                content = file_path.read_text(encoding="utf-8", errors="ignore")
                            except Exception:
                                pass

                        # Insert / Update file record
                        if row:
                            file_id = row["id"]
                            conn.execute("""
                                UPDATE files SET size_bytes = ?, mtime = ?, file_type = ?, last_indexed = ?
                                WHERE id = ?
                            """, (size, mtime, file_type, now, file_id))
                            conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
                        else:
                            cur.execute("""
                                INSERT INTO files (path, filename, extension, size_bytes, mtime, file_type, last_indexed)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (abs_str, fn, ext, size, mtime, file_type, now))
                            file_id = cur.lastrowid

                        files_indexed += 1

                        # Extract and insert AST symbols
                        if content and file_type in ("python", "javascript", "typescript", "rust", "go", "c", "cpp"):
                            symbols = CodeASTExtractor.extract_symbols(file_path, file_type, content)
                            for sym in symbols:
                                conn.execute("""
                                    INSERT INTO symbols (file_id, symbol_name, symbol_type, line_number, signature, docstring)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (file_id, sym["symbol_name"], sym["symbol_type"],
                                      sym["line_number"], sym["signature"], sym["docstring"]))
                                symbols_indexed += 1

                    except (PermissionError, OSError):
                        continue

            conn.commit()
        finally:
            conn.close()

        duration = time.time() - start_time
        return {
            "success": True,
            "target_dir": str(root),
            "files_indexed": files_indexed,
            "symbols_indexed": symbols_indexed,
            "duration_sec": round(duration, 3),
            "database": self.storage.db_path
        }

    def find_symbol(self, symbol_name: str, symbol_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches index for matching function/class symbols."""
        query = """
            SELECT s.symbol_name, s.symbol_type, s.line_number, s.signature, s.docstring, f.path, f.filename
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.symbol_name LIKE ?
        """
        params = [f"%{symbol_name}%"]
        if symbol_type:
            query += " AND s.symbol_type = ?"
            params.append(symbol_type)
        query += " LIMIT 50"

        conn = self.storage._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def search_code(self, query_term: str, max_results: int = 25) -> List[Dict[str, Any]]:
        """
        Token-efficient search across indexed files returning line snippets and locations.
        """
        results = []
        conn = self.storage._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, path, filename FROM files WHERE file_type != 'binary'")
            files = cur.fetchall()

            count = 0
            for f in files:
                f_path = Path(f["path"])
                if not f_path.exists():
                    continue
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as fp:
                        for line_idx, line in enumerate(fp, 1):
                            if query_term.lower() in line.lower():
                                results.append({
                                    "path": str(f["path"]),
                                    "filename": f["filename"],
                                    "line_number": line_idx,
                                    "snippet": line.strip()[:160]
                                })
                                count += 1
                                if count >= max_results:
                                    return results
                except Exception:
                    continue
        finally:
            conn.close()

        return results

    def get_project_tree(self, path: str, max_depth: int = 3) -> str:
        """Generates a clean ASCII tree representation of the directory."""
        root = Path(path).resolve()
        if not root.exists():
            return f"Path not found: {path}"

        lines = [f"{root.name}/"]
        matcher = GitignoreMatcher(root)

        def _walk(current: Path, prefix: str, depth: int):
            if depth > max_depth:
                lines.append(f"{prefix}... (depth limit reached)")
                return

            try:
                entries = sorted(list(current.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            except (PermissionError, OSError):
                return

            filtered = [e for e in entries if e.name not in IGNORED_DIRS and not matcher.is_ignored(e)]
            total = len(filtered)

            for idx, entry in enumerate(filtered):
                is_last = (idx == total - 1)
                connector = "\\-- " if is_last else "|-- "
                sub_prefix = "    " if is_last else "|   "

                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    _walk(entry, prefix + sub_prefix, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")

        _walk(root, "", 1)
        return "\n".join(lines)

    def get_index_stats(self) -> Dict[str, Any]:
        """Returns database statistics."""
        conn = self.storage._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS total_files FROM files")
            total_files = cur.fetchone()["total_files"]
            cur.execute("SELECT COUNT(*) AS total_symbols FROM symbols")
            total_symbols = cur.fetchone()["total_symbols"]
            cur.execute("SELECT file_type, COUNT(*) AS cnt FROM files GROUP BY file_type")
            by_type = {r["file_type"]: r["cnt"] for r in cur.fetchall()}
        finally:
            conn.close()

        return {
            "database_path": self.storage.db_path,
            "total_files": total_files,
            "total_symbols": total_symbols,
            "files_by_type": by_type
        }

    def close(self):
        """Releases all open resources."""
        pass


# ==============================================================================
# CLI Entry Point
# ==============================================================================
def main():
    indexer = SystemIndexer()

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("""AI OS System Indexer & Context Retrieval CLI
Usage:
  ai-index --scan <dir>             # Scan and index directory tree
  ai-index --query <search_term>    # Search code snippets across indexed files
  ai-index --symbol <symbol_name>   # Look up functions, classes, or imports
  ai-index --tree <dir>             # Display ASCII directory hierarchy tree
  ai-index --status                 # Show database index metrics
""")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "--scan":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        print(f"[*] Scanning and indexing '{target}'...")
        res = indexer.scan_directory(target)
        print(f"[OK] Indexed {res['files_indexed']} files and {res['symbols_indexed']} symbols in {res['duration_sec']}s")

    elif cmd == "--query":
        if len(sys.argv) < 3:
            print("Usage: ai-index --query <search_term>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        matches = indexer.search_code(query)
        print(f"Found {len(matches)} matching occurrences:")
        for m in matches:
            print(f"  {m['filename']}:{m['line_number']} -> {m['snippet']}")

    elif cmd == "--symbol":
        if len(sys.argv) < 3:
            print("Usage: ai-index --symbol <name>")
            sys.exit(1)
        sym_name = sys.argv[2]
        syms = indexer.find_symbol(sym_name)
        print(f"Found {len(syms)} symbols matching '{sym_name}':")
        for s in syms:
            print(f"  [{s['symbol_type'].upper()}] {s['signature']} ({s['filename']}:{s['line_number']})")

    elif cmd == "--tree":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        print(indexer.get_project_tree(target))

    elif cmd == "--status":
        stats = indexer.get_index_stats()
        print(f"Database: {stats['database_path']}")
        print(f"Indexed Files: {stats['total_files']}")
        print(f"Indexed Symbols: {stats['total_symbols']}")
        print(f"By Type: {stats['files_by_type']}")

    else:
        print(f"Unrecognized command: {cmd}. Run with --help.")
        sys.exit(1)

if __name__ == "__main__":
    main()
