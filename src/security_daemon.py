#!/usr/bin/env python3
"""
security_daemon.py - Fine-Grained Security Guardrail & Permission Subsystem
Author: Linux Security Architect & System Auditor

Provides strict pre-execution evaluation, risk classification, path boundary enforcement,
and tamper-evident cryptographic audit logging for AI agent actions and system operations.
"""

import os
import sys
import re
import json
import time
import shlex
import socket
import hashlib
import platform
import subprocess
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Callable

# ==============================================================================
# Constants & Default Configurations
# ==============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_POLICY_PATHS = [
    "/etc/ai_os/security_policy.json",
    os.path.abspath(os.path.join(SCRIPT_DIR, "..", "configs", "security_policy.json")),
    os.path.abspath(os.path.join(SCRIPT_DIR, "security_policy.json")),
    os.path.abspath(os.path.join(os.getcwd(), "configs", "security_policy.json")),
    os.path.abspath(os.path.join(os.getcwd(), "security_policy.json"))
]

DEFAULT_AUDIT_LOG_PRIMARY = "/var/log/ai_security_audit.log"
DEFAULT_AUDIT_LOG_FALLBACK = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "logs", "ai_security_audit.log"))
DEFAULT_SOCKET_PATH = "/run/ai_security.sock"
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 9876
GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


# ==============================================================================
# Enums & Data Structures
# ==============================================================================
class RiskLevel(str, Enum):
    LOW = "LOW"            # Auto-approve: Read-only inspection commands
    MEDIUM = "MEDIUM"      # Notify: Safe writes inside workspace, safe package installs
    HIGH = "HIGH"          # Prompt required: Root ops, package removals, socket/firewall, disk edits, rm -rf
    BLOCKED = "BLOCKED"    # Hard block: Out-of-bounds writes, critical dir attacks, catastrophic wipes


class ApprovalStatus(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    NOTIFIED_ALLOWED = "NOTIFIED_ALLOWED"
    USER_APPROVED = "USER_APPROVED"
    USER_DENIED = "USER_DENIED"
    BLOCKED_DISALLOWED = "BLOCKED_DISALLOWED"


class ExecutionOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    DENIED = "DENIED"
    SKIPPED = "SKIPPED"


@dataclass
class EvaluationResult:
    command: str
    risk_level: RiskLevel
    approval_status: ApprovalStatus
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    detected_paths: List[str] = field(default_factory=list)
    critical_violations: List[str] = field(default_factory=list)
    action_type: str = "shell_command"
    requires_prompt: bool = False
    prompt_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["risk_level"] = self.risk_level.value
        data["approval_status"] = self.approval_status.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AuditEntry:
    entry_id: int
    timestamp: str
    command: str
    action_type: str
    risk_level: str
    approval_status: str
    execution_outcome: str
    target_paths: List[str]
    reasons: List[str]
    prev_hash: str
    entry_hash: str = ""

    def compute_hash(self) -> str:
        payload = {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "command": self.command,
            "action_type": self.action_type,
            "risk_level": self.risk_level,
            "approval_status": self.approval_status,
            "execution_outcome": self.execution_outcome,
            "target_paths": sorted(self.target_paths),
            "reasons": self.reasons,
            "prev_hash": self.prev_hash
        }
        canonical_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True) + "\n"


# ==============================================================================
# Tamper-Evident Hash-Chained Audit Logger
# ==============================================================================
class AuditLogger:
    """
    Maintains an append-only, tamper-evident cryptographic hash chain of all
    evaluated and executed AI operations.
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = self._resolve_log_path(log_path)
        self._ensure_log_directory()
        self._last_entry_id = 0
        self._last_entry_hash = GENESIS_HASH
        self._sync_chain_head()

    def _resolve_log_path(self, custom_path: Optional[str]) -> str:
        if custom_path:
            return os.path.abspath(custom_path)

        # On Linux root, attempt /var/log/ai_security_audit.log
        if platform.system() != "Windows":
            try:
                test_dir = os.path.dirname(DEFAULT_AUDIT_LOG_PRIMARY)
                if os.path.exists(test_dir) and os.access(test_dir, os.W_OK):
                    return DEFAULT_AUDIT_LOG_PRIMARY
            except Exception:
                pass

        # Fallback to local logs directory
        return DEFAULT_AUDIT_LOG_FALLBACK

    def _ensure_log_directory(self):
        log_dir = os.path.dirname(self.log_path)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception:
                # If cannot create /var/log or parent, fallback to local ./logs
                self.log_path = DEFAULT_AUDIT_LOG_FALLBACK
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _sync_chain_head(self):
        """Scans the existing log file to find the latest valid block in the hash chain."""
        if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
            self._last_entry_id = 0
            self._last_entry_hash = GENESIS_HASH
            return

        last_id = 0
        last_hash = GENESIS_HASH
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    last_id = record.get("entry_id", last_id + 1)
                    last_hash = record.get("entry_hash", last_hash)
            self._last_entry_id = last_id
            self._last_entry_hash = last_hash
        except Exception as e:
            # If log corrupted during read, retain discovered state
            pass

    def log_event(self,
                  command: str,
                  risk_level: RiskLevel,
                  approval_status: ApprovalStatus,
                  execution_outcome: ExecutionOutcome,
                  target_paths: Optional[List[str]] = None,
                  reasons: Optional[List[str]] = None,
                  action_type: str = "shell_command") -> AuditEntry:
        """
        Cryptographically signs and appends an event to the tamper-evident audit log.
        """
        self._last_entry_id += 1
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        target_paths = target_paths or []
        reasons = reasons or []

        entry = AuditEntry(
            entry_id=self._last_entry_id,
            timestamp=timestamp,
            command=command,
            action_type=action_type,
            risk_level=risk_level.value,
            approval_status=approval_status.value,
            execution_outcome=execution_outcome.value,
            target_paths=target_paths,
            reasons=reasons,
            prev_hash=self._last_entry_hash
        )

        entry.entry_hash = entry.compute_hash()
        self._last_entry_hash = entry.entry_hash

        # Atomic append and fsync to ensure tamper resistance
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry.to_json_line())
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

        return entry

    def record_event(self, action_type: str, details: Optional[Dict[str, Any]] = None) -> AuditEntry:
        """Convenience method to log lifecycle events like SYSTEM_BOOT, SYSTEM_SHUTDOWN."""
        details = details or {}
        cmd_str = f"system_lifecycle::{action_type.lower()}"
        reasons = [f"{k}: {v}" for k, v in details.items()] if details else [f"System event: {action_type}"]
        return self.log_event(
            command=cmd_str,
            risk_level=RiskLevel.LOW,
            approval_status=ApprovalStatus.AUTO_APPROVED,
            execution_outcome=ExecutionOutcome.SUCCESS,
            target_paths=[],
            reasons=reasons,
            action_type=action_type
        )

    def read_entries(self) -> List[Dict[str, Any]]:
        """Reads and parses all JSON lines from the audit log."""
        if not os.path.exists(self.log_path):
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries

    @staticmethod
    def verify_audit_log(log_path: str) -> Tuple[bool, int, List[str]]:
        """
        Audits and mathematically verifies the entire cryptographic hash chain of an audit log.
        Returns:
            (is_valid: bool, verified_count: int, violations: List[str])
        """
        if not os.path.exists(log_path):
            return False, 0, [f"Audit log file does not exist: {log_path}"]

        violations = []
        expected_prev_hash = GENESIS_HASH
        expected_id = 1
        verified_count = 0

        with open(log_path, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue

                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError as err:
                    violations.append(f"Line {line_no}: Malformed JSON syntax - {err}")
                    return False, verified_count, violations

                entry_id = record.get("entry_id")
                entry_hash = record.get("entry_hash")
                prev_hash = record.get("prev_hash")

                # Verify sequence ID
                if entry_id != expected_id:
                    violations.append(
                        f"Line {line_no}: Sequence ID broken (expected {expected_id}, got {entry_id})"
                    )

                # Verify previous block hash link
                if prev_hash != expected_prev_hash:
                    violations.append(
                        f"Line {line_no}: Hash chain link broken! Previous hash mismatch.\n"
                        f"  Expected: {expected_prev_hash}\n"
                        f"  Recorded: {prev_hash}"
                    )

                # Recompute current entry hash
                entry_obj = AuditEntry(
                    entry_id=entry_id,
                    timestamp=record.get("timestamp", ""),
                    command=record.get("command", ""),
                    action_type=record.get("action_type", ""),
                    risk_level=record.get("risk_level", ""),
                    approval_status=record.get("approval_status", ""),
                    execution_outcome=record.get("execution_outcome", ""),
                    target_paths=record.get("target_paths", []),
                    reasons=record.get("reasons", []),
                    prev_hash=prev_hash
                )
                computed_hash = entry_obj.compute_hash()

                if computed_hash != entry_hash:
                    violations.append(
                        f"Line {line_no}: Cryptographic tampering detected in entry data!\n"
                        f"  Calculated Hash: {computed_hash}\n"
                        f"  Tampered Hash:   {entry_hash}"
                    )

                expected_prev_hash = entry_hash
                expected_id = entry_id + 1
                verified_count += 1

        is_valid = (len(violations) == 0 and verified_count > 0)
        return is_valid, verified_count, violations


# ==============================================================================
# Path Traversal & Boundary Enforcer
# ==============================================================================
class BoundaryEnforcer:
    """
    Validates filesystem targets against authorized project workspaces and
    blocks any attempted modification of protected host OS directories.
    """

    def __init__(self,
                 allowed_workspaces: Optional[List[str]] = None,
                 critical_directories: Optional[List[str]] = None,
                 default_workspace: str = "/workspace"):
        self.default_workspace = default_workspace
        self.allowed_workspaces = allowed_workspaces or [
            "/workspace",
            "/home",
            "/tmp/workspace",
            "./workspace",
            "./"
        ]
        self.critical_directories = critical_directories or [
            "/boot",
            "/etc/shadow",
            "/etc/passwd",
            "/etc/sudoers",
            "/etc/security",
            "/etc",
            "/lib",
            "/lib64",
            "/usr/lib",
            "/usr/lib64",
            "/bin",
            "/sbin",
            "/usr/bin",
            "/usr/sbin",
            "/sys",
            "/proc",
            "/dev",
            "/root",
            "/vmlinuz",
            "/initrd.img"
        ]

    def normalize_posix(self, path: str) -> str:
        """Normalizes path representation for unified rule matching."""
        p = path.replace("\\", "/").strip()
        # Remove trailing slash unless it's root
        if len(p) > 1 and p.endswith("/"):
            p = p[:-1]
        return p

    def is_critical_directory(self, target_path: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
        """
        Checks whether target_path matches or is contained inside a protected system directory.
        """
        norm_path = self.normalize_posix(target_path)
        base_cwd = self.normalize_posix(cwd or self.default_workspace)

        # Handle absolute and relative resolution
        if not norm_path.startswith("/") and not (len(norm_path) > 1 and norm_path[1] == ":"):
            resolved = self.normalize_posix(os.path.normpath(f"{base_cwd}/{norm_path}"))
        else:
            resolved = self.normalize_posix(os.path.normpath(norm_path))

        # Check exact and prefix match for critical host directories
        for crit in self.critical_directories:
            norm_crit = self.normalize_posix(crit)
            if resolved == norm_crit or resolved.startswith(norm_crit + "/"):
                return True, f"Target path '{norm_path}' resolves to critical host directory '{norm_crit}'"

        return False, ""

    def is_within_allowed_boundary(self, target_path: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
        """
        Verifies that a write/modify target is strictly inside designated workspace paths.
        Detects path traversal attacks (e.g. '/workspace/../../etc/shadow').
        """
        norm_path = self.normalize_posix(target_path)
        base_cwd = self.normalize_posix(cwd or self.default_workspace)

        # Resolve path components and eliminate dot-dot traversal
        if not norm_path.startswith("/") and not (len(norm_path) > 1 and norm_path[1] == ":"):
            resolved = self.normalize_posix(os.path.normpath(f"{base_cwd}/{norm_path}"))
        else:
            resolved = self.normalize_posix(os.path.normpath(norm_path))

        # First check critical host collision
        is_crit, crit_msg = self.is_critical_directory(resolved, cwd)
        if is_crit:
            return False, f"Boundary violation: {crit_msg}"

        # Check if resolved is within at least one allowed workspace
        for allowed in self.allowed_workspaces:
            norm_allowed = self.normalize_posix(allowed)

            # If allowed is relative (e.g. './' or './workspace')
            if not norm_allowed.startswith("/") and not (len(norm_allowed) > 1 and norm_allowed[1] == ":"):
                norm_allowed = self.normalize_posix(os.path.normpath(f"{base_cwd}/{norm_allowed}"))

            if resolved == norm_allowed or resolved.startswith(norm_allowed + "/"):
                return True, f"Path '{norm_path}' safely contained in '{norm_allowed}'"

        return False, f"Target path '{norm_path}' (resolved: '{resolved}') is outside allowed workspaces: {self.allowed_workspaces}"


# ==============================================================================
# Security Evaluator Engine
# ==============================================================================
class SecurityEvaluator:
    """
    Evaluates shell commands and system calls against security policies, assigning
    risk tiers (LOW, MEDIUM, HIGH, BLOCKED) and enforcing boundary guardrails.
    """

    def __init__(self, policy: Optional[Dict[str, Any]] = None):
        self.policy = policy or self._load_default_policy()
        boundaries = self.policy.get("boundaries", {})
        self.enforcer = BoundaryEnforcer(
            allowed_workspaces=boundaries.get("allowed_write_paths"),
            critical_directories=boundaries.get("critical_host_directories"),
            default_workspace=self.policy.get("daemon", {}).get("default_workspace", "/workspace")
        )
        self.risk_rules = self.policy.get("risk_rules", {})
        self.syscall_rules = self.policy.get("syscall_guardrails", {})

    def _load_default_policy(self) -> Dict[str, Any]:
        for p in DEFAULT_POLICY_PATHS:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass

        # Built-in robust policy fallback
        return {
            "daemon": {"default_workspace": "/workspace"},
            "boundaries": {
                "allowed_write_paths": ["/workspace", "/home", "/tmp/workspace", "./workspace", "./"],
                "critical_host_directories": ["/boot", "/etc/shadow", "/etc", "/lib", "/lib64", "/sys", "/proc", "/dev", "/root"]
            },
            "risk_rules": {
                "low_commands": ["ls", "cat", "grep", "egrep", "status", "ps", "top", "df", "du", "pwd", "whoami", "uname", "id", "uptime", "head", "tail", "wc", "echo", "date", "find"],
                "medium_commands": ["mkdir", "touch", "cp", "tee", "git", "python", "python3", "node", "npm", "cargo", "go", "tar", "gzip"],
                "medium_package_install_patterns": [r"^apk\s+add\b", r"^apt(-get)?\s+install\b", r"^pip[0-9]*\s+install\b", r"^npm\s+install\b"],
                "high_commands": ["sudo", "su", "doas", "rm", "unlink", "shred", "kill", "pkill", "systemctl", "iptables", "nftables", "ip", "ifconfig", "fdisk", "parted", "mkfs", "dd", "mount", "umount", "chmod", "chown"],
                "high_package_removal_patterns": [r"^apk\s+del\b", r"^apt(-get)?\s+(remove|purge)\b", r"^dpkg\s+-(r|P)\b"],
                "high_network_patterns": [r".*iptables\s+.*", r".*ip\s+route.*", r".*ifconfig.*"],
                "blocked_patterns": [
                    r"^rm\s+(-[a-zA-Z]*r[a-zA-Z]*f*|-f[a-zA-Z]*r[a-zA-Z]*)\s+(/|/\*)$",
                    r".*rm\s+.*--no-preserve-root.*",
                    r".*mkfs(\.[a-z0-9]+)?\s+/dev/.*",
                    r".*dd\s+.*of=/dev/(sd[a-z]|nvme|hd[a-z]|mem|kmem).*",
                    r".*:\(\)\s*\{\s*:\|:&\s*\};:.*",
                    r".*kill\s+-9\s+1\b.*"
                ]
            },
            "syscall_guardrails": {
                "blocked_syscalls": ["reboot", "kexec_load", "init_module", "delete_module", "bpf", "swapon", "swapoff", "sys_chroot", "ptrace"],
                "high_risk_syscalls": ["mount", "umount2", "setuid", "setgid", "kill", "unlink", "unlinkat"],
                "medium_syscalls": ["mkdir", "creat", "openat", "write", "pwrite64"],
                "low_syscalls": ["read", "stat", "fstat", "access", "getcwd"]
            }
        }

    def _split_compound_commands(self, command_line: str) -> List[str]:
        """Splits pipelines, logical chains, and sequential command invocations."""
        cmd = command_line.strip()
        # Split on &&, ||, ;, and | while respecting quoted segments
        pattern = r'(?:[^\s"\';|&]+|"[^"]*"|\'[^\']*\')+'
        # Regex to split on unquoted delimiters
        delimiters = r'(&&|\|\||;|\|)'
        parts = re.split(delimiters, cmd)

        sub_commands = []
        for p in parts:
            p_strip = p.strip()
            if p_strip and p_strip not in ("&&", "||", ";", "|"):
                sub_commands.append(p_strip)

        return sub_commands if sub_commands else [cmd]

    def _extract_paths_from_command(self, cmd_tokens: List[str]) -> List[str]:
        """Extracts potential filesystem path arguments from tokenized shell commands."""
        paths = []
        for idx, token in enumerate(cmd_tokens):
            clean = token.strip()
            # Handle redirection targets (e.g. > /file or >> /file)
            if clean.startswith(">") or clean.startswith("<"):
                target = clean.lstrip("><").strip()
                if target:
                    paths.append(target)
                elif idx + 1 < len(cmd_tokens):
                    paths.append(cmd_tokens[idx + 1].strip())
                continue

            # Skip command flags/options (e.g. -rf, --force)
            if clean.startswith("-") and not (clean == "-" or clean.startswith("-/")):
                continue

            # Identify path-like tokens (containing slash, dot, or starting with tilde/workspace)
            if "/" in clean or "\\" in clean or clean.startswith(".") or clean.startswith("~"):
                paths.append(clean)
            elif idx > 0 and cmd_tokens[0] in ("rm", "touch", "mkdir", "cat", "cp", "mv", "vi", "nano"):
                # Arguments to file manipulation commands are treated as target paths
                paths.append(clean)

        return paths

    def evaluate_syscall(self, syscall_name: str, args: Optional[List[Any]] = None) -> EvaluationResult:
        """Evaluates an intercepted system call against security rules."""
        name = syscall_name.strip().lower()
        blocked_syscalls = self.syscall_rules.get("blocked_syscalls", [])
        high_syscalls = self.syscall_rules.get("high_risk_syscalls", [])
        medium_syscalls = self.syscall_rules.get("medium_syscalls", [])
        low_syscalls = self.syscall_rules.get("low_syscalls", [])

        if name in blocked_syscalls:
            return EvaluationResult(
                command=f"syscall::{name}",
                risk_level=RiskLevel.BLOCKED,
                approval_status=ApprovalStatus.BLOCKED_DISALLOWED,
                allowed=False,
                reasons=[f"Syscall '{name}' is strictly forbidden by kernel seccomp policy"],
                action_type="syscall"
            )

        if name in high_syscalls:
            return EvaluationResult(
                command=f"syscall::{name}",
                risk_level=RiskLevel.HIGH,
                approval_status=ApprovalStatus.USER_DENIED,
                allowed=False,
                requires_prompt=True,
                reasons=[f"Syscall '{name}' performs privileged or system-altering operation"],
                prompt_message=f"Intercepted High-Risk Syscall: {name}. Grant execution?",
                action_type="syscall"
            )

        if name in medium_syscalls:
            return EvaluationResult(
                command=f"syscall::{name}",
                risk_level=RiskLevel.MEDIUM,
                approval_status=ApprovalStatus.NOTIFIED_ALLOWED,
                allowed=True,
                reasons=[f"Syscall '{name}' modifies files or allocated memory"],
                action_type="syscall"
            )

        # Default to low / auto-approve if in allowed low list
        return EvaluationResult(
            command=f"syscall::{name}",
            risk_level=RiskLevel.LOW,
            approval_status=ApprovalStatus.AUTO_APPROVED,
            allowed=True,
            reasons=[f"Syscall '{name}' is read-only or standard unprivileged call"],
            action_type="syscall"
        )

    def evaluate_command(self, command_line: str, cwd: Optional[str] = None) -> EvaluationResult:
        """
        Comprehensive evaluation of a shell command line:
        1. Checks zero-tolerance catastrophic signatures (BLOCKED).
        2. Detects path traversals and critical host directory modifications (BLOCKED).
        3. Identifies root operations, package removals, network edits, and destructive writes (HIGH).
        4. Identifies non-destructive workspace writes and safe package installations (MEDIUM).
        5. Identifies read-only inspection commands (LOW).
        """
        cmd_raw = command_line.strip()
        cwd = cwd or self.policy.get("daemon", {}).get("default_workspace", "/workspace")

        if not cmd_raw:
            return EvaluationResult(
                command="",
                risk_level=RiskLevel.LOW,
                approval_status=ApprovalStatus.AUTO_APPROVED,
                allowed=True,
                reasons=["Empty command line"]
            )

        reasons = []
        detected_paths = []
        critical_violations = []

        # ----------------------------------------------------------------------
        # Step 1: Check Zero-Tolerance Blocked Regex Signatures
        # ----------------------------------------------------------------------
        blocked_patterns = self.risk_rules.get("blocked_patterns", [])
        for pat in blocked_patterns:
            if re.search(pat, cmd_raw, re.IGNORECASE):
                reasons.append(f"Matched blocked catastrophic signature pattern: {pat}")
                return EvaluationResult(
                    command=cmd_raw,
                    risk_level=RiskLevel.BLOCKED,
                    approval_status=ApprovalStatus.BLOCKED_DISALLOWED,
                    allowed=False,
                    reasons=reasons,
                    detected_paths=detected_paths,
                    critical_violations=[f"Zero-tolerance catastrophic signature matched: {pat}"]
                )

        # ----------------------------------------------------------------------
        # Step 2: Parse and Evaluate Sub-commands & Arguments
        # ----------------------------------------------------------------------
        sub_cmds = self._split_compound_commands(cmd_raw)
        sub_risks: List[RiskLevel] = []

        for sub_cmd in sub_cmds:
            sub_clean = sub_cmd.strip()
            if not sub_clean:
                continue

            try:
                tokens = shlex.split(sub_clean, posix=(platform.system() != "Windows"))
            except ValueError:
                # Malformed quoting / injection evasion attempt
                reasons.append("Unbalanced quotes or unparseable shell command tokens detected")
                return EvaluationResult(
                    command=cmd_raw,
                    risk_level=RiskLevel.BLOCKED,
                    approval_status=ApprovalStatus.BLOCKED_DISALLOWED,
                    allowed=False,
                    reasons=reasons,
                    critical_violations=["Command string contains invalid or obfuscated shell syntax"]
                )

            if not tokens:
                continue

            # Strip leading environment variables (e.g. VAR=val cmd)
            cmd_idx = 0
            while cmd_idx < len(tokens) and "=" in tokens[cmd_idx] and not tokens[cmd_idx].startswith("-"):
                cmd_idx += 1
            if cmd_idx >= len(tokens):
                cmd_idx = 0

            base_binary = os.path.basename(tokens[cmd_idx])

            # Extract target paths
            paths_in_sub = self._extract_paths_from_command(tokens[cmd_idx:])
            detected_paths.extend(paths_in_sub)

            # ------------------------------------------------------------------
            # Boundary & Critical Directory Enforcement
            # ------------------------------------------------------------------
            # Determine if this command writes or deletes files
            is_write_cmd = base_binary in (
                "rm", "unlink", "shred", "touch", "mkdir", "cp", "mv", "tee",
                "truncate", "sed", "dd", "mkfs", "chmod", "chown", "tar"
            ) or (">" in sub_clean)

            for target in paths_in_sub:
                # Check for critical directory targets
                is_crit, crit_err = self.enforcer.is_critical_directory(target, cwd=cwd)
                if is_crit:
                    # If command is writing/deleting to a critical directory, immediate BLOCK
                    if is_write_cmd or base_binary in ("rm", "mv", "dd", "chmod", "chown"):
                        critical_violations.append(f"Blocked write/delete to critical host directory: {crit_err}")
                        reasons.append(crit_err)
                        return EvaluationResult(
                            command=cmd_raw,
                            risk_level=RiskLevel.BLOCKED,
                            approval_status=ApprovalStatus.BLOCKED_DISALLOWED,
                            allowed=False,
                            reasons=reasons,
                            detected_paths=detected_paths,
                            critical_violations=critical_violations
                        )
                    else:
                        # Read-only access to shadow/security files is HIGH risk
                        if any(sensitive in target for sensitive in ("/etc/shadow", "/etc/sudoers")):
                            reasons.append(f"Attempted access to highly sensitive system file: {target}")
                            sub_risks.append(RiskLevel.HIGH)

                # If it's a write or delete, enforce strict workspace boundaries
                if is_write_cmd:
                    in_boundary, boundary_err = self.enforcer.is_within_allowed_boundary(target, cwd=cwd)
                    if not in_boundary:
                        critical_violations.append(boundary_err)
                        reasons.append(f"Path traversal or boundary violation: {boundary_err}")
                        return EvaluationResult(
                            command=cmd_raw,
                            risk_level=RiskLevel.BLOCKED,
                            approval_status=ApprovalStatus.BLOCKED_DISALLOWED,
                            allowed=False,
                            reasons=reasons,
                            detected_paths=detected_paths,
                            critical_violations=critical_violations
                        )

            # ------------------------------------------------------------------
            # Classify Sub-Command Risk Level
            # ------------------------------------------------------------------
            # 1. High Risk Commands & Root Elevation
            high_commands = self.risk_rules.get("high_commands", [])
            removal_patterns = self.risk_rules.get("high_package_removal_patterns", [])
            network_patterns = self.risk_rules.get("high_network_patterns", [])

            is_high = False
            if base_binary in high_commands:
                is_high = True
                reasons.append(f"Command '{base_binary}' requires elevated privileges or is potentially destructive")

            # Check package removals (e.g. apk del, apt remove)
            for r_pat in removal_patterns:
                if re.search(r_pat, sub_clean, re.IGNORECASE):
                    is_high = True
                    reasons.append(f"Detected system package removal operation: {sub_clean}")
                    break

            # Check network/socket/firewall changes
            for n_pat in network_patterns:
                if re.search(n_pat, sub_clean, re.IGNORECASE):
                    is_high = True
                    reasons.append(f"Detected network/firewall/socket configuration alteration: {sub_clean}")
                    break

            # Check recursive or force deletion
            if base_binary == "rm":
                is_high = True
                reasons.append("File deletion command requires explicit confirmation")

            if is_high:
                sub_risks.append(RiskLevel.HIGH)
                continue

            # 2. Medium Risk (Safe writes, safe installs)
            medium_commands = self.risk_rules.get("medium_commands", [])
            install_patterns = self.risk_rules.get("medium_package_install_patterns", [])

            is_medium = False
            if base_binary in medium_commands or (">" in sub_clean):
                is_medium = True
                reasons.append(f"Non-destructive write or workspace operation: '{base_binary}'")

            for i_pat in install_patterns:
                if re.search(i_pat, sub_clean, re.IGNORECASE):
                    is_medium = True
                    reasons.append(f"Safe package installation detected: {sub_clean}")
                    break

            if is_medium:
                sub_risks.append(RiskLevel.MEDIUM)
                continue

            # 3. Low Risk (Read-only tools)
            low_commands = self.risk_rules.get("low_commands", [])
            if base_binary in low_commands:
                sub_risks.append(RiskLevel.LOW)
                continue

            # If unrecognized command, treat as HIGH for safety
            sub_risks.append(RiskLevel.HIGH)
            reasons.append(f"Unrecognized binary '{base_binary}' defaulted to HIGH risk tier")

        # ----------------------------------------------------------------------
        # Step 3: Compute Overall Composite Risk Level
        # ----------------------------------------------------------------------
        if RiskLevel.BLOCKED in sub_risks:
            composite_risk = RiskLevel.BLOCKED
            approval = ApprovalStatus.BLOCKED_DISALLOWED
            allowed = False
        elif RiskLevel.HIGH in sub_risks:
            composite_risk = RiskLevel.HIGH
            approval = ApprovalStatus.USER_DENIED
            allowed = False
        elif RiskLevel.MEDIUM in sub_risks:
            composite_risk = RiskLevel.MEDIUM
            approval = ApprovalStatus.NOTIFIED_ALLOWED
            allowed = True
        else:
            composite_risk = RiskLevel.LOW
            approval = ApprovalStatus.AUTO_APPROVED
            allowed = True

        prompt_msg = ""
        requires_prompt = False
        if composite_risk == RiskLevel.HIGH:
            requires_prompt = True
            prompt_msg = (
                f"[SECURITY PROMPT] The AI action involves HIGH-RISK operations:\n"
                f"  Command: {cmd_raw}\n"
                f"  Warnings: {'; '.join(reasons)}\n"
                f"Authorize execution? (yes/no): "
            )

        return EvaluationResult(
            command=cmd_raw,
            risk_level=composite_risk,
            approval_status=approval,
            allowed=allowed,
            reasons=reasons,
            detected_paths=list(set(detected_paths)),
            critical_violations=critical_violations,
            requires_prompt=requires_prompt,
            prompt_message=prompt_msg
        )


# ==============================================================================
# Security Daemon & Permission Manager
# ==============================================================================
class SecurityDaemon:
    """
    Coordinates security evaluation, user authorization prompts, safe command
    execution, and cryptographic audit trail logging.
    """

    def __init__(self,
                 policy_path: Optional[str] = None,
                 audit_log_path: Optional[str] = None):
        self.policy = self._load_policy(policy_path)
        self.evaluator = SecurityEvaluator(self.policy)
        self.audit_logger = AuditLogger(audit_log_path or self.policy.get("daemon", {}).get("audit_log_path"))

    def _load_policy(self, path: Optional[str]) -> Dict[str, Any]:
        search_candidates = [path] if path else DEFAULT_POLICY_PATHS
        for p in search_candidates:
            if p and os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    print(f"[!] Warning: Failed parsing policy file '{p}': {e}", file=sys.stderr)
        # Return fallback
        return SecurityEvaluator(None)._load_default_policy()

    def evaluate(self, command: str, cwd: Optional[str] = None) -> EvaluationResult:
        """Evaluates command risk without executing it."""
        return self.evaluator.evaluate_command(command, cwd=cwd)

    def evaluate_syscall(self, syscall_name: str, args: Optional[List[Any]] = None) -> EvaluationResult:
        """Evaluates system call risk."""
        return self.evaluator.evaluate_syscall(syscall_name, args)

    def execute_with_guardrails(self,
                                command: str,
                                cwd: Optional[str] = None,
                                user_approval_callback: Optional[Callable[[EvaluationResult], bool]] = None,
                                interactive: bool = True) -> Tuple[bool, int, str, str]:
        """
        Intercepts, evaluates, requests authorization if needed, executes the command,
        and logs the tamper-evident audit record.
        Returns:
            (executed: bool, exit_code: int, stdout: str, stderr: str)
        """
        res = self.evaluate(command, cwd=cwd)

        # Handle BLOCKED commands immediately
        if res.risk_level == RiskLevel.BLOCKED:
            self.audit_logger.log_event(
                command=command,
                risk_level=res.risk_level,
                approval_status=ApprovalStatus.BLOCKED_DISALLOWED,
                execution_outcome=ExecutionOutcome.BLOCKED,
                target_paths=res.detected_paths,
                reasons=res.reasons
            )
            err_msg = f"[SECURITY VIOLATION] Command strictly BLOCKED:\n  " + "\n  ".join(res.critical_violations or res.reasons)
            print(f"\033[1;31m{err_msg}\033[0m", file=sys.stderr)
            return False, -1, "", err_msg

        # Handle HIGH risk commands (Prompt required)
        if res.risk_level == RiskLevel.HIGH:
            approved = False
            if user_approval_callback:
                approved = user_approval_callback(res)
            elif interactive and sys.stdin.isatty():
                print(f"\033[1;33m{res.prompt_message}\033[0m", end="")
                try:
                    ans = input().strip().lower()
                    approved = ans in ("y", "yes")
                except (EOFError, KeyboardInterrupt):
                    approved = False
            else:
                # Non-interactive without callback denies HIGH risk actions
                approved = False

            if not approved:
                self.audit_logger.log_event(
                    command=command,
                    risk_level=res.risk_level,
                    approval_status=ApprovalStatus.USER_DENIED,
                    execution_outcome=ExecutionOutcome.DENIED,
                    target_paths=res.detected_paths,
                    reasons=res.reasons + ["User denied or non-interactive context rejected high-risk execution"]
                )
                denied_msg = f"[GUARDRAIL DENIED] High-risk command rejected by user policy: {command}"
                print(f"\033[1;33m{denied_msg}\033[0m", file=sys.stderr)
                return False, -2, "", denied_msg

            # Approved by user
            approval_status = ApprovalStatus.USER_APPROVED
        elif res.risk_level == RiskLevel.MEDIUM:
            # Medium risk: Notify and proceed
            approval_status = ApprovalStatus.NOTIFIED_ALLOWED
            print(f"\033[1;36m[NOTIFY] Executing non-destructive write / package operation:\033[0m {command}")
        else:
            # Low risk: Auto-approve
            approval_status = ApprovalStatus.AUTO_APPROVED

        # Execute Command
        try:
            run_cwd = cwd or self.policy.get("daemon", {}).get("default_workspace", "/workspace")
            if not os.path.exists(run_cwd):
                run_cwd = os.getcwd()

            proc = subprocess.run(
                command,
                shell=True,
                cwd=run_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120
            )
            outcome = ExecutionOutcome.SUCCESS if proc.returncode == 0 else ExecutionOutcome.FAILED

            self.audit_logger.log_event(
                command=command,
                risk_level=res.risk_level,
                approval_status=approval_status,
                execution_outcome=outcome,
                target_paths=res.detected_paths,
                reasons=res.reasons
            )
            return True, proc.returncode, proc.stdout, proc.stderr

        except subprocess.TimeoutExpired:
            self.audit_logger.log_event(
                command=command,
                risk_level=res.risk_level,
                approval_status=approval_status,
                execution_outcome=ExecutionOutcome.FAILED,
                target_paths=res.detected_paths,
                reasons=res.reasons + ["Process execution timed out (120s)"]
            )
            return False, -3, "", "Execution timed out"

        except Exception as ex:
            self.audit_logger.log_event(
                command=command,
                risk_level=res.risk_level,
                approval_status=approval_status,
                execution_outcome=ExecutionOutcome.FAILED,
                target_paths=res.detected_paths,
                reasons=res.reasons + [f"Execution exception: {str(ex)}"]
            )
            return False, -4, "", str(ex)

    def run_daemon_server(self, socket_path: Optional[str] = None):
        """
        Runs the daemon service listening for AI agent IPC requests over UNIX domain socket
        or local TCP loopback.
        """
        sock_file = socket_path or self.policy.get("daemon", {}).get("socket_path", DEFAULT_SOCKET_PATH)
        use_unix = (platform.system() != "Windows")

        server = None
        try:
            if use_unix:
                if os.path.exists(sock_file):
                    os.unlink(sock_file)
                sock_dir = os.path.dirname(sock_file)
                if sock_dir and not os.path.exists(sock_dir):
                    os.makedirs(sock_dir, exist_ok=True)
                server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                server.bind(sock_file)
                print(f"[*] Security Guardrail Daemon listening on UNIX socket: {sock_file}")
            else:
                port = self.policy.get("daemon", {}).get("fallback_tcp_port", DEFAULT_TCP_PORT)
                host = self.policy.get("daemon", {}).get("fallback_tcp_host", DEFAULT_TCP_HOST)
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((host, port))
                print(f"[*] Security Guardrail Daemon listening on TCP: {host}:{port}")

            server.listen(5)
            while True:
                conn, _ = server.accept()
                with conn:
                    data = conn.recv(65536)
                    if not data:
                        continue
                    try:
                        req = json.loads(data.decode("utf-8"))
                        action = req.get("action", "evaluate")

                        if action == "evaluate":
                            cmd = req.get("command", "")
                            cwd = req.get("cwd")
                            eval_res = self.evaluate(cmd, cwd=cwd)
                            response = eval_res.to_dict()

                        elif action == "evaluate_syscall":
                            sys_name = req.get("syscall", "")
                            sys_args = req.get("args", [])
                            eval_res = self.evaluate_syscall(sys_name, sys_args)
                            response = eval_res.to_dict()

                        elif action == "verify_audit":
                            log_path = req.get("log_path", self.audit_logger.log_path)
                            valid, count, errors = AuditLogger.verify_audit_log(log_path)
                            response = {"valid": valid, "verified_entries": count, "violations": errors}

                        else:
                            response = {"error": f"Unknown action: {action}"}

                        conn.sendall(json.dumps(response).encode("utf-8"))
                    except Exception as err:
                        err_resp = {"error": f"Request processing failed: {err}"}
                        conn.sendall(json.dumps(err_resp).encode("utf-8"))

        except KeyboardInterrupt:
            print("\n[*] Shutting down Security Daemon.")
        finally:
            if server:
                server.close()
            if use_unix and os.path.exists(sock_file):
                try:
                    os.unlink(sock_file)
                except Exception:
                    pass


# ==============================================================================
# CLI Entrypoint & Utility Subcommands
# ==============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Fine-Grained Security Guardrails & Permission Manager Daemon for AI OS"
    )
    parser.add_argument("--eval", dest="eval_cmd", type=str, help="Evaluate risk and boundaries of a shell command")
    parser.add_argument("--exec", dest="exec_cmd", type=str, help="Evaluate, prompt if high-risk, execute, and log")
    parser.add_argument("--eval-syscall", dest="eval_syscall", type=str, help="Evaluate risk of a system call")
    parser.add_argument("--daemon", action="store_true", help="Start background security guardrail daemon")
    parser.add_argument("--verify-log", dest="verify_log", nargs="?", const="", help="Verify cryptographic audit log integrity")
    parser.add_argument("--policy", dest="policy_file", type=str, help="Path to custom security_policy.json")
    parser.add_argument("--audit-log", dest="audit_log_file", type=str, help="Path to custom audit log file")
    parser.add_argument("--cwd", dest="cwd", type=str, default="/workspace", help="Current working directory context")

    args = parser.parse_args()
    daemon = SecurityDaemon(policy_path=args.policy_file, audit_log_path=args.audit_log_file)

    if args.eval_cmd:
        res = daemon.evaluate(args.eval_cmd, cwd=args.cwd)
        print(res.to_json())
        sys.exit(0 if res.allowed else 1)

    elif args.eval_syscall:
        res = daemon.evaluate_syscall(args.eval_syscall)
        print(res.to_json())
        sys.exit(0 if res.allowed else 1)

    elif args.exec_cmd:
        success, code, out, err = daemon.execute_with_guardrails(args.exec_cmd, cwd=args.cwd)
        if out:
            print(out, end="")
        if err:
            print(err, file=sys.stderr, end="")
        sys.exit(code)

    elif args.verify_log is not None:
        target_log = args.verify_log if args.verify_log else daemon.audit_logger.log_path
        valid, count, violations = AuditLogger.verify_audit_log(target_log)
        print("=" * 60)
        print(f"Audit Trail Verification: {target_log}")
        print("=" * 60)
        print(f"Status:             {'VALID [PASS]' if valid else 'COMPROMISED / INVALID [FAIL]'}")
        print(f"Verified Records:   {count}")
        if violations:
            print("\nSecurity Violations / Tampering Discrepancies:")
            for v in violations:
                print(f"  [!] {v}")
            sys.exit(1)
        else:
            print("Cryptographic Hash Chain: INTACT & UNBROKEN")
            sys.exit(0)

    elif args.daemon:
        daemon.run_daemon_server()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
