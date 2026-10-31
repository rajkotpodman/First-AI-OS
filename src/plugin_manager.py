#!/usr/bin/env python3
"""
plugin_manager.py - Modular Plugin Subsystem & Security Sandbox for AI OS
Author: Software Platform Architect and Plugin Framework Engineer

Manages dynamic discovery, manifest validation, sandboxed execution,
permission enforcement, and natural language trigger routing for AI OS extensions.
"""

import os
import sys
import re
import json
import time
import shutil
import logging
import importlib.util
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Callable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# AI OS Subsystem imports (lazy / optional)
try:
    from personal_memory import PersonalMemoryEngine
except ImportError:
    PersonalMemoryEngine = None

try:
    from offline_docs_engine import OfflineDocsEngine
except ImportError:
    OfflineDocsEngine = None


# Default plugin search locations
USER_PLUGINS_DIR = os.path.expanduser("~/.ai_os/plugins")
LOCAL_PLUGINS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugins"))
SYSTEM_PLUGINS_DIR = "/etc/ai_os/plugins"

ALLOWED_PERMISSIONS = {
    "network",
    "filesystem_read",
    "filesystem_write",
    "execute_command",
    "memory_access",
    "docs_access"
}


# ==============================================================================
# Manifest Data Models & Validator
# ==============================================================================
@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    author: str
    entrypoint: str
    enabled: bool
    triggers: List[str]
    permissions: List[str]
    cli_command: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    plugin_dir: Path = field(default_factory=lambda: Path("."))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["plugin_dir"] = str(self.plugin_dir)
        return d


class ManifestValidator:
    """Validates plugin manifest JSON files for structure and security permissions."""

    @classmethod
    def validate(cls, manifest_data: Dict[str, Any], plugin_dir: Path) -> Tuple[bool, Optional[PluginManifest], str]:
        # Required fields check
        required_fields = ["name", "version", "entrypoint", "triggers", "permissions"]
        for f in required_fields:
            if f not in manifest_data:
                return False, None, f"Missing mandatory manifest field: '{f}'"

        name = str(manifest_data["name"]).strip()
        if not re.match(r"^[a-zA-Z0-9_\-]+$", name):
            return False, None, f"Invalid plugin name '{name}': only alphanumeric, '-' and '_' allowed."

        entrypoint = str(manifest_data["entrypoint"]).strip()
        entry_file = (plugin_dir / entrypoint).resolve()
        if not entry_file.exists():
            return False, None, f"Entrypoint script not found: '{entrypoint}' in {plugin_dir}"

        # Permissions validation
        raw_perms = manifest_data.get("permissions", [])
        if not isinstance(raw_perms, list):
            return False, None, "Manifest 'permissions' must be an array of strings."

        validated_perms = []
        for p in raw_perms:
            p_str = str(p).strip().lower()
            if p_str not in ALLOWED_PERMISSIONS:
                return False, None, f"Unrecognized or forbidden sandbox permission requested: '{p}'"
            validated_perms.append(p_str)

        triggers = [str(t).strip().lower() for t in manifest_data.get("triggers", []) if str(t).strip()]
        if not triggers:
            return False, None, "At least one natural language trigger phrase is required."

        manifest = PluginManifest(
            name=name,
            version=str(manifest_data.get("version", "1.0.0")),
            description=str(manifest_data.get("description", "")),
            author=str(manifest_data.get("author", "Unknown")),
            entrypoint=entrypoint,
            enabled=bool(manifest_data.get("enabled", True)),
            triggers=triggers,
            permissions=validated_perms,
            cli_command=manifest_data.get("cli_command"),
            config=manifest_data.get("config", {}),
            plugin_dir=plugin_dir
        )
        return True, manifest, "Manifest is valid."


# ==============================================================================
# Security Sandbox & Restricted Context Interface
# ==============================================================================
class SandboxedRunner:
    """Controlled command runner adhering strictly to plugin execution permissions."""

    def __init__(self, allowed: bool, plugin_name: str):
        self.allowed = allowed
        self.plugin_name = plugin_name

    def run(self, command: str, cwd: Optional[str] = None, timeout: int = 30) -> Tuple[int, str, str]:
        if not self.allowed:
            raise PermissionError(f"Plugin '{self.plugin_name}' does not have 'execute_command' permission.")

        # Guard against dangerous system commands
        dangerous = ["mkfs", "dd if=", "chmod -R 777 /", "> /dev/sd"]
        if any(d in command for d in dangerous):
            raise PermissionError(f"Security Sandbox blocked dangerous command pattern in plugin '{self.plugin_name}'.")

        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Execution timed out after {timeout} seconds."
        except Exception as e:
            return 1, "", str(e)


class SandboxedLogger:
    """Isolated logging interface for plugins."""

    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.logger = logging.getLogger(f"plugin.{plugin_name}")

    def info(self, msg: str):
        self.logger.info(f"[{self.plugin_name}] {msg}")

    def warn(self, msg: str):
        self.logger.warning(f"[{self.plugin_name}] {msg}")

    def error(self, msg: str):
        self.logger.error(f"[{self.plugin_name}] {msg}")


@dataclass
class PluginResult:
    plugin_name: str
    success: bool
    content: str
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PluginContext:
    """
    Restricted operating system interface exposed to plugins during execution.
    Controls access to filesystem, runner, logger, memory, and offline docs.
    """

    def __init__(self,
                 manifest: PluginManifest,
                 prompt: str = "",
                 args: Optional[List[str]] = None,
                 extra_context: Optional[Dict[str, Any]] = None):
        self.manifest = manifest
        self.plugin_name = manifest.name
        self.prompt = prompt
        self.args = args or []
        self.config = manifest.config or {}
        self.extra = extra_context or {}

        # Sandboxed components
        self.logger = SandboxedLogger(self.plugin_name)
        self.runner = SandboxedRunner(
            allowed="execute_command" in manifest.permissions,
            plugin_name=self.plugin_name
        )

        # Restricted subsystems
        self.memory = PersonalMemoryEngine() if ("memory_access" in manifest.permissions and PersonalMemoryEngine) else None
        self.docs = OfflineDocsEngine() if ("docs_access" in manifest.permissions and OfflineDocsEngine) else None

    def has_permission(self, permission: str) -> bool:
        """Checks if a specific sandbox permission was granted in manifest."""
        return permission.lower().strip() in self.manifest.permissions

    def read_file(self, file_path: str) -> str:
        """Safely reads file if filesystem_read permission is granted."""
        if not self.has_permission("filesystem_read"):
            raise PermissionError(f"Plugin '{self.plugin_name}' missing 'filesystem_read' permission.")
        p = Path(file_path).resolve()
        return p.read_text(encoding="utf-8")

    def write_file(self, file_path: str, content: str):
        """Safely writes file if filesystem_write permission is granted."""
        if not self.has_permission("filesystem_write"):
            raise PermissionError(f"Plugin '{self.plugin_name}' missing 'filesystem_write' permission.")
        p = Path(file_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ==============================================================================
# Plugin Loader & Dispatcher
# ==============================================================================
class LoadedPlugin:
    """Represents an active, validated, and loaded plugin in memory."""

    def __init__(self, manifest: PluginManifest, entry_callable: Callable[[PluginContext], Any]):
        self.manifest = manifest
        self.callable = entry_callable

    def execute(self, context: PluginContext) -> PluginResult:
        start_time = time.time()
        try:
            raw_output = self.callable(context)
            elapsed = time.time() - start_time

            if isinstance(raw_output, dict):
                return PluginResult(
                    plugin_name=self.manifest.name,
                    success=raw_output.get("success", True),
                    content=raw_output.get("content", str(raw_output)),
                    data=raw_output.get("data", {}),
                    execution_time=elapsed
                )
            elif isinstance(raw_output, str):
                return PluginResult(
                    plugin_name=self.manifest.name,
                    success=True,
                    content=raw_output,
                    execution_time=elapsed
                )
            else:
                return PluginResult(
                    plugin_name=self.manifest.name,
                    success=True,
                    content=str(raw_output),
                    execution_time=elapsed
                )
        except Exception as e:
            elapsed = time.time() - start_time
            return PluginResult(
                plugin_name=self.manifest.name,
                success=False,
                content=f"Error executing plugin '{self.manifest.name}': {e}",
                execution_time=elapsed,
                error=str(e)
            )


class PluginManager:
    """
    Central Plugin Subsystem for AI OS.
    Handles dynamic discovery, manifest checking, intent trigger matching,
    and sandboxed execution.
    """

    def __init__(self, plugin_dirs: Optional[List[str]] = None):
        self.plugin_dirs = [Path(d).resolve() for d in (plugin_dirs or [USER_PLUGINS_DIR, LOCAL_PLUGINS_DIR, SYSTEM_PLUGINS_DIR])]
        self.plugins: Dict[str, LoadedPlugin] = {}
        self.trigger_index: Dict[str, str] = {}  # trigger_phrase -> plugin_name
        self.cli_command_index: Dict[str, str] = {}  # cli_cmd -> plugin_name

        self.discover_and_load_plugins()

    def discover_and_load_plugins(self) -> int:
        """Scans plugin directories and dynamically loads valid plugins."""
        loaded_count = 0
        self.plugins.clear()
        self.trigger_index.clear()
        self.cli_command_index.clear()

        for p_dir in self.plugin_dirs:
            if not p_dir.exists() or not p_dir.is_dir():
                continue

            for item in p_dir.iterdir():
                if not item.is_dir():
                    continue

                manifest_file = item / "manifest.json"
                if not manifest_file.exists():
                    continue

                try:
                    data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    valid, manifest, reason = ManifestValidator.validate(data, item)
                    if not valid or not manifest:
                        continue

                    if not manifest.enabled:
                        continue

                    loaded = self._load_single_plugin(manifest)
                    if loaded:
                        self.plugins[manifest.name] = loaded
                        for trig in manifest.triggers:
                            self.trigger_index[trig.lower()] = manifest.name
                        if manifest.cli_command:
                            self.cli_command_index[manifest.cli_command.lower()] = manifest.name
                        loaded_count += 1
                except Exception:
                    continue

        return loaded_count

    def _load_single_plugin(self, manifest: PluginManifest) -> Optional[LoadedPlugin]:
        """Dynamically imports the entrypoint script into an isolated module."""
        entry_file = (manifest.plugin_dir / manifest.entrypoint).resolve()
        module_name = f"aios_plugin_{manifest.name}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, str(entry_file))
            if not spec or not spec.loader:
                return None

            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            # Check entrypoint function or class
            entry_callable = None
            if hasattr(mod, "execute") and callable(mod.execute):
                entry_callable = mod.execute
            elif hasattr(mod, "Plugin"):
                plugin_instance = mod.Plugin()
                if hasattr(plugin_instance, "execute") and callable(plugin_instance.execute):
                    entry_callable = plugin_instance.execute

            if not entry_callable:
                return None

            return LoadedPlugin(manifest, entry_callable)
        except Exception:
            return None

    def match_intent(self, user_prompt: str) -> Optional[Tuple[LoadedPlugin, str, float]]:
        """
        Matches a natural language prompt against registered plugin triggers.
        Returns (LoadedPlugin, matched_trigger, confidence_score) or None.
        """
        cleaned = user_prompt.strip().lower()

        # 1. Exact match on trigger
        if cleaned in self.trigger_index:
            p_name = self.trigger_index[cleaned]
            return self.plugins[p_name], cleaned, 1.0

        # 2. Trigger contained within prompt (substring or prefix)
        best_match = None
        best_len = 0
        for trigger, p_name in self.trigger_index.items():
            if trigger in cleaned:
                if len(trigger) > best_len:
                    best_match = (self.plugins[p_name], trigger, 0.95)
                    best_len = len(trigger)

        if best_match:
            return best_match

        # 3. Token-based overlap
        tokens = set(re.findall(r"\w+", cleaned))
        for trigger, p_name in self.trigger_index.items():
            trig_tokens = set(re.findall(r"\w+", trigger))
            if trig_tokens and trig_tokens.issubset(tokens):
                return self.plugins[p_name], trigger, 0.85

        return None

    def execute_by_name(self,
                        plugin_name: str,
                        prompt: str = "",
                        args: Optional[List[str]] = None,
                        extra_context: Optional[Dict[str, Any]] = None) -> PluginResult:
        """Executes a plugin directly by its name."""
        if plugin_name not in self.plugins:
            return PluginResult(
                plugin_name=plugin_name,
                success=False,
                content=f"Plugin '{plugin_name}' is not loaded or enabled.",
                error="Plugin not found"
            )

        plugin = self.plugins[plugin_name]
        ctx = PluginContext(plugin.manifest, prompt=prompt, args=args, extra_context=extra_context)
        return plugin.execute(ctx)

    def execute_matching_plugin(self, prompt: str) -> Optional[PluginResult]:
        """
        Checks if the prompt matches an active plugin trigger,
        and if so, executes the plugin and returns the result.
        """
        match = self.match_intent(prompt)
        if not match:
            return None

        plugin, trigger, confidence = match
        ctx = PluginContext(plugin.manifest, prompt=prompt)
        return plugin.execute(ctx)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Returns details of all installed and active plugins."""
        out = []
        for name, p in self.plugins.items():
            out.append(p.manifest.to_dict())
        return out


# ==============================================================================
# CLI Entrypoint for Testing
# ==============================================================================
if __name__ == "__main__":
    pm = PluginManager()
    print(f"Loaded {len(pm.plugins)} plugin(s).")
    for name, p in pm.plugins.items():
        print(f"  • {name} v{p.manifest.version}: {p.manifest.description}")
        print(f"    Triggers: {', '.join(p.manifest.triggers)}")
