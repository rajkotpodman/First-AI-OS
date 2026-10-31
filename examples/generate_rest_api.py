#!/usr/bin/env python3
"""
generate_rest_api.py - Example Usage Script for Project Architect Engine
Demonstrates automated scaffolding, Git initialization, and sandbox verification
for a production-ready FastAPI SQLite REST API service.
"""

import os
import sys
import json
from pathlib import Path

# Add src to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from project_architect import ProjectArchitect

# Sample production-ready REST API blueprint for offline/standalone execution
SAMPLE_REST_API_BLUEPRINT = {
    "project_name": "fastapi_auth_service",
    "description": "Production-grade REST API with FastAPI, SQLite ORM, and JWT authentication",
    "runtime": "python",
    "dependencies": {
        "pip": ["fastapi", "uvicorn", "pydantic", "sqlite3"],
        "system": ["sqlite"]
    },
    "files": [
        {
            "path": "requirements.txt",
            "content": "fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\n",
            "description": "Python dependencies"
        },
        {
            "path": "app/database.py",
            "content": """import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "app.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL
            )
        ''')
        conn.commit()
""",
            "description": "SQLite connection and schema manager"
        },
        {
            "path": "app/main.py",
            "content": """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .database import get_connection, init_db

app = FastAPI(title="FastAPI Auth Service", version="1.0.0")

class UserCreate(BaseModel):
    username: str
    email: str

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "fastapi-auth"}

@app.post("/users", status_code=201)
def create_user(user: UserCreate):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, email) VALUES (?, ?)", (user.username, user.email))
        conn.commit()
        return {"id": cur.lastrowid, "username": user.username, "email": user.email}
    except Exception as e:
        raise HTTPException(status_code=400, detail="User already exists or invalid data")
    finally:
        conn.close()

@app.get("/users")
def list_users():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, email FROM users")
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()
""",
            "description": "Core FastAPI application routes"
        },
        {
            "path": "tests/test_api.py",
            "content": """import unittest
import os
import sys

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.database import init_db, get_connection

class TestDatabase(unittest.TestCase):
    def setUp(self):
        os.environ["DB_PATH"] = ":memory:"
        init_db()

    def test_database_table_creation(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "users")
        conn.close()

    def test_user_insertion(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, email) VALUES ('alice', 'alice@test.com')")
        conn.commit()
        cur.execute("SELECT * FROM users WHERE username='alice'")
        user = cur.fetchone()
        self.assertEqual(user["email"], "alice@test.com")
        conn.close()

if __name__ == '__main__':
    unittest.main()
""",
            "description": "Unit tests for database and business logic"
        },
        {
            "path": "Dockerfile",
            "content": """FROM python:3.11-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
            "description": "Docker container build configuration"
        },
        {
            "path": "README.md",
            "content": """# FastAPI Auth Service
Automated microservice scaffolded by AI OS Project Architect Engine.

## Running Locally:
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Running Tests:
```bash
python -m unittest discover tests
```
""",
            "description": "Project documentation"
        }
    ],
    "setup_commands": ["pip install -r requirements.txt"],
    "entrypoint": "uvicorn app.main:app --host 0.0.0.0 --port 8000",
    "test_command": "python -m unittest discover tests"
}

def main():
    print("==================================================================")
    print("  AI OS Autonomous Project Architect — Sample REST API Generator")
    print("==================================================================")

    architect = ProjectArchitect()

    # If user provided a command line argument, attempt AI generation
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"[*] Processing user prompt: '{query}'")
        result = architect.build_project(query, run_verification=True)
    else:
        # Standalone scaffold demonstration using sample blueprint
        print("[*] Scaffolding sample FastAPI REST API project from architectural blueprint...")
        success, proj_path, files = architect.scaffold_project(SAMPLE_REST_API_BLUEPRINT)
        lifecycle = architect.build_and_verify(proj_path, SAMPLE_REST_API_BLUEPRINT, run_sandbox=False, install_deps=False)

        result = {
            "success": success,
            "project_name": SAMPLE_REST_API_BLUEPRINT["project_name"],
            "project_path": str(proj_path),
            "files_created": files,
            "lifecycle": lifecycle
        }

    print("\n[OK] Project Generation Result:")
    print(json.dumps(result, indent=2))
    print(f"\nTarget project location: {result.get('project_path')}")

if __name__ == "__main__":
    main()
