#!/usr/bin/env python3
"""
index_docs.py - Documentation Ingestion & SQLite FTS5 Indexing Subsystem
Author: Search Engine Architect & Developer Tooling Specialist

Ingests HTML, Markdown, DevDocs bundles, and Manpage specifications into
the OfflineDocsEngine SQLite FTS5 database. Packages and seeds rich offline
documentation sets for Python, Node.js, Rust, Linux CLI, and SQLite.
"""

import os
import sys
import re
import json
import tarfile
import zipfile
import argparse
from pathlib import Path
from html.parser import HTMLParser
from typing import Dict, List, Optional, Any, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from offline_docs_engine import OfflineDocsEngine, resolve_docs_storage_dir


# ==============================================================================
# HTML & Markdown Documentation Extractors
# ==============================================================================
class SimpleHTMLDocParser(HTMLParser):
    """Extracts text, headers, and code snippets from DevDocs or API HTML files."""

    def __init__(self):
        super().__init__()
        self.text_chunks: List[str] = []
        self.code_chunks: List[str] = []
        self.headers: List[Tuple[str, str]] = []  # (tag, text)
        self.in_code = False
        self.in_pre = False
        self.current_tag = ""
        self.current_header = ""

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag.lower()
        if self.current_tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.current_header = ""
        elif self.current_tag == "pre":
            self.in_pre = True
        elif self.current_tag == "code":
            self.in_code = True

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if self.current_header.strip():
                self.headers.append((t, self.current_header.strip()))
            self.current_header = ""
        elif t == "pre":
            self.in_pre = False
        elif t == "code":
            self.in_code = False
        self.current_tag = ""

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if self.current_tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.current_header += (" " + text)
        elif self.in_pre or self.in_code:
            self.code_chunks.append(data)
        else:
            self.text_chunks.append(data)

    def get_full_text(self) -> str:
        return " ".join(self.text_chunks)


class MarkdownDocParser:
    """Parses markdown documentation files to extract symbols, headers, and code."""

    @staticmethod
    def parse_markdown(content: str) -> Dict[str, Any]:
        lines = content.splitlines()
        title = ""
        headers = []
        code_blocks = []
        text_lines = []

        in_code_block = False
        current_code = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_code_block:
                    in_code_block = False
                    code_blocks.append("\n".join(current_code))
                    current_code = []
                else:
                    in_code_block = True
                continue

            if in_code_block:
                current_code.append(line)
                continue

            if stripped.startswith("#"):
                header_text = stripped.lstrip("#").strip()
                headers.append(header_text)
                if not title:
                    title = header_text
            else:
                text_lines.append(stripped)

        return {
            "title": title or "Documentation",
            "headers": headers,
            "code_snippets": code_blocks,
            "content": "\n".join(text_lines)
        }


# ==============================================================================
# Comprehensive Built-in Seed Datasets (Python, Node, Rust, Linux, SQLite)
# ==============================================================================
def get_seed_documentation() -> List[Dict[str, Any]]:
    """
    Returns high-value, official documentation specifications for
    critical developer stacks so the engine is fully populated out-of-the-box.
    """
    docs = []

    # --------------------------------------------------------------------------
    # 1. PYTHON DOCUMENTATION
    # --------------------------------------------------------------------------
    docs.extend([
        {
            "symbol": "json.dumps",
            "title": "json.dumps - Serialize obj to a JSON formatted str",
            "language": "python",
            "category": "module",
            "path": "library/json.html#json.dumps",
            "signature": "json.dumps(obj, *, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, cls=None, indent=None, separators=None, default=None, sort_keys=False, **kw) -> str",
            "parameters": [
                "obj: Python object to serialize (dict, list, tuple, str, int, float, bool, None)",
                "indent: If non-negative integer or string, JSON array elements and object members are pretty-printed",
                "default: Function called for objects that cannot otherwise be serialized",
                "sort_keys: If True, dictionary keys are sorted"
            ],
            "return_type": "str",
            "code_snippets": [
                "import json\n\ndata = {'name': 'AI OS', 'version': '1.0'}\njson_str = json.dumps(data, indent=2, sort_keys=True)\nprint(json_str)"
            ],
            "content": "Serialize obj to a JSON formatted str using this Python-to-JSON conversion table. If ensure_ascii is true (the default), the output is guaranteed to have all incoming non-ASCII characters escaped. If indent is a non-negative integer, then JSON array elements and object members will be pretty-printed with that indent level.",
            "summary": "Serializes a Python object to a JSON formatted string with optional indentation and key sorting."
        },
        {
            "symbol": "json.loads",
            "title": "json.loads - Deserialize s to a Python object",
            "language": "python",
            "category": "module",
            "path": "library/json.html#json.loads",
            "signature": "json.loads(s, *, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, **kw) -> Any",
            "parameters": [
                "s: A str, bytes or bytearray instance containing a JSON document",
                "object_hook: Optional function that will be called with the result of any object literal decoded",
                "object_pairs_hook: Optional function that will be called with the result of any object literal decoded with an ordered list of pairs"
            ],
            "return_type": "Any",
            "code_snippets": [
                "import json\n\njson_str = '{\"status\": \"active\", \"id\": 42}'\ndata = json.loads(json_str)\nprint(data['status'])"
            ],
            "content": "Deserialize s (a str, bytes or bytearray instance containing a JSON document) to a Python object using standard conversion table. Raises json.JSONDecodeError on invalid JSON.",
            "summary": "Deserializes a JSON formatted string, bytes or bytearray into a Python dictionary or list."
        },
        {
            "symbol": "os.path.join",
            "title": "os.path.join - Join one or more path components",
            "language": "python",
            "category": "module",
            "path": "library/os.path.html#os.path.join",
            "signature": "os.path.join(path, *paths) -> str",
            "parameters": [
                "path: Initial path component",
                "*paths: Subsequent path components to concatenate intelligently"
            ],
            "return_type": "str",
            "code_snippets": [
                "import os\n\nfull_path = os.path.join('/workspace', 'projects', 'app', 'main.py')\nprint(full_path)"
            ],
            "content": "Join one or more path components intelligently. The return value is the concatenation of path and any members of *paths with exactly one directory separator following each non-empty part, except the last. If a component is an absolute path, all previous components are discarded.",
            "summary": "Intelligently joins one or more path segments using the current operating system separator."
        },
        {
            "symbol": "pathlib.Path",
            "title": "pathlib.Path - Object-oriented filesystem path handler",
            "language": "python",
            "category": "class",
            "path": "library/pathlib.html#pathlib.Path",
            "signature": "class pathlib.Path(*pathsegments)",
            "parameters": [
                "*pathsegments: String or Path segments to form a new Path object"
            ],
            "return_type": "Path",
            "code_snippets": [
                "from pathlib import Path\n\np = Path('/workspace/projects') / 'demo.py'\np.parent.mkdir(parents=True, exist_ok=True)\np.write_text('print(\"Hello\")', encoding='utf-8')\nprint(p.exists(), p.read_text())"
            ],
            "content": "A subclass of PurePath representing concrete paths for the system's path flavour (PosixPath or WindowsPath). Provides methods such as .exists(), .is_file(), .is_dir(), .mkdir(), .write_text(), .read_text(), and .resolve().",
            "summary": "Object-oriented representation of a filesystem path offering path manipulation, I/O operations, and permission checks."
        },
        {
            "symbol": "subprocess.run",
            "title": "subprocess.run - Run command with arguments and return CompletedProcess",
            "language": "python",
            "category": "function",
            "path": "library/subprocess.html#subprocess.run",
            "signature": "subprocess.run(args, *, stdin=None, input=None, stdout=None, stderr=None, capture_output=False, shell=False, cwd=None, timeout=None, check=False, encoding=None, errors=None, text=None, env=None) -> CompletedProcess",
            "parameters": [
                "args: String or sequence of program arguments",
                "capture_output: If True, stdout and stderr will be captured",
                "shell: If True, the specified command will be executed through the shell",
                "check: If True and process exits with non-zero code, CalledProcessError is raised",
                "text: If True, stdout and stderr are returned as strings instead of bytes"
            ],
            "return_type": "CompletedProcess",
            "code_snippets": [
                "import subprocess\n\nres = subprocess.run(['git', 'status'], capture_output=True, text=True, check=True)\nprint(res.stdout)"
            ],
            "content": "Run the command described by args. Wait for command to complete, then return a CompletedProcess instance. This is the recommended high-level entrypoint for executing system commands.",
            "summary": "Executes a command line subprocess, waits for completion, and returns output, errors, and returncode."
        },
        {
            "symbol": "sqlite3.connect",
            "title": "sqlite3.connect - Open a connection to an SQLite database",
            "language": "python",
            "category": "function",
            "path": "library/sqlite3.html#sqlite3.connect",
            "signature": "sqlite3.connect(database, timeout=5.0, detect_types=0, isolation_level='DEFERRED', check_same_thread=True, factory=sqlite3.Connection, cached_statements=128, uri=False) -> Connection",
            "parameters": [
                "database: Path to database file or ':memory:' for RAM database",
                "timeout: How many seconds the connection should wait before raising an OperationalError on locked tables",
                "uri: If True, database is interpreted as a URI"
            ],
            "return_type": "sqlite3.Connection",
            "code_snippets": [
                "import sqlite3\n\nconn = sqlite3.connect(':memory:')\nconn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)')\nconn.execute('INSERT INTO users (name) VALUES (?)', ('Alice',))\nconn.commit()\nfor row in conn.execute('SELECT * FROM users'):\n    print(row)"
            ],
            "content": "Open a connection to an SQLite database. You can use ':memory:' to open a database connection to a database that resides in RAM instead of on disk.",
            "summary": "Establishes a connection to a local SQLite database file or in-memory instance."
        },
        {
            "symbol": "fastapi.FastAPI",
            "title": "fastapi.FastAPI - Modern high-performance web framework",
            "language": "python",
            "category": "framework",
            "path": "fastapi/reference/fastapi.html",
            "signature": "class fastapi.FastAPI(title='FastAPI', description='', version='0.1.0', routes=None, middleware=None, ...)",
            "parameters": [
                "title: API document title shown in Swagger UI",
                "docs_url: URL for Swagger documentation (default '/docs')",
                "redoc_url: URL for ReDoc documentation (default '/redoc')"
            ],
            "return_type": "FastAPI",
            "code_snippets": [
                "from fastapi import FastAPI\n\napp = FastAPI(title='AI OS Gateway')\n\n@app.get('/health')\ndef health_check():\n    return {'status': 'healthy'}\n\n# Run with: uvicorn main:app --reload"
            ],
            "content": "FastAPI is a modern, fast (high-performance), web framework for building APIs with Python 3.8+ based on standard Python type hints and Starlette/Pydantic.",
            "summary": "Main FastAPI application class for defining asynchronous REST APIs, routes, dependencies, and Swagger docs."
        },
        {
            "symbol": "pydantic.BaseModel",
            "title": "pydantic.BaseModel - Data validation and settings management",
            "language": "python",
            "category": "framework",
            "path": "pydantic/models.html",
            "signature": "class pydantic.BaseModel(**data)",
            "parameters": [
                "**data: Field keyword arguments validated against model type annotations"
            ],
            "return_type": "BaseModel",
            "code_snippets": [
                "from pydantic import BaseModel, Field\nfrom typing import Optional\n\nclass User(BaseModel):\n    id: int\n    username: str\n    email: Optional[str] = None\n    is_active: bool = True\n\nu = User(id=1, username='root')\nprint(u.model_dump())"
            ],
            "content": "Base class for creating data models in Pydantic. Fields are defined as type annotations. Provides automatic validation, type coercion, JSON serialization (.model_dump_json()), and schema generation.",
            "summary": "Primary Pydantic model base class used for request/response serialization and strict type validation."
        }
    ])

    # --------------------------------------------------------------------------
    # 2. NODE.JS / JAVASCRIPT DOCUMENTATION
    # --------------------------------------------------------------------------
    docs.extend([
        {
            "symbol": "fs.readFileSync",
            "title": "fs.readFileSync - Synchronously read the entire contents of a file",
            "language": "node",
            "category": "module",
            "path": "api/fs.html#fs_fs_readfilesync_path_options",
            "signature": "fs.readFileSync(path[, options]) -> string | Buffer",
            "parameters": [
                "path: <string> | <Buffer> | <URL> | <integer> filename or file descriptor",
                "options: <Object> | <string> encoding ('utf-8') or flag ('r')"
            ],
            "return_type": "string | Buffer",
            "code_snippets": [
                "const fs = require('fs');\n\nconst content = fs.readFileSync('/workspace/config.json', 'utf8');\nconst config = JSON.parse(content);\nconsole.log(config);"
            ],
            "content": "Returns the contents of the path. If the encoding option is specified then this function returns a string. Otherwise it returns a buffer.",
            "summary": "Synchronously reads file content into a UTF-8 string or raw binary Buffer."
        },
        {
            "symbol": "fs.promises.writeFile",
            "title": "fs.promises.writeFile - Asynchronously writes data to a file",
            "language": "node",
            "category": "module",
            "path": "api/fs.html#fspromiseswritefilefile-data-options",
            "signature": "fs.promises.writeFile(file, data[, options]) -> Promise<void>",
            "parameters": [
                "file: <string> | <Buffer> | <URL> | <FileHandle> filename or handle",
                "data: <string> | <Buffer> | <TypedArray> | <DataView> | <AsyncIterable>",
                "options: <Object> | <string> encoding ('utf8'), mode (0o666), flag ('w')"
            ],
            "return_type": "Promise<void>",
            "code_snippets": [
                "const fs = require('fs').promises;\n\nasync function save() {\n  await fs.writeFile('output.txt', 'Hello AI OS', 'utf8');\n  console.log('File written');\n}\nsave();"
            ],
            "content": "Asynchronously writes data to a file, replacing the file if it already exists. Returns a Promise that resolves with no arguments upon success.",
            "summary": "Asynchronous Promise-based file writer supporting strings, binary buffers, and encoding options."
        },
        {
            "symbol": "path.join",
            "title": "path.join - Join all given path segments together",
            "language": "node",
            "category": "module",
            "path": "api/path.html#path_path_join_paths",
            "signature": "path.join([...paths]) -> string",
            "parameters": [
                "...paths: <string> A sequence of path segments"
            ],
            "return_type": "string",
            "code_snippets": [
                "const path = require('path');\n\nconst full = path.join(__dirname, 'src', 'index.js');\nconsole.log(full);"
            ],
            "content": "The path.join() method joins all given path segments together using the platform-specific separator as a delimiter, then normalizes the resulting path. Zero-length path segments are ignored.",
            "summary": "Joins arbitrary file path segments using system delimiters and normalizes path separators."
        },
        {
            "symbol": "child_process.exec",
            "title": "child_process.exec - Spawns a shell and runs a command",
            "language": "node",
            "category": "module",
            "path": "api/child_process.html#child_process_child_process_exec_command_options_callback",
            "signature": "child_process.exec(command[, options][, callback]) -> ChildProcess",
            "parameters": [
                "command: <string> The command to run with space-separated arguments",
                "options: <Object> cwd, env, timeout, maxBuffer (default 1024*1024)",
                "callback: <Function> (error, stdout, stderr)"
            ],
            "return_type": "ChildProcess",
            "code_snippets": [
                "const { exec } = require('child_process');\n\nexec('uname -a', (err, stdout, stderr) => {\n  if (err) return console.error(err);\n  console.log('Kernel:', stdout.trim());\n});"
            ],
            "content": "Spawns a shell then executes the command within that shell, buffering any generated output. The callback is invoked with stdout and stderr.",
            "summary": "Executes shell command asynchronously, capturing stdout and stderr via callback or promisified wrapper."
        },
        {
            "symbol": "http.createServer",
            "title": "http.createServer - Returns a new instance of http.Server",
            "language": "node",
            "category": "module",
            "path": "api/http.html#httpcreateserveroptions-requestlistener",
            "signature": "http.createServer([options][, requestListener]) -> http.Server",
            "parameters": [
                "options: <Object> InsecureHTTPParser, maxHeaderSize, etc.",
                "requestListener: <Function> Automatically added to the 'request' event: (req, res)"
            ],
            "return_type": "http.Server",
            "code_snippets": [
                "const http = require('http');\n\nconst server = http.createServer((req, res) => {\n  res.writeHead(200, { 'Content-Type': 'application/json' });\n  res.end(JSON.stringify({ status: 'ok' }));\n});\nserver.listen(3000, () => console.log('Listening on 3000'));"
            ],
            "content": "Returns a new instance of http.Server. The requestListener is a function which is automatically added to the 'request' event.",
            "summary": "Instantiates an HTTP server handling incoming requests and returning responses."
        }
    ])

    # --------------------------------------------------------------------------
    # 3. RUST DOCUMENTATION
    # --------------------------------------------------------------------------
    docs.extend([
        {
            "symbol": "std::fs::read_to_string",
            "title": "std::fs::read_to_string - Read the entire contents of a file into a string",
            "language": "rust",
            "category": "function",
            "path": "std/fs/fn.read_to_string.html",
            "signature": "pub fn read_to_string<P: AsRef<Path>>(path: P) -> Result<String>",
            "parameters": [
                "path: An object implementing AsRef<Path>"
            ],
            "return_type": "std::io::Result<String>",
            "code_snippets": [
                "use std::fs;\n\nfn main() -> std::io::Result<()> {\n    let content = fs::read_to_string(\"/etc/os-release\")?;\n    println!(\"{}\", content);\n    Ok(())\n}"
            ],
            "content": "Read the entire contents of a file into a string. This is a convenience function for using File::open and read_to_end with an allocated String. Returns Err if file not found or contains invalid UTF-8.",
            "summary": "Reads a file at the specified path into a String, returning an io::Result."
        },
        {
            "symbol": "std::sync::Arc",
            "title": "std::sync::Arc - Atomically reference-counted pointer",
            "language": "rust",
            "category": "struct",
            "path": "std/sync/struct.Arc.html",
            "signature": "pub struct Arc<T: ?Sized> { /* private fields */ }",
            "parameters": [
                "T: Inner type wrapped in atomic reference counted pointer"
            ],
            "return_type": "Arc<T>",
            "code_snippets": [
                "use std::sync::{Arc, Mutex};\nuse std::thread;\n\nlet counter = Arc::new(Mutex::new(0));\nlet c = Arc::clone(&counter);\nthread::spawn(move || {\n    let mut val = c.lock().unwrap();\n    *val += 1;\n}).join().unwrap();"
            ],
            "content": "A thread-safe reference-counting pointer. 'Arc' stands for 'Atomically Reference Counted'. Provides shared ownership of an immutable value of type T allocated in the heap.",
            "summary": "Thread-safe atomically reference-counted pointer for sharing data across threads."
        },
        {
            "symbol": "Option::unwrap",
            "title": "Option::unwrap - Returns the contained Some value or panics",
            "language": "rust",
            "category": "method",
            "path": "std/option/enum.Option.html#method.unwrap",
            "signature": "pub const fn unwrap(self) -> T",
            "parameters": [],
            "return_type": "T",
            "code_snippets": [
                "let x: Option<&str> = Some(\"air\");\nassert_eq!(x.unwrap(), \"air\");\n\n// Use unwrap_or to avoid panics in production:\nlet y: Option<&str> = None;\nlet val = y.unwrap_or(\"default\");"
            ],
            "content": "Returns the contained Some value, consuming the self value. Because this function may panic, its use is generally discouraged. Instead, prefer pattern matching, unwrap_or, unwrap_or_else, or the '?' operator.",
            "summary": "Extracts the value from a Some variant or triggers a runtime panic if None."
        }
    ])

    # --------------------------------------------------------------------------
    # 4. LINUX CLI & COREUTILS DOCUMENTATION
    # --------------------------------------------------------------------------
    docs.extend([
        {
            "symbol": "grep",
            "title": "grep - print lines matching a pattern",
            "language": "linux",
            "category": "command",
            "path": "man/man1/grep.1.html",
            "signature": "grep [OPTIONS] PATTERN [FILE...]",
            "parameters": [
                "-E, --extended-regexp: Interpret PATTERN as extended regular expression",
                "-F, --fixed-strings: Interpret PATTERN as fixed strings (fast)",
                "-i, --ignore-case: Case insensitive matching",
                "-r, -R, --recursive: Read all files under each directory recursively",
                "-n, --line-number: Prefix each line of output with line number",
                "-v, --invert-match: Select non-matching lines"
            ],
            "return_type": "exit code (0 on match, 1 on no match, 2 on error)",
            "code_snippets": [
                "grep -rn 'TODO' /workspace/src/\ngrep -E 'error|fatal' /var/log/syslog"
            ],
            "content": "grep searches for PATTERN in each FILE. A PATTERN is one or more regular expressions separated by newline characters. grep prints each line that matches a pattern.",
            "summary": "Fast text search utility scanning files for regular expression or literal string pattern matches."
        },
        {
            "symbol": "find",
            "title": "find - search for files in a directory hierarchy",
            "language": "linux",
            "category": "command",
            "path": "man/man1/find.1.html",
            "signature": "find [-H] [-L] [-P] [path...] [expression]",
            "parameters": [
                "-name pattern: Base of file name matches shell pattern",
                "-type [f|d|l]: File is of type f (regular file), d (directory), l (symlink)",
                "-mtime n: File data was last modified n*24 hours ago",
                "-exec command {} +: Execute command on matched files"
            ],
            "return_type": "exit code",
            "code_snippets": [
                "find /workspace -type f -name '*.py'\nfind . -name '*.log' -mtime +7 -delete"
            ],
            "content": "find searches the directory tree rooted at each given file name by evaluating the given expression from left to right, according to the rules of precedence, until the outcome is known.",
            "summary": "Recursively searches directory hierarchies matching criteria such as name, size, type, or timestamps."
        },
        {
            "symbol": "systemctl",
            "title": "systemctl - Control the systemd system and service manager",
            "language": "linux",
            "category": "command",
            "path": "man/man1/systemctl.1.html",
            "signature": "systemctl [OPTIONS...] COMMAND [UNIT...]",
            "parameters": [
                "start UNIT: Start (activate) one or more units",
                "stop UNIT: Stop (deactivate) one or more units",
                "restart UNIT: Stop and then start one or more units",
                "status UNIT: Show terse runtime status information about one or more units",
                "enable UNIT: Enable one or more unit files to start on boot"
            ],
            "return_type": "exit code",
            "code_snippets": [
                "systemctl status ollama.service\nsudo systemctl restart docker\nsystemctl list-units --type=service"
            ],
            "content": "systemctl may be used to introspect and control the state of the 'systemd' system and service manager.",
            "summary": "Command-line utility for managing system services, daemons, targets, and sockets in modern Linux."
        },
        {
            "symbol": "tar",
            "title": "tar - an archiving utility",
            "language": "linux",
            "category": "command",
            "path": "man/man1/tar.1.html",
            "signature": "tar [OPTION...] [FILE]...",
            "parameters": [
                "-c, --create: Create a new archive",
                "-x, --extract: Extract files from an archive",
                "-z, --gzip: Filter the archive through gzip",
                "-f, --file=ARCHIVE: Use archive file ARCHIVE",
                "-v, --verbose: Verbosely list files processed"
            ],
            "return_type": "exit code",
            "code_snippets": [
                "tar -czvf backup.tar.gz /workspace/projects\ntar -xzvf backup.tar.gz -C /workspace/restored"
            ],
            "content": "GNU tar is an archiving program designed to store multiple files in a single file (an archive), and to manipulate such archives.",
            "summary": "Standard Unix file archiving utility for creating and extracting tar, tar.gz, and tar.bz2 bundles."
        }
    ])

    # --------------------------------------------------------------------------
    # 5. SQLITE DOCUMENTATION
    # --------------------------------------------------------------------------
    docs.extend([
        {
            "symbol": "CREATE VIRTUAL TABLE fts5",
            "title": "SQLite FTS5 - Full-Text Search Virtual Table Syntax",
            "language": "sqlite",
            "category": "syntax",
            "path": "fts5.html",
            "signature": "CREATE VIRTUAL TABLE table_name USING fts5(col1, col2, ..., tokenize='porter unicode61');",
            "parameters": [
                "col1, col2: Column names indexed by the FTS engine",
                "tokenize: Tokenizer algorithm ('porter', 'unicode61', 'ascii')",
                "content: External content table to reference without duplicating data"
            ],
            "return_type": "virtual table",
            "code_snippets": [
                "CREATE VIRTUAL TABLE docs_fts USING fts5(title, content, tokenize='porter unicode61');\n\n-- Fast search query:\nSELECT * FROM docs_fts WHERE docs_fts MATCH 'python AND sqlite' ORDER BY bm25(docs_fts);"
            ],
            "content": "FTS5 is an SQLite virtual table module that provides full-text search capability. FTS5 allows users to efficiently search large collections of documents for words or phrases. Supports BM25 ranking, prefix queries (*), and phrase queries.",
            "summary": "Creates an SQLite Full-Text Search version 5 virtual table supporting BM25 ranking and tokenization."
        },
        {
            "symbol": "json_extract",
            "title": "json_extract - Extract values from a JSON string",
            "language": "sqlite",
            "category": "function",
            "path": "json1.html#jex",
            "signature": "json_extract(json, path1, path2, ...) -> Any",
            "parameters": [
                "json: Well-formed JSON text or BLOB",
                "path: JSON path expression starting with '$' (e.g. '$.user.name' or '$[0]')"
            ],
            "return_type": "SQL value (TEXT, INTEGER, REAL, or NULL)",
            "code_snippets": [
                "SELECT json_extract('{\"user\": {\"name\": \"Alice\", \"age\": 30}}', '$.user.name');\n-- Returns: 'Alice'"
            ],
            "content": "The json_extract() function extracts and returns one or more values from well-formed JSON at specified paths. If multiple paths are given, values are returned inside a JSON array.",
            "summary": "Extracts scalar values or sub-objects from JSON strings stored in SQLite columns."
        },
        {
            "symbol": "PRAGMA journal_mode",
            "title": "PRAGMA journal_mode - Query or set the database journal mode",
            "language": "sqlite",
            "category": "pragma",
            "path": "pragma.html#pragma_journal_mode",
            "signature": "PRAGMA journal_mode = DELETE | TRUNCATE | PERSIST | MEMORY | WAL | OFF;",
            "parameters": [
                "WAL: Write-Ahead Logging mode for massive concurrent read/write performance",
                "DELETE: Default rollback journal mode"
            ],
            "return_type": "TEXT string of the active mode",
            "code_snippets": [
                "PRAGMA journal_mode = WAL;\nPRAGMA synchronous = NORMAL;"
            ],
            "content": "This pragma queries or sets the journal mode for databases associated with the connection. WAL mode provides much faster concurrent writes without blocking readers.",
            "summary": "Configures SQLite transactional journaling mode (WAL mode enables high-speed concurrency)."
        }
    ])

    return docs


# ==============================================================================
# Indexing Controller & Pipeline
# ==============================================================================
class DocsIndexer:
    """Orchestrates indexing of seed documentation, custom folders, and DevDocs packages."""

    def __init__(self, engine: Optional[OfflineDocsEngine] = None):
        self.engine = engine or OfflineDocsEngine()

    def seed_default_documentation(self, force: bool = False) -> int:
        """
        Populates the SQLite FTS5 database with core documentation sets
        if currently empty or if force=True.
        """
        if not force and not self.engine.is_empty():
            stats = self.engine.get_stats()
            print(f"[*] Offline Docs Engine already contains {stats['total_entries']} entries across {stats['total_docsets']} docsets.")
            return stats['total_entries']

        print("\033[1;36m[*] Seeding comprehensive offline documentation sets into SQLite FTS5 database...\033[0m")
        seed_data = get_seed_documentation()

        # Group by language
        by_lang: Dict[str, List[Dict[str, Any]]] = {}
        for d in seed_data:
            lang = d["language"]
            by_lang.setdefault(lang, []).append(d)

        total_indexed = 0
        for lang, docs in by_lang.items():
            docset_name = f"{lang}_core_docs"
            count = self.engine.bulk_index_documents(docs, docset_name=docset_name, language=lang)
            print(f"\033[1;32m  [+] Indexed {count} symbols for docset: '{docset_name}' ({lang})\033[0m")
            total_indexed += count

        print(f"\033[1;32m[OK] Successfully indexed {total_indexed} total documentation symbols into: {self.engine.db_path}\033[0m")
        return total_indexed

    def index_directory(self, target_dir: str, language: str = "generic") -> int:
        """
        Recursively scans a directory for .html and .md files and indexes them.
        """
        path = Path(target_dir).resolve()
        if not path.exists():
            print(f"[!] Directory does not exist: {target_dir}")
            return 0

        print(f"\033[1;34m[*] Scanning and indexing directory: {path} (Language: {language})...\033[0m")
        indexed_count = 0
        batch: List[Dict[str, Any]] = []

        for f in path.rglob("*"):
            if not f.is_file():
                continue

            rel_path = str(f.relative_to(path))
            stem = f.stem

            if f.suffix.lower() in (".html", ".htm"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    parser = SimpleHTMLDocParser()
                    parser.feed(content)
                    full_text = parser.get_full_text()
                    title = parser.headers[0][1] if parser.headers else stem

                    batch.append({
                        "symbol": stem,
                        "title": title,
                        "category": "html_doc",
                        "path": rel_path,
                        "signature": "",
                        "parameters": [],
                        "return_type": "",
                        "code_snippets": parser.code_chunks[:3],
                        "content": full_text[:4000],
                        "summary": full_text[:200]
                    })
                except Exception as e:
                    continue

            elif f.suffix.lower() in (".md", ".markdown"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    parsed = MarkdownDocParser.parse_markdown(content)
                    batch.append({
                        "symbol": stem,
                        "title": parsed["title"],
                        "category": "markdown_doc",
                        "path": rel_path,
                        "signature": "",
                        "parameters": [],
                        "return_type": "",
                        "code_snippets": parsed["code_snippets"][:3],
                        "content": parsed["content"][:4000],
                        "summary": parsed["content"][:200]
                    })
                except Exception:
                    continue

            if len(batch) >= 100:
                self.engine.bulk_index_documents(batch, f"dir_{path.name}", language)
                indexed_count += len(batch)
                batch = []

        if batch:
            self.engine.bulk_index_documents(batch, f"dir_{path.name}", language)
            indexed_count += len(batch)

        print(f"\033[1;32m[OK] Indexed {indexed_count} files from {target_dir}\033[0m")
        return indexed_count

    def index_archive(self, archive_path: str, language: str = "generic") -> int:
        """
        Unpacks a compressed .tar.gz or .zip file and indexes its contents.
        """
        arc = Path(archive_path).resolve()
        if not arc.exists():
            print(f"[!] Archive file not found: {archive_path}")
            return 0

        extract_dir = self.engine.storage_dir / "unpacked" / arc.stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        print(f"\033[1;34m[*] Unpacking {arc.name} to {extract_dir}...\033[0m")
        if arc.name.endswith(".zip"):
            with zipfile.ZipFile(arc, "r") as z:
                z.extractall(extract_dir)
        elif arc.name.endswith((".tar.gz", ".tgz", ".tar")):
            with tarfile.open(arc, "r:*") as t:
                t.extractall(extract_dir)
        else:
            print(f"[!] Unsupported archive format: {arc.name}")
            return 0

        return self.index_directory(str(extract_dir), language=language)


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="AI OS Documentation Ingestion & Indexer")
    parser.add_argument("--seed", action="store_true", help="Populate default offline documentation sets (Python, Node, Rust, Linux, SQLite)")
    parser.add_argument("--force", action="store_true", help="Force re-seeding even if database contains data")
    parser.add_argument("--dir", type=str, help="Index all HTML/Markdown documentation inside a directory")
    parser.add_argument("--archive", type=str, help="Unpack and index a .tar.gz or .zip documentation bundle")
    parser.add_argument("--lang", type=str, default="generic", help="Language tag for directory or archive")
    parser.add_argument("--stats", action="store_true", help="Display index statistics")
    parser.add_argument("--storage", type=str, help="Custom directory path for SQLite FTS database")

    args = parser.parse_args()

    engine = OfflineDocsEngine(storage_dir=args.storage)
    indexer = DocsIndexer(engine)

    if args.stats:
        stats = engine.get_stats()
        print(json.dumps(stats, indent=2))
        langs = engine.list_supported_languages()
        print("Languages indexed:")
        for l in langs:
            print(f"  - {l['language'].upper()}: {l['total_symbols']} entries")
        return

    if args.dir:
        indexer.index_directory(args.dir, language=args.lang)
    elif args.archive:
        indexer.index_archive(args.archive, language=args.lang)
    else:
        # Default behavior: ensure database is seeded
        indexer.seed_default_documentation(force=args.force)


if __name__ == "__main__":
    main()
