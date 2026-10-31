#!/usr/bin/env python3
"""
ai_shell_agent.py - Core Natural Language CLI Agent & Command Interpreter for AI OS
Author: Lead Systems Programmer specializing in AI Agents and IPC

Serves as the default interactive shell on TTY1 / Terminal, replacing or wrapping
traditional Bash/Zsh with seamless Natural Language understanding, local/remote AI
routing, automated system context injection, and strict safety guardrails.
"""

import os
import sys
import re
import json
import shutil
import platform
import subprocess
import time
from typing import Dict, List, Optional, Any, Tuple

# Try loading requests with urllib fallback
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error

# Try loading PyYAML with fallback
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Try importing readline for shell history
try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False

# Import local subsystems (DependencyResolver, SandboxRunner, GUIExpander)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from dependency_resolver import DependencyResolver
except ImportError:
    DependencyResolver = None

try:
    from sandbox_runner import SandboxRunner
except ImportError:
    SandboxRunner = None

try:
    from gui_expander import GUIExpander
except ImportError:
    GUIExpander = None

try:
    from project_architect import ProjectArchitect
except ImportError:
    ProjectArchitect = None

try:
    from self_healer import SelfHealer
except ImportError:
    SelfHealer = None

try:
    from system_indexer import SystemIndexer
except ImportError:
    SystemIndexer = None

try:
    from hardware_manager import HardwareManager
except ImportError:
    HardwareManager = None

try:
    from model_router import ModelRouter
except ImportError:
    ModelRouter = None

try:
    from security_daemon import SecurityDaemon
except ImportError:
    SecurityDaemon = None

try:
    from ai_terminal_ui import AITerminalUI
except ImportError:
    AITerminalUI = None

try:
    from personal_memory import PersonalMemoryEngine
except ImportError:
    PersonalMemoryEngine = None

try:
    from system_updater import SystemUpdater
except ImportError:
    SystemUpdater = None

try:
    from multimodal_gateway import MultimodalGateway
except ImportError:
    MultimodalGateway = None

try:
    from git_automator import GitAutomator
except ImportError:
    GitAutomator = None

try:
    from offline_docs_engine import OfflineDocsEngine
except ImportError:
    OfflineDocsEngine = None

try:
    from plugin_manager import PluginManager
except ImportError:
    PluginManager = None

try:
    from ai_cron_daemon import AICronDaemon
except ImportError:
    AICronDaemon = None


# ==============================================================================
# ANSI Color Palette & UI Utilities
# ==============================================================================
class TerminalUI:
    CYAN = "\033[1;36m"
    BLUE = "\033[1;34m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    RED = "\033[1;31m"
    MAGENTA = "\033[1;35m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @classmethod
    def banner(cls):
        return f"""{cls.CYAN}
   ▄████████  ▄█        ▄████████ 
  ███    ███ ███       ███    ███ 
  ███    ███ ███▌      ███    ███   {cls.MAGENTA}[ AI OPERATING SYSTEM ]{cls.CYAN}
  ███    ███ ███▌     ▄███▄▄▄▄██▀   {cls.DIM}Next-Gen Autonomous Agentic Shell{cls.CYAN}
▀███████████ ███▌    ▀▀███▀▀▀▀▀     {cls.GREEN}Kernel: Alpine Minirootfs TTY{cls.CYAN}
  ███    ███ ███       ███          {cls.YELLOW}Ollama LLM + Auto-Healing Shell{cls.CYAN}
  ███    ███ ███       ███        
  ███    █▀  █▀        ███        
{cls.RESET}"""

    @classmethod
    def print_info(cls, msg: str):
        print(f"{cls.BLUE}[*]{cls.RESET} {msg}")

    @classmethod
    def print_success(cls, msg: str):
        print(f"{cls.GREEN}[OK]{cls.RESET} {msg}")

    @classmethod
    def print_warn(cls, msg: str):
        print(f"{cls.YELLOW}[!]{cls.RESET} {msg}")

    @classmethod
    def print_error(cls, msg: str):
        print(f"{cls.RED}[✗]{cls.RESET} {msg}")


# ==============================================================================
# Configuration Loader
# ==============================================================================
class ConfigManager:
    """Loads config.yaml with fallback defaults."""
    DEFAULT_CONFIG = {
        "system": {
            "hostname": "ai-os",
            "workspace_dir": "/workspace",
        },
        "ai_routing": {
            "local": {
                "enabled": True,
                "provider": "ollama",
                "endpoint": "http://127.0.0.1:11434",
                "model": "llama3.2:3b",
                "timeout_seconds": 45,
                "temperature": 0.2
            },
            "remote": {
                "enabled": True,
                "provider": "openai",
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-4o-mini",
                "timeout_seconds": 30,
                "temperature": 0.2
            }
        },
        "safety": {
            "strict_mode": True,
            "destructive_patterns": [
                r"^rm\s+(-[a-zA-Z]*r[a-zA-Z]*f*|-f[a-zA-Z]*r[a-zA-Z]*)\s+.*(/|\*).*",
                r".*mkfs(\.[a-z0-9]+)?\s+.*",
                r".*dd\s+.*of=/dev/.*",
                r".*fdisk\s+.*",
                r".*parted\s+.*",
                r".*chmod\s+(-R\s+)?777\s+.*",
                r".*>\s*/dev/(sd[a-z]|nvme[0-9]n[0-9]|hd[a-z]).*",
                r".*(shutdown|poweroff|reboot|init\s+0).*",
                r".*kill\s+-9\s+1\b.*"
            ]
        },
        "dependency_resolver": {
            "auto_heal": True,
            "max_healing_retries": 2,
            "log_file": "/var/log/ai_deps.log"
        }
    }

    @classmethod
    def load(cls) -> Dict[str, Any]:
        search_paths = [
            "/etc/ai_os/config.yaml",
            os.path.join(SCRIPT_DIR, "..", "configs", "config.yaml"),
            os.path.join(SCRIPT_DIR, "config.yaml"),
            os.path.expanduser("~/.config/ai_os/config.yaml")
        ]

        for p in search_paths:
            if os.path.exists(p):
                try:
                    if HAS_YAML:
                        with open(p, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                            if isinstance(data, dict):
                                return data
                except Exception:
                    pass
        return cls.DEFAULT_CONFIG


# ==============================================================================
# System Context Extractor
# ==============================================================================
class SystemContextEngine:
    """Collects real-time OS state, hardware, memory, and active processes."""

    @staticmethod
    def get_context_snapshot() -> Dict[str, Any]:
        snapshot = {
            "cwd": os.getcwd(),
            "user": os.getenv("USER", "root"),
            "hostname": platform.node() or "ai-os",
            "kernel": platform.release(),
            "memory": SystemContextEngine._get_memory_summary(),
            "disk": SystemContextEngine._get_disk_summary(),
            "processes": SystemContextEngine._get_top_processes(),
            "hardware": SystemContextEngine._get_hardware_summary(),
            "git": SystemContextEngine._get_git_info()
        }
        return snapshot

    @staticmethod
    def _get_memory_summary() -> str:
        # Check /proc/meminfo or free
        if os.path.exists("/proc/meminfo"):
            try:
                mem = {}
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            mem[parts[0].strip()] = parts[1].strip()
                total = mem.get("MemTotal", "N/A")
                avail = mem.get("MemAvailable", mem.get("MemFree", "N/A"))
                return f"Total: {total}, Available: {avail}"
            except Exception:
                pass
        return "Unknown"

    @staticmethod
    def _get_disk_summary() -> str:
        try:
            cwd = os.getcwd()
            total, used, free = shutil.disk_usage(cwd)
            return f"Mount: {cwd} | Free: {free // (1024*1024)}MB / {total // (1024*1024)}MB"
        except Exception:
            return "Unknown"

    @staticmethod
    def _get_top_processes() -> List[str]:
        procs = []
        try:
            if shutil.which("ps"):
                res = subprocess.run(["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"],
                                     capture_output=True, text=True, timeout=2)
                if res.returncode == 0:
                    lines = [line.strip() for line in res.stdout.strip().splitlines()]
                    procs = lines[:8]  # Top 8 processes
            else:
                procs = ["ps utility not available"]
        except Exception:
            procs = ["Process inspection timeout"]
        return procs

    @staticmethod
    def _get_hardware_summary() -> Dict[str, str]:
        info = {
            "arch": platform.machine(),
            "cpu_cores": str(os.cpu_count() or 1)
        }
        # Check GPU / PCI
        if os.path.exists("/dev/dri"):
            info["gpu_drm"] = "Present (/dev/dri available)"
        return info

    @staticmethod
    def _get_git_info() -> Optional[str]:
        try:
            if shutil.which("git"):
                res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                     capture_output=True, text=True, timeout=2)
                if res.returncode == 0:
                    return f"Branch: {res.stdout.strip()}"
        except Exception:
            pass
        return None

    @classmethod
    def format_for_prompt(cls, user_query: Optional[str] = None) -> str:
        snap = cls.get_context_snapshot()
        ctx_str = (
            f"[SYSTEM CONTEXT]\n"
            f"- CWD: {snap['cwd']}\n"
            f"- User: {snap['user']} @ {snap['hostname']} (Kernel: {snap['kernel']}, Arch: {snap['hardware']['arch']}, CPU Cores: {snap['hardware']['cpu_cores']})\n"
            f"- Memory: {snap['memory']}\n"
            f"- Disk: {snap['disk']}\n"
        )
        if snap['git']:
            ctx_str += f"- Git: {snap['git']}\n"
        ctx_str += f"- Top Active Processes:\n  " + "\n  ".join(snap['processes'][:5]) + "\n"

        if PersonalMemoryEngine:
            try:
                mem_engine = PersonalMemoryEngine()
                mem_ctx = mem_engine.get_system_prompt_context(user_query or snap['cwd'])
                if mem_ctx:
                    ctx_str += f"\n{mem_ctx}\n"
            except Exception:
                pass

        return ctx_str


# ==============================================================================
# Local & Remote AI Router
# ==============================================================================
class AIRouter:
    """Routes prompts to local Ollama with graceful fallback to Remote LLM."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.local_cfg = config.get("ai_routing", {}).get("local", {})
        self.remote_cfg = config.get("ai_routing", {}).get("remote", {})
        self.active_provider = "local"

    def is_local_online(self) -> bool:
        """Verifies local Ollama server connectivity."""
        if not self.local_cfg.get("enabled", True):
            return False

        endpoint = self.local_cfg.get("endpoint", "http://127.0.0.1:11434").rstrip("/")
        url = f"{endpoint}/api/tags"

        try:
            if HAS_REQUESTS:
                res = requests.get(url, timeout=2)
                return res.status_code == 200
            else:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=2) as resp:
                    return resp.status == 200
        except Exception:
            return False

    def query(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str]:
        """
        Queries Ollama first or delegates to ModelRouter if available.
        Returns: (success, response_text)
        """
        if ModelRouter:
            try:
                router = ModelRouter(config=self.config)
                resp = router.generate(prompt=user_prompt, system_context=system_prompt)
                if resp.fallback_triggered and resp.fallback_reason:
                    TerminalUI.print_warn(f"Cloud fallback triggered: {resp.fallback_reason}")
                self.active_provider = f"{resp.provider} ({resp.model})"
                return True, resp.content
            except Exception as e:
                TerminalUI.print_warn(f"ModelRouter delegation failed: {e}. Falling back to internal router.")

        # 1. Attempt Local Ollama
        if self.is_local_online():
            self.active_provider = f"local ({self.local_cfg.get('model', 'ollama')})"
            ok, text = self._query_ollama(system_prompt, user_prompt)
            if ok:
                return True, text
            TerminalUI.print_warn("Local LLM request failed or timed out. Checking remote fallback...")

        # 2. Check Remote Fallback
        remote_key = os.getenv(self.remote_cfg.get("api_key_env", "OPENAI_API_KEY"), "")
        if self.remote_cfg.get("enabled", True) and remote_key:
            TerminalUI.print_info(f"Failing over to remote AI ({self.remote_cfg.get('model', 'remote')})...")
            self.active_provider = f"remote ({self.remote_cfg.get('model')})"
            return self._query_remote(system_prompt, user_prompt, remote_key)

        return False, (
            "Local Ollama daemon is unreachable at 127.0.0.1:11434 and no remote API key (OPENAI_API_KEY) was found.\n"
            "Tip: Ensure the 'ai-agent' OpenRC service is running: `rc-service ai-agent status`."
        )

    def _query_ollama(self, system_prompt: str, user_prompt: str) -> Tuple[bool, str]:
        endpoint = self.local_cfg.get("endpoint", "http://127.0.0.1:11434").rstrip("/")
        url = f"{endpoint}/api/chat"
        payload = {
            "model": self.local_cfg.get("model", "llama3.2:3b"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "options": {
                "temperature": self.local_cfg.get("temperature", 0.2)
            },
            "stream": False
        }

        try:
            if HAS_REQUESTS:
                res = requests.post(url, json=payload, timeout=self.local_cfg.get("timeout_seconds", 45))
                if res.status_code == 200:
                    data = res.json()
                    return True, data.get("message", {}).get("content", "")
            else:
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=self.local_cfg.get("timeout_seconds", 45)) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    return True, resp_json.get("message", {}).get("content", "")
        except Exception as e:
            return False, str(e)
        return False, "Unknown Ollama response error."

    def _query_remote(self, system_prompt: str, user_prompt: str, api_key: str) -> Tuple[bool, str]:
        url = self.remote_cfg.get("endpoint", "https://api.openai.com/v1/chat/completions")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.remote_cfg.get("model", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.remote_cfg.get("temperature", 0.2)
        }

        try:
            if HAS_REQUESTS:
                res = requests.post(url, headers=headers, json=payload, timeout=self.remote_cfg.get("timeout_seconds", 30))
                if res.status_code == 200:
                    data = res.json()
                    return True, data["choices"][0]["message"]["content"]
                return False, f"Remote API HTTP {res.status_code}: {res.text}"
            else:
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data_bytes, headers=headers)
                with urllib.request.urlopen(req, timeout=self.remote_cfg.get("timeout_seconds", 30)) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    return True, resp_json["choices"][0]["message"]["content"]
        except Exception as e:
            return False, f"Remote API Exception: {e}"


# ==============================================================================
# Command Parser & Structured Action Generator
# ==============================================================================
SYSTEM_AGENT_PROMPT = """You are the Core Agent and Command Interpreter for AI OS.
Your job is to translate user natural language requests and goals into actionable system commands.

You MUST respond with a valid JSON array of action objects. Do NOT output extra narrative outside the JSON array.
Valid actions:
1. Shell command execution:
   {"action": "execute_shell", "command": "<shell command>", "description": "<brief description>"}
2. File creation/modification:
   {"action": "create_file", "path": "<relative or absolute filepath>", "content": "<file content>", "description": "<description>"}
3. Dependency installation:
   {"action": "install_dep", "packages": ["<package_name>"], "package_manager": "apk|pip|npm|cargo", "description": "<description>"}
4. Informational or clarifying response:
   {"action": "message", "content": "<message to user>"}

Examples:
User: "Build a full REST API for user authentication in Python"
Response:
[
  {"action": "install_dep", "packages": ["fastapi", "uvicorn", "pyjwt", "passlib", "bcrypt"], "package_manager": "pip", "description": "Install required authentication dependencies"},
  {"action": "create_file", "path": "auth_api.py", "content": "# FastAPI Auth API implementation...", "description": "Create REST API service script"},
  {"action": "execute_shell", "command": "python -m py_compile auth_api.py", "description": "Verify python syntax"},
  {"action": "message", "content": "REST API for user authentication generated in auth_api.py with FastAPI and PyJWT."}
]
"""

class ActionParser:
    """Extracts structured JSON action arrays from LLM responses."""

    @staticmethod
    def parse_actions(llm_output: str) -> List[Dict[str, Any]]:
        cleaned = llm_output.strip()

        # Extract markdown code fence if present
        json_fence_match = re.search(r"```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```", cleaned, re.DOTALL)
        if json_fence_match:
            cleaned = json_fence_match.group(1).strip()
        else:
            # Fallback regex search for JSON array
            bracket_match = re.search(r"(\[\s*\{.*\}\s*\])", cleaned, re.DOTALL)
            if bracket_match:
                cleaned = bracket_match.group(1).strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except Exception:
            pass

        # Fallback if model just returned text
        return [{"action": "message", "content": llm_output}]


# ==============================================================================
# Safety Guardrail & Approval Engine
# ==============================================================================
class SafetyGuardrail:
    """Detects dangerous/destructive commands and enforces interactive user confirmation."""

    def __init__(self, destructive_patterns: List[str]):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in destructive_patterns]

    def is_destructive(self, command: str) -> Tuple[bool, str]:
        cmd_stripped = command.strip()
        for pat in self.patterns:
            if pat.search(cmd_stripped):
                return True, f"Command matched dangerous system pattern: '{pat.pattern}'"

        # Explicit root checks
        if re.search(r"\brm\s+-[a-zA-Z]*r.*(/|/\*|/home|/workspace|/etc)", cmd_stripped):
            return True, "Destructive recursive deletion targeting critical path."

        return False, ""

    def request_approval(self, command: str, reason: str) -> bool:
        """Prompts user on TTY for explicit confirmation."""
        print(f"\n{TerminalUI.RED}{TerminalUI.BOLD}[!] DANGER: POTENTIALLY DESTRUCTIVE ACTION DETECTED{TerminalUI.RESET}")
        print(f"  {TerminalUI.YELLOW}Command:{TerminalUI.RESET} {command}")
        print(f"  {TerminalUI.YELLOW}Reason:{TerminalUI.RESET}  {reason}")
        try:
            choice = input(f"{TerminalUI.RED}Are you sure you want to proceed? [y/N]: {TerminalUI.RESET}").strip().lower()
            return choice in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            print()
            return False


# ==============================================================================
# Core Shell Agent
# ==============================================================================
class AIShellAgent:
    """The central interactive CLI shell agent for AI OS."""

    def __init__(self):
        self.config = ConfigManager.load()
        self.router = AIRouter(self.config)
        self.safety = SafetyGuardrail(self.config.get("safety", {}).get("destructive_patterns", []))
        self.dep_resolver = DependencyResolver(
            log_path=self.config.get("dependency_resolver", {}).get("log_file", "/var/log/ai_deps.log"),
            max_retries=self.config.get("dependency_resolver", {}).get("max_healing_retries", 2)
        ) if DependencyResolver else None
        self.sandbox = SandboxRunner() if SandboxRunner else None
        self.gui_expander = GUIExpander() if GUIExpander else None
        self.unified_router = ModelRouter(self.config) if ModelRouter else None
        self.architect = ProjectArchitect(router=self.router, resolver=self.dep_resolver, sandbox=self.sandbox) if ProjectArchitect else None
        self.healer = SelfHealer(router=self.router, sandbox=self.sandbox) if SelfHealer else None
        self.indexer = SystemIndexer() if SystemIndexer else None
        self.hw_manager = HardwareManager() if HardwareManager else None
        self.security_daemon = SecurityDaemon() if SecurityDaemon else None
        self.terminal_ui = AITerminalUI() if AITerminalUI else None
        self.memory = PersonalMemoryEngine() if PersonalMemoryEngine else None
        self.updater = SystemUpdater() if SystemUpdater else None
        self.multimodal = MultimodalGateway() if MultimodalGateway else None
        self.git_automator = GitAutomator(router=self.router) if GitAutomator else None
        self.docs_engine = OfflineDocsEngine() if OfflineDocsEngine else None
        self.plugin_manager = PluginManager() if PluginManager else None
        self.cron_daemon = AICronDaemon() if AICronDaemon else None

        self.history_file = os.path.expanduser("~/.ai_shell_history")
        self._init_history()

    def _init_history(self):
        if HAS_READLINE:
            try:
                if os.path.exists(self.history_file):
                    readline.read_history_file(self.history_file)
                readline.set_history_length(1000)
            except Exception:
                pass

    def _save_history(self):
        if HAS_READLINE:
            try:
                readline.write_history_file(self.history_file)
            except Exception:
                pass

    def is_standard_shell_command(self, user_input: str) -> bool:
        """Determines if the input is a direct POSIX command or natural language."""
        tokens = user_input.strip().split()
        if not tokens:
            return False

        first = tokens[0]

        # Explicit escape to standard shell
        if user_input.startswith("!"):
            return True

        # Common shell builtins and core utilities
        shell_builtins = {
            "cd", "pwd", "ls", "ll", "la", "cat", "echo", "grep", "find",
            "chmod", "chown", "mkdir", "rmdir", "cp", "mv", "rm", "touch",
            "ps", "kill", "top", "htop", "free", "df", "du", "uname",
            "whoami", "id", "su", "sudo", "apk", "apt", "pacman", "pip", "pip3",
            "python", "python3", "node", "npm", "cargo", "git", "docker",
            "curl", "wget", "tar", "gzip", "unzip", "export", "alias",
            "source", "history", "clear", "exit", "reboot", "poweroff",
            "rc-service", "rc-status", "openrc", "ollama", "systemctl"
        }

        if first in shell_builtins:
            return True

        # Check if contains shell operators (pipes, redirection)
        if any(op in user_input for op in ["|", ">", ">>", "<", ";", "&&", "||"]):
            return True

        # Check if first token exists as binary in PATH
        if shutil.which(first):
            # If it's a short command invocation, treat as shell
            if len(tokens) <= 5 and not any(w in user_input.lower() for w in ["build", "create", "how", "why", "write", "make a", "implement"]):
                return True

        return False

    def execute_native_command(self, cmd_str: str) -> int:
        """Executes a standard shell command with auto-healing and cd support."""
        cmd_str = cmd_str.strip()
        if cmd_str.startswith("!"):
            cmd_str = cmd_str[1:].strip()

        # Handle 'cd' internally to maintain process state
        if cmd_str.startswith("cd"):
            parts = cmd_str.split(maxsplit=1)
            target_dir = parts[1] if len(parts) > 1 else os.path.expanduser("~")
            try:
                target_dir = os.path.expanduser(os.path.expandvars(target_dir))
                os.chdir(target_dir)
                return 0
            except Exception as e:
                TerminalUI.print_error(f"cd: {e}")
                return 1

        # Check safety guardrail
        is_bad, reason = self.safety.is_destructive(cmd_str)
        if is_bad:
            approved = self.safety.request_approval(cmd_str, reason)
            if not approved:
                TerminalUI.print_warn("Execution aborted by user.")
                return 130

        # Execute with Auto-Healing Dependency Resolver if available
        if self.dep_resolver and self.config.get("dependency_resolver", {}).get("auto_heal", True):
            code, stdout_out, stderr_out = self.dep_resolver.run_with_autoheal(cmd_str)
            if stdout_out:
                sys.stdout.write(stdout_out)
                sys.stdout.flush()
            if stderr_out:
                sys.stderr.write(stderr_out)
                sys.stderr.flush()
            return code
        else:
            try:
                return subprocess.run(cmd_str, shell=True).returncode
            except Exception as e:
                TerminalUI.print_error(f"Command failed: {e}")
                return 1

    def handle_natural_language(self, prompt: str):
        """Processes natural language request via AI Router & executes actions."""
        # 1. Check for unread background task notifications
        if self.cron_daemon:
            unread = self.cron_daemon.notifications.get_unread()
            if unread:
                for n in unread:
                    print(f"\n{TerminalUI.YELLOW}[Task Notification] {n.get('title')}:{TerminalUI.RESET} {n.get('message')}\n")
                self.cron_daemon.notifications.mark_all_read()

        # 2. Check if prompt matches an active plugin trigger
        if self.plugin_manager:
            match = self.plugin_manager.match_intent(prompt)
            if match:
                plugin, trigger, confidence = match
                TerminalUI.print_info(f"Trigger matched active plugin: '{plugin.manifest.name}' ({confidence*100:.0f}% confidence)")
                res = self.plugin_manager.execute_matching_plugin(prompt)
                if res:
                    print(f"\n{TerminalUI.CYAN}[AI OS Plugin: {plugin.manifest.name}]:{TerminalUI.RESET}\n{res.content}\n")
                    return

        TerminalUI.print_info(f"Analyzing request with {self.router.active_provider}...")

        # Inject real-time system context
        context_str = SystemContextEngine.format_for_prompt()
        full_system_prompt = f"{SYSTEM_AGENT_PROMPT}\n\n{context_str}"

        start_time = time.time()
        success, response_text = self.router.query(full_system_prompt, prompt)
        elapsed = time.time() - start_time

        if not success:
            TerminalUI.print_error(response_text)
            return

        # Parse actions
        actions = ActionParser.parse_actions(response_text)
        TerminalUI.print_success(f"Generated plan ({len(actions)} actions in {elapsed:.2f}s):")

        for idx, act in enumerate(actions, 1):
            action_type = act.get("action", "message")
            desc = act.get("description", "")

            if action_type == "message":
                print(f"\n{TerminalUI.CYAN}[AI OS]:{TerminalUI.RESET} {act.get('content', '')}\n")

            elif action_type == "install_dep":
                packages = act.get("packages", [])
                pkg_mgr = act.get("package_manager", "pip")
                print(f"{TerminalUI.BLUE}Action {idx}:{TerminalUI.RESET} Install [{pkg_mgr}] dependencies: {TerminalUI.BOLD}{', '.join(packages)}{TerminalUI.RESET} ({desc})")

                if self.dep_resolver:
                    for pkg in packages:
                        if pkg_mgr == "pip":
                            self.dep_resolver.adapter.install_pip_package(pkg)
                        elif pkg_mgr == "apk":
                            self.dep_resolver.adapter.install_system_package(pkg)
                        elif pkg_mgr == "npm":
                            self.dep_resolver.adapter.install_npm_package(pkg)
                        elif pkg_mgr == "cargo":
                            self.dep_resolver.adapter.install_cargo_package(pkg)
                else:
                    self.execute_native_command(f"{pkg_mgr} install {' '.join(packages)}")

            elif action_type == "create_file":
                file_path = act.get("path", "")
                content = act.get("content", "")
                print(f"{TerminalUI.BLUE}Action {idx}:{TerminalUI.RESET} Create file {TerminalUI.GREEN}{file_path}{TerminalUI.RESET} ({desc})")

                try:
                    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    TerminalUI.print_success(f"Wrote {len(content)} bytes to {file_path}")
                except Exception as e:
                    TerminalUI.print_error(f"Failed to create file {file_path}: {e}")

            elif action_type == "execute_shell":
                cmd = act.get("command", "")
                print(f"{TerminalUI.BLUE}Action {idx}:{TerminalUI.RESET} Executing: {TerminalUI.YELLOW}{cmd}{TerminalUI.RESET} ({desc})")
                self.execute_native_command(cmd)

    def print_help(self):
        print(f"""
{TerminalUI.BOLD}AI OS Shell Agent Commands:{TerminalUI.RESET}
  {TerminalUI.CYAN}<natural language>{TerminalUI.RESET}  - Submit instructions (e.g. 'Build a REST API in Python', 'Give me GUI')
  {TerminalUI.CYAN}<linux command>{TerminalUI.RESET}     - Standard POSIX execution (e.g. 'ls -la', 'git status', 'docker ps')
  {TerminalUI.CYAN}!<linux command>{TerminalUI.RESET}    - Explicitly force execution as a raw shell command
  {TerminalUI.CYAN}project <prompt>{TerminalUI.RESET}     - Architect & scaffold full software project from prompt
  {TerminalUI.CYAN}heal <project_dir>{TerminalUI.RESET}   - Autonomous self-debugging & iterative patch loop
  {TerminalUI.CYAN}index --scan <dir>{TerminalUI.RESET}   - Index directory tree & AST symbols into SQLite
  {TerminalUI.CYAN}symbol <name>{TerminalUI.RESET}         - Fast AST lookup for functions/classes
  {TerminalUI.CYAN}search <term>{TerminalUI.RESET}         - Token-efficient code snippet search
  {TerminalUI.CYAN}tree <dir>{TerminalUI.RESET}           - Clean ASCII directory hierarchy tree
  {TerminalUI.CYAN}hw / hardware{TerminalUI.RESET}       - Inspect CPU/GPU acceleration metrics & tier
  {TerminalUI.CYAN}route{TerminalUI.RESET}               - Inspect hybrid AI routing & network connectivity status
  {TerminalUI.CYAN}gui --enable / on{TerminalUI.RESET}  - Zero-to-GUI: Launch Sway/Wayland Graphical Desktop
  {TerminalUI.CYAN}gui --disable / off{TerminalUI.RESET} - Exit GUI and revert to low-resource TTY mode
  {TerminalUI.CYAN}sandbox <dir> [cmd]{TerminalUI.RESET} - Execute command inside isolated Docker/Podman container
  {TerminalUI.CYAN}sandbox-test <dir>{TerminalUI.RESET}  - Run automated test suite inside ephemeral container
  {TerminalUI.CYAN}context{TerminalUI.RESET}            - Display real-time system context injected into the AI
  {TerminalUI.CYAN}status{TerminalUI.RESET}             - Display AI engine, Docker, and persistent storage states
  {TerminalUI.CYAN}config{TerminalUI.RESET}             - Show active AI models and endpoints
  {TerminalUI.CYAN}help{TerminalUI.RESET}               - Show this help menu
  {TerminalUI.CYAN}exit / logout{TerminalUI.RESET}      - Exit shell session
""")

    def repl(self):
        """Main Read-Eval-Print Loop for the shell."""
        print(TerminalUI.banner())
        TerminalUI.print_success("AI OS Core Agent Shell initialized.")
        TerminalUI.print_info(f"Default Provider: {self.router.local_cfg.get('model')} (Local) | Auto-Healing: Active")
        print(f"{TerminalUI.DIM}Type standard shell commands or natural language prompts. Type 'help' for options.{TerminalUI.RESET}\n")

        while True:
            try:
                cwd = os.getcwd()
                user = os.getenv("USER", "root")
                prompt_str = f"{TerminalUI.GREEN}{user}@ai-os{TerminalUI.RESET}:{TerminalUI.BLUE}{cwd}{TerminalUI.RESET} ⚡ "
                line = input(prompt_str).strip()

                if not line:
                    continue

                if line.lower() in ("exit", "logout"):
                    self._save_history()
                    print(f"{TerminalUI.YELLOW}Closing AI OS session...{TerminalUI.RESET}")
                    break

                elif line.lower() == "help":
                    self.print_help()

                elif line.lower() == "context":
                    print(f"\n{SystemContextEngine.format_for_prompt()}")

                elif line.lower() == "status":
                    self.execute_native_command("rc-status default 2>/dev/null || true")
                    print()
                    self.execute_native_command("df -h / /workspace 2>/dev/null || df -h")

                elif line.lower() == "config":
                    print(json.dumps(self.config, indent=2))

                # Check Hybrid AI Router Status
                elif line.lower() in ("route", "router") and self.unified_router:
                    print(json.dumps(self.unified_router.get_system_status(), indent=2))

                # Check Hardware Diagnostics Command
                elif line.lower() in ("hw", "hardware") and self.hw_manager:
                    metrics = self.hw_manager.get_system_metrics()
                    print(json.dumps(metrics, indent=2))

                # Check System Indexer Commands
                elif line.startswith("index --scan ") and self.indexer:
                    target = line.split(maxsplit=2)[2]
                    res = self.indexer.scan_directory(target)
                    print(f"[OK] Indexed {res['files_indexed']} files and {res['symbols_indexed']} symbols in {res['duration_sec']}s")

                elif line.startswith("symbol ") and self.indexer:
                    s_name = line.split(maxsplit=1)[1]
                    syms = self.indexer.find_symbol(s_name)
                    print(f"Found {len(syms)} symbol(s):")
                    for s in syms:
                        print(f"  [{s['symbol_type'].upper()}] {s['signature']} ({s['filename']}:{s['line_number']})")

                elif line.startswith("search ") and self.indexer:
                    q = line.split(maxsplit=1)[1]
                    matches = self.indexer.search_code(q)
                    print(f"Found {len(matches)} match(es):")
                    for m in matches:
                        print(f"  {m['filename']}:{m['line_number']} -> {m['snippet']}")

                elif line.startswith("tree ") and self.indexer:
                    t_dir = line.split(maxsplit=1)[1]
                    print(self.indexer.get_project_tree(t_dir))

                # Check Project Architect Command
                elif line.startswith("project ") and self.architect:
                    prompt = line.split(maxsplit=1)[1]
                    res = self.architect.build_project(prompt)
                    print(json.dumps(res, indent=2))

                # Check Self-Healer Command
                elif line.startswith("heal ") and self.healer:
                    parts = line.split(maxsplit=2)
                    target_dir = parts[1]
                    t_cmd = parts[2] if len(parts) > 2 else None
                    summary = self.healer.auto_heal_project(target_dir, custom_test_cmd=t_cmd)
                    print(summary.to_json())

                # Check GUI Triggers
                elif self.gui_expander and self.gui_expander.is_gui_trigger(line):
                    self.gui_expander.enable_gui()

                elif self.gui_expander and self.gui_expander.is_gui_disable_trigger(line):
                    self.gui_expander.disable_gui()

                # Check Sandbox Runner commands
                elif line.startswith("sandbox-test ") and self.sandbox:
                    target_dir = line.split(maxsplit=1)[1]
                    report = self.sandbox.run_automated_tests(target_dir)
                    print(report.to_json())

                elif line.startswith("sandbox ") and self.sandbox:
                    parts = line.split(maxsplit=2)
                    target_dir = parts[1]
                    cmd = parts[2] if len(parts) > 2 else "sh"
                    report = self.sandbox.run_command(target_dir, cmd)
                    print(report.to_json())

                elif self.is_standard_shell_command(line):
                    self.execute_native_command(line)

                else:
                    self.handle_natural_language(line)

            except KeyboardInterrupt:
                print(f"\n{TerminalUI.DIM}[Interrupt. Type 'exit' to quit]{TerminalUI.RESET}")
                continue
            except EOFError:
                self._save_history()
                print(f"\n{TerminalUI.YELLOW}EOF received. Exiting...{TerminalUI.RESET}")
                break
            except Exception as e:
                TerminalUI.print_error(f"Shell loop error: {e}")


# ==============================================================================
# Script Entry Point
# ==============================================================================
if __name__ == "__main__":
    agent = AIShellAgent()
    agent.repl()
