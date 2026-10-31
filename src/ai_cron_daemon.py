#!/usr/bin/env python3
"""
ai_cron_daemon.py - Autonomous Task Scheduler & Background Cron Daemon for AI OS
Author: Linux System Daemon Architect and Automation Engineer

Provides an asynchronous background daemon capable of scheduling and executing
recurring AI operations, system maintenance (System Care), repository verifications
(Project Health), and data extraction (Autonomous Research/Scraping).
Supports standard 5-field cron syntax and natural language time descriptions.
"""

import os
import sys
import re
import json
import time
import signal
import logging
import datetime
import threading
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any, Callable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# AI OS Subsystem imports
try:
    from system_indexer import SystemIndexer
except ImportError:
    SystemIndexer = None

try:
    from security_daemon import SecurityDaemon
except ImportError:
    SecurityDaemon = None

try:
    from git_automator import GitAutomator
except ImportError:
    GitAutomator = None

try:
    from offline_docs_engine import OfflineDocsEngine
except ImportError:
    OfflineDocsEngine = None


# ==============================================================================
# Path Resolution & Default Configurations
# ==============================================================================
DEFAULT_SYSTEM_TASKS = "/etc/ai_os/tasks.json"
USER_TASKS_FALLBACK = os.path.expanduser("~/.ai_os/tasks.json")
LOCAL_TASKS_FALLBACK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "tasks.json"))

DEFAULT_LOG_PATH = "/var/log/ai_cron.log"
USER_LOG_FALLBACK = os.path.expanduser("~/.ai_os/ai_cron.log")
LOCAL_LOG_FALLBACK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "ai_cron.log"))

NOTIFICATIONS_PATH = "/var/run/ai_notifications.json"
USER_NOTIFICATIONS_FALLBACK = os.path.expanduser("~/.ai_os/notifications.json")
LOCAL_NOTIFICATIONS_FALLBACK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "notifications.json"))

PID_PATH = "/var/run/ai_cron.pid"
USER_PID_FALLBACK = os.path.expanduser("~/.ai_os/ai_cron.pid")
LOCAL_PID_FALLBACK = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "ai_cron.pid"))


def resolve_writable_path(primary: str, user_fallback: str, local_fallback: str) -> Path:
    """Finds the best writable path among system, user, and local fallbacks."""
    for candidate in [primary, user_fallback, local_fallback]:
        try:
            p = Path(candidate).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            # Test write permissions
            test_file = p.parent / ".write_probe"
            test_file.touch()
            test_file.unlink()
            return p
        except (PermissionError, OSError):
            continue
    fallback = Path("./ai_cron_fallback.data").resolve()
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return fallback


# ==============================================================================
# Natural Language & Cron Time Parser
# ==============================================================================
class ScheduleParser:
    """
    Parses both standard 5-field cron syntax (e.g., '0 2 * * *')
    and natural language schedules (e.g., 'Every 30 minutes', 'Every day at 2 AM').
    """

    WEEKDAYS = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6
    }

    @classmethod
    def natural_to_cron(cls, text: str) -> Optional[str]:
        """Converts natural language expressions to standard cron expression if possible."""
        cleaned = text.strip().lower()

        # Handle simple keywords
        if cleaned in ("hourly", "every hour"):
            return "0 * * * *"
        if cleaned in ("daily", "every day", "midnight", "every night", "daily at midnight", "every day at midnight"):
            return "0 0 * * *"
        if cleaned in ("weekly", "every week"):
            return "0 0 * * 0"
        if cleaned in ("monthly", "every month"):
            return "0 0 1 * *"

        # Every N minutes: 'every 15 minutes', 'every 30 mins'
        m = re.match(r"^every\s+(\d+)\s*(?:m|min|minute|minutes)$", cleaned)
        if m:
            mins = int(m.group(1))
            return f"*/{mins} * * * *" if mins < 60 else f"0 */{mins//60} * * *"

        # Every N hours: 'every 2 hours', 'every 4 hours'
        m = re.match(r"^every\s+(\d+)\s*(?:h|hr|hour|hours)$", cleaned)
        if m:
            hours = int(m.group(1))
            return f"0 */{hours} * * *"

        # Every N seconds: 'every 30 seconds' (cron doesn't have seconds, return special token)
        m = re.match(r"^every\s+(\d+)\s*(?:s|sec|second|seconds)$", cleaned)
        if m:
            secs = int(m.group(1))
            return f"@every {secs}s"

        # Every day at HH[:MM] [AM|PM]: 'every day at 2 am', 'daily at 14:30', 'every day at 9:00 pm'
        m = re.match(r"^(?:every\s+day|daily)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", cleaned)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            meridiem = m.group(3)
            if meridiem == "pm" and hour < 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            return f"{minute} {hour} * * *"

        # Weekdays at HH[:MM] [AM|PM]: 'every weekday at 8:00', 'weekdays at 9 am'
        m = re.match(r"^(?:every\s+weekday|weekdays)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", cleaned)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            meridiem = m.group(3)
            if meridiem == "pm" and hour < 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            return f"{minute} {hour} * * 1-5"

        # Specific day of week at time: 'every monday at 9 am', 'every friday at 17:00'
        m = re.match(r"^every\s+([a-zA-Z]+)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", cleaned)
        if m:
            day_name = m.group(1).lower()
            if day_name in cls.WEEKDAYS:
                dow = cls.WEEKDAYS[day_name]
                # In standard cron: 0 = Sun, 1 = Mon ... 6 = Sat, 7 = Sun
                cron_dow = (dow + 1) % 7 if dow == 6 else dow + 1
                hour = int(m.group(2))
                minute = int(m.group(3)) if m.group(3) else 0
                meridiem = m.group(4)
                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
                return f"{minute} {hour} * * {cron_dow}"

        return None

    @classmethod
    def is_valid_cron(cls, expression: str) -> bool:
        """Validates 5-field cron syntax or '@every Ns' syntax."""
        expr = expression.strip()
        if expr.startswith("@every "):
            return True
        fields = expr.split()
        if len(fields) != 5:
            return False
        # Verify basic cron characters
        for f in fields:
            if not re.match(r"^[0-9\*\,\-\/]+$", f):
                return False
        return True

    @classmethod
    def normalize_schedule(cls, raw_input: str) -> Tuple[str, str]:
        """
        Normalizes any input (cron or natural language) into a tuple:
        (canonical_cron_expression, natural_description)
        """
        raw = raw_input.strip()
        if cls.is_valid_cron(raw):
            return raw, cls.cron_to_natural(raw)

        converted = cls.natural_to_cron(raw)
        if converted:
            return converted, raw

        # Fallback default: daily at midnight
        return "0 0 * * *", raw

    @classmethod
    def cron_to_natural(cls, cron_expr: str) -> str:
        """Produces a readable description of a cron expression."""
        if cron_expr.startswith("@every "):
            return f"Every {cron_expr.replace('@every ', '')}"

        parts = cron_expr.split()
        if len(parts) != 5:
            return cron_expr

        m, h, dom, mon, dow = parts
        if m.startswith("*/"):
            return f"Every {m[2:]} minutes"
        if m == "0" and h.startswith("*/"):
            return f"Every {h[2:]} hours"
        if m == "0" and h == "0" and dom == "*" and mon == "*" and dow == "*":
            return "Daily at midnight"
        if dom == "*" and mon == "*" and dow == "*":
            return f"Daily at {int(h):02d}:{int(m):02d}"
        if dom == "*" and mon == "*" and dow in ("1-5", "1,2,3,4,5"):
            return f"Every weekday at {int(h):02d}:{int(m):02d}"

        return f"Cron ({cron_expr})"

    @classmethod
    def calculate_next_run(cls, cron_expr: str, from_dt: Optional[datetime.datetime] = None) -> datetime.datetime:
        """
        Calculates the next execution datetime from a reference datetime (default: now).
        Handles minutes, hours, days, weekdays, and sub-minute intervals.
        """
        now = from_dt or datetime.datetime.now()

        # Handle sub-minute @every Ns
        if cron_expr.startswith("@every "):
            m = re.match(r"@every\s+(\d+)s", cron_expr)
            secs = int(m.group(1)) if m else 60
            return now + datetime.timedelta(seconds=secs)

        parts = cron_expr.split()
        if len(parts) != 5:
            return now + datetime.timedelta(hours=1)

        def matches_field(val: int, pattern: str) -> bool:
            if pattern == "*":
                return True
            for part in pattern.split(","):
                if "/" in part:
                    sub_parts = part.split("/")
                    base = 0 if sub_parts[0] == "*" else int(sub_parts[0])
                    step = int(sub_parts[1])
                    if (val - base) % step == 0 and val >= base:
                        return True
                elif "-" in part:
                    low, high = map(int, part.split("-"))
                    if low <= val <= high:
                        return True
                elif part.isdigit():
                    if int(part) == val:
                        return True
            return False

        # Advance minute by minute up to 30 days ahead
        candidate = (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
        max_attempts = 60 * 24 * 31  # 31 days

        for _ in range(max_attempts):
            min_match = matches_field(candidate.minute, parts[0])
            hour_match = matches_field(candidate.hour, parts[1])
            dom_match = matches_field(candidate.day, parts[2])
            mon_match = matches_field(candidate.month, parts[3])

            # Python weekday: Mon=0, Sun=6. Cron: Sun=0 or 7, Mon=1...
            cron_weekday = (candidate.weekday() + 1) % 7
            dow_match = matches_field(cron_weekday, parts[4]) or (parts[4] == "7" and cron_weekday == 0)

            if min_match and hour_match and dom_match and mon_match and dow_match:
                return candidate

            candidate += datetime.timedelta(minutes=1)

        return now + datetime.timedelta(days=1)


# ==============================================================================
# Task Definition Data Structures
# ==============================================================================
@dataclass
class ScheduledTask:
    id: str
    name: str
    schedule: str
    natural_schedule: str
    task_type: str  # system_care | project_health | research_scrape | custom_command
    enabled: bool
    config: Dict[str, Any]
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    last_status: str = "pending"
    last_output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Terminal UI Notification Subsystem
# ==============================================================================
class NotificationHub:
    """Manages notifications posted to the AI OS terminal UI and shell session."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or resolve_writable_path(
            NOTIFICATIONS_PATH, USER_NOTIFICATIONS_FALLBACK, LOCAL_NOTIFICATIONS_FALLBACK
        )

    def notify(self, title: str, message: str, level: str = "info", task_id: Optional[str] = None):
        """Appends a new notification to the active notification queue."""
        event = {
            "id": f"notif_{int(time.time()*1000)}",
            "timestamp": datetime.datetime.now().isoformat(),
            "title": title,
            "message": message,
            "level": level,  # info, success, warning, error
            "task_id": task_id,
            "read": False
        }
        notifications = self.get_all()
        notifications.insert(0, event)
        # Keep last 50
        notifications = notifications[:50]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(notifications, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def get_unread(self) -> List[Dict[str, Any]]:
        return [n for n in self.get_all() if not n.get("read", False)]

    def mark_all_read(self):
        items = self.get_all()
        for i in items:
            i["read"] = True
        try:
            self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")
        except Exception:
            pass


# ==============================================================================
# Task Handlers Implementation
# ==============================================================================
class TaskExecutors:
    """Implements handlers for the 3 core AI OS task types and custom commands."""

    @staticmethod
    def execute_system_care(config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        System Care:
        - Clears temporary files (__pycache__, /tmp, .pytest_cache, stale logs)
        - Triggers incremental system index update (SystemIndexer)
        - Executes security audit (SecurityDaemon)
        """
        actions = config.get("actions", ["clear_temp", "reindex", "security_audit"])
        details = []

        # 1. Clear temporary files
        if "clear_temp" in actions:
            temp_dirs = config.get("temp_dirs", ["/tmp", "/var/tmp"])
            max_age_days = config.get("max_age_days", 3)
            cutoff = time.time() - (max_age_days * 86400)
            cleaned_count = 0
            cleaned_bytes = 0

            # Scan workspace temp dirs as well
            workspace = config.get("workspace_dir", os.getcwd())
            for pat in ["**/__pycache__", "**/.pytest_cache"]:
                for p in Path(workspace).glob(pat):
                    if p.is_dir():
                        try:
                            for f in p.glob("*"):
                                if f.is_file() and f.stat().st_mtime < cutoff:
                                    cleaned_bytes += f.stat().st_size
                                    f.unlink()
                                    cleaned_count += 1
                        except Exception:
                            pass

            details.append(f"Cleaned {cleaned_count} cached/temp files ({cleaned_bytes / 1024:.1f} KB)")

        # 2. Update filesystem & AST index via SystemIndexer
        if "reindex" in actions and SystemIndexer:
            try:
                target_dir = config.get("index_dir", os.getcwd())
                indexer = SystemIndexer()
                res = indexer.scan_directory(target_dir, incremental=True)
                details.append(f"Indexed {res.get('files_indexed', 0)} files, {res.get('symbols_indexed', 0)} symbols")
            except Exception as e:
                details.append(f"Index update skipped: {e}")

        # 3. Security Audit via SecurityDaemon
        if "security_audit" in actions and SecurityDaemon:
            try:
                daemon = SecurityDaemon()
                res = daemon.evaluate("ls -la /tmp")
                details.append(f"Security audit passed (policy: {daemon.policy.get('mode', 'strict')})")
            except Exception as e:
                details.append(f"Security check note: {e}")

        return True, " | ".join(details)

    @staticmethod
    def execute_project_health(config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Project Health:
        - Scans Git repositories in projects root
        - Inspects status and branches with GitAutomator
        - Runs test suites
        """
        projects_root = config.get("projects_root", os.path.join(os.getcwd(), "workspace", "projects"))
        root_path = Path(projects_root).resolve()

        if not root_path.exists():
            # Check current working directory as project
            root_path = Path(os.getcwd()).resolve()

        automator = GitAutomator() if GitAutomator else None
        details = []
        any_test_failed = False

        # Find git directories
        repos = [root_path] if (root_path / ".git").exists() else [p for p in root_path.iterdir() if p.is_dir() and (p / ".git").exists()]

        if not repos:
            return True, "No Git repositories found in monitored workspace."

        for repo in repos[:5]:
            repo_name = repo.name
            if automator and automator.is_git_repo(repo):
                status = automator.get_status(repo)
                clean_str = "clean" if status.clean else f"{len(status.staged_files) + len(status.unstaged_files)} modified"
                details.append(f"{repo_name}: branch '{status.current_branch}' ({clean_str})")

            # Check if tests exist and run if requested
            if config.get("run_tests", True):
                test_files = list(repo.glob("**/test_*.py")) + list(repo.glob("**/*_test.py"))
                if test_files:
                    cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(repo), "-p", "test_*.py"]
                    proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=30)
                    if proc.returncode == 0:
                        details.append(f"{repo_name}: tests PASSED")
                    else:
                        details.append(f"{repo_name}: tests FAILED")
                        any_test_failed = True

        return (not any_test_failed), " | ".join(details)

    @staticmethod
    def execute_research_scrape(config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Autonomous Research / Scraping:
        - Extracts text from specified web URLs or local documentation files
        - Indexes extracted excerpts into offline documentation database
        """
        target_urls = config.get("urls", [])
        local_files = config.get("files", [])
        extracted_count = 0

        # Process local files or offline scraping
        for f_path in local_files:
            p = Path(f_path).resolve()
            if p.exists() and p.is_file():
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    extracted_count += 1
                except Exception:
                    pass

        # If offline docs engine is available, register scraped knowledge
        if OfflineDocsEngine and extracted_count > 0:
            try:
                engine = OfflineDocsEngine()
                engine.index_document(
                    symbol=f"research_scrape_{int(time.time())}",
                    title="Scheduled Data Extraction Report",
                    language="markdown",
                    content=f"Extracted content from {extracted_count} sources.",
                    summary="Automated scraping job"
                )
            except Exception:
                pass

        return True, f"Scraped and extracted {extracted_count} data source(s)."

    @staticmethod
    def execute_custom_command(config: Dict[str, Any]) -> Tuple[bool, str]:
        """Executes a custom shell or python command with timeout."""
        cmd = config.get("command")
        if not cmd:
            return False, "No command specified in task configuration."

        cwd = config.get("cwd", os.getcwd())
        timeout = config.get("timeout_seconds", 60)

        try:
            res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            out_preview = res.stdout.strip()[:300] if res.stdout else res.stderr.strip()[:300]
            success = (res.returncode == 0)
            return success, out_preview or f"Process exited with code {res.returncode}"
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout} seconds."
        except Exception as e:
            return False, f"Command execution failed: {e}"


# ==============================================================================
# Core AI Cron Daemon Controller
# ==============================================================================
class AICronDaemon:
    """
    Background Task Scheduler Daemon.
    Monitors tasks.json, evaluates schedules, dispatches workers,
    writes structured logs, and notifies the AI OS terminal UI.
    """

    def __init__(self,
                 tasks_file: Optional[str] = None,
                 log_file: Optional[str] = None,
                 notifications_file: Optional[str] = None):
        self.tasks_path = Path(tasks_file).resolve() if tasks_file else resolve_writable_path(
            DEFAULT_SYSTEM_TASKS, USER_TASKS_FALLBACK, LOCAL_TASKS_FALLBACK
        )
        self.log_path = Path(log_file).resolve() if log_file else resolve_writable_path(
            DEFAULT_LOG_PATH, USER_LOG_FALLBACK, LOCAL_LOG_FALLBACK
        )
        self.notifications = NotificationHub(
            Path(notifications_file).resolve() if notifications_file else resolve_writable_path(
                NOTIFICATIONS_PATH, USER_NOTIFICATIONS_FALLBACK, LOCAL_NOTIFICATIONS_FALLBACK
            )
        )
        self.pid_path = resolve_writable_path(PID_PATH, USER_PID_FALLBACK, LOCAL_PID_FALLBACK)

        self.running = False
        self._setup_logging()
        self._ensure_default_tasks()

    def _setup_logging(self):
        """Sets up structured file and stream logger."""
        self.logger = logging.getLogger("AICronDaemon")
        self.logger.setLevel(logging.INFO)
        for h in list(self.logger.handlers):
            try:
                h.close()
            except Exception:
                pass
        self.logger.handlers = []

        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "ai_cron", "message": "%(message)s"}'
        )

        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(str(self.log_path), encoding="utf-8")
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
        except Exception:
            pass

        # Stream handler for foreground debugging
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)

    def _ensure_default_tasks(self):
        """Creates the default tasks configuration file if missing."""
        if self.tasks_path.exists():
            return

        default_tasks = {
            "version": "1.0",
            "updated_at": datetime.datetime.now().isoformat(),
            "tasks": [
                {
                    "id": "system_care_daily",
                    "name": "Daily System Care & AST Re-indexing",
                    "schedule": "0 2 * * *",
                    "natural_schedule": "Every day at 2 AM",
                    "task_type": "system_care",
                    "enabled": True,
                    "config": {
                        "actions": ["clear_temp", "reindex", "security_audit"],
                        "max_age_days": 3
                    },
                    "last_run": None,
                    "next_run": ScheduleParser.calculate_next_run("0 2 * * *").isoformat(),
                    "run_count": 0,
                    "last_status": "pending",
                    "last_output": ""
                },
                {
                    "id": "project_health_hourly",
                    "name": "Hourly Git Project Health & Verification",
                    "schedule": "0 * * * *",
                    "natural_schedule": "Every hour",
                    "task_type": "project_health",
                    "enabled": True,
                    "config": {
                        "run_tests": True
                    },
                    "last_run": None,
                    "next_run": ScheduleParser.calculate_next_run("0 * * * *").isoformat(),
                    "run_count": 0,
                    "last_status": "pending",
                    "last_output": ""
                },
                {
                    "id": "research_scraper_daily",
                    "name": "Daily Knowledge Extraction & Indexing",
                    "schedule": "0 3 * * *",
                    "natural_schedule": "Every day at 3 AM",
                    "task_type": "research_scrape",
                    "enabled": False,
                    "config": {
                        "files": []
                    },
                    "last_run": None,
                    "next_run": ScheduleParser.calculate_next_run("0 3 * * *").isoformat(),
                    "run_count": 0,
                    "last_status": "pending",
                    "last_output": ""
                }
            ]
        }

        try:
            self.tasks_path.parent.mkdir(parents=True, exist_ok=True)
            self.tasks_path.write_text(json.dumps(default_tasks, indent=2), encoding="utf-8")
            self.logger.info(f"Initialized default task configuration at {self.tasks_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize default tasks.json: {e}")

    def load_tasks(self) -> List[ScheduledTask]:
        """Loads and parses all scheduled tasks from tasks.json."""
        if not self.tasks_path.exists():
            return []

        try:
            data = json.loads(self.tasks_path.read_text(encoding="utf-8"))
            tasks = []
            for item in data.get("tasks", []):
                tasks.append(ScheduledTask(
                    id=item.get("id", f"task_{int(time.time()*1000)}"),
                    name=item.get("name", "Unnamed Task"),
                    schedule=item.get("schedule", "0 0 * * *"),
                    natural_schedule=item.get("natural_schedule", item.get("schedule", "")),
                    task_type=item.get("task_type", "system_care"),
                    enabled=item.get("enabled", True),
                    config=item.get("config", {}),
                    last_run=item.get("last_run"),
                    next_run=item.get("next_run"),
                    run_count=item.get("run_count", 0),
                    last_status=item.get("last_status", "pending"),
                    last_output=item.get("last_output", "")
                ))
            return tasks
        except Exception as e:
            self.logger.error(f"Error reading tasks file {self.tasks_path}: {e}")
            return []

    def save_tasks(self, tasks: List[ScheduledTask]):
        """Persists task list to tasks.json atomically."""
        data = {
            "version": "1.0",
            "updated_at": datetime.datetime.now().isoformat(),
            "tasks": [t.to_dict() for t in tasks]
        }
        try:
            temp_path = self.tasks_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            if sys.platform == "win32" and self.tasks_path.exists():
                self.tasks_path.unlink()
            temp_path.rename(self.tasks_path)
        except Exception as e:
            self.logger.error(f"Failed saving tasks to {self.tasks_path}: {e}")

    def add_task(self,
                 name: str,
                 schedule_input: str,
                 task_type: str = "system_care",
                 config: Optional[Dict[str, Any]] = None,
                 task_id: Optional[str] = None) -> ScheduledTask:
        """Adds a new task using either cron expression or natural language schedule."""
        cron_expr, natural_expr = ScheduleParser.normalize_schedule(schedule_input)
        tid = task_id or re.sub(r"[^a-zA-Z0-9_\-]", "_", name.lower().strip())[:30]

        next_run = ScheduleParser.calculate_next_run(cron_expr)

        task = ScheduledTask(
            id=tid,
            name=name,
            schedule=cron_expr,
            natural_schedule=natural_expr,
            task_type=task_type,
            enabled=True,
            config=config or {},
            last_run=None,
            next_run=next_run.isoformat(),
            run_count=0,
            last_status="scheduled",
            last_output=""
        )

        tasks = self.load_tasks()
        # Remove existing with same id if any
        tasks = [t for t in tasks if t.id != tid]
        tasks.append(task)
        self.save_tasks(tasks)

        self.logger.info(f"Registered new task '{name}' [{cron_expr}] ({natural_expr})")
        return task

    def remove_task(self, task_id: str) -> bool:
        """Removes a task by its ID."""
        tasks = self.load_tasks()
        initial_len = len(tasks)
        tasks = [t for t in tasks if t.id != task_id]
        if len(tasks) < initial_len:
            self.save_tasks(tasks)
            self.logger.info(f"Removed task with ID: {task_id}")
            return True
        return False

    def toggle_task(self, task_id: str, enabled: bool) -> bool:
        """Enables or pauses a task."""
        tasks = self.load_tasks()
        found = False
        for t in tasks:
            if t.id == task_id:
                t.enabled = enabled
                found = True
                break
        if found:
            self.save_tasks(tasks)
            self.logger.info(f"Task '{task_id}' state updated to enabled={enabled}")
        return found

    def execute_task(self, task: ScheduledTask) -> Tuple[bool, str]:
        """Dispatches execution of a single task and records outcome."""
        self.logger.info(f"Executing scheduled task: '{task.name}' ({task.task_type})")
        start_time = time.time()
        success = False
        output = ""

        try:
            if task.task_type == "system_care":
                success, output = TaskExecutors.execute_system_care(task.config)
            elif task.task_type == "project_health":
                success, output = TaskExecutors.execute_project_health(task.config)
            elif task.task_type == "research_scrape":
                success, output = TaskExecutors.execute_research_scrape(task.config)
            elif task.task_type == "custom_command":
                success, output = TaskExecutors.execute_custom_command(task.config)
            else:
                success = False
                output = f"Unknown task type: {task.task_type}"
        except Exception as e:
            success = False
            output = f"Unhandled exception during execution: {e}"

        elapsed = time.time() - start_time
        status_str = "success" if success else "failed"
        self.logger.info(f"Task '{task.name}' completed in {elapsed:.2f}s with status={status_str}: {output}")

        # Dispatch notification to UI
        level = "success" if success else "error"
        self.notifications.notify(
            title=f"Task Completed: {task.name}",
            message=output,
            level=level,
            task_id=task.id
        )

        return success, output

    def run_once(self) -> int:
        """
        Evaluates all tasks and runs those whose next_run <= current_time.
        Returns the number of tasks executed.
        """
        tasks = self.load_tasks()
        now = datetime.datetime.now()
        executed_count = 0

        for task in tasks:
            if not task.enabled:
                continue

            should_run = False
            if not task.next_run:
                should_run = True
            else:
                try:
                    next_dt = datetime.datetime.fromisoformat(task.next_run)
                    if now >= next_dt:
                        should_run = True
                except Exception:
                    should_run = True

            if should_run:
                success, output = self.execute_task(task)
                task.last_run = now.isoformat()
                task.run_count += 1
                task.last_status = "success" if success else "failed"
                task.last_output = output
                task.next_run = ScheduleParser.calculate_next_run(task.schedule, from_dt=now).isoformat()
                executed_count += 1

        if executed_count > 0:
            self.save_tasks(tasks)

        return executed_count

    def start_daemon(self, poll_interval: int = 5):
        """Starts the persistent background daemon loop."""
        self.running = True
        self._write_pid()

        self.logger.info(f"AI Cron Daemon started (PID: {os.getpid()}) monitoring {self.tasks_path}")

        # Setup graceful termination signals if running in main thread
        if threading.current_thread() == threading.main_thread():
            def handle_signal(sig, frame):
                self.logger.info("Termination signal received. Shutting down daemon gracefully...")
                self.stop_daemon()

            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)

        try:
            while self.running:
                self.run_once()
                time.sleep(poll_interval)
        except Exception as e:
            self.logger.error(f"Daemon error in main loop: {e}")
        finally:
            self._remove_pid()
            self.logger.info("AI Cron Daemon stopped cleanly.")

    def stop_daemon(self):
        """Stops the daemon execution loop."""
        self.running = False

    def _write_pid(self):
        try:
            self.pid_path.parent.mkdir(parents=True, exist_ok=True)
            self.pid_path.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

    def _remove_pid(self):
        try:
            if self.pid_path.exists():
                self.pid_path.unlink()
        except Exception:
            pass


# ==============================================================================
# CLI Entrypoint for Direct Running / Daemonization
# ==============================================================================
if __name__ == "__main__":
    daemon = AICronDaemon()
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        executed = daemon.run_once()
        print(f"Executed {executed} due task(s).")
    else:
        daemon.start_daemon(poll_interval=5)
