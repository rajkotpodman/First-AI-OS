#!/usr/bin/env python3
"""
test_security_daemon.py - Unit tests for Fine-Grained Security Guardrails & Permission Subsystem
Author: Linux Security Architect and System Auditor
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure src/ is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from security_daemon import (
    RiskLevel,
    ApprovalStatus,
    ExecutionOutcome,
    EvaluationResult,
    AuditEntry,
    AuditLogger,
    BoundaryEnforcer,
    SecurityEvaluator,
    SecurityDaemon,
    GENESIS_HASH
)


class TestRiskLevelClassification(unittest.TestCase):
    """Verifies that shell commands and actions are categorized into correct risk tiers."""

    def setUp(self):
        self.evaluator = SecurityEvaluator()

    # --------------------------------------------------------------------------
    # LOW Risk Tier (Auto-approve read-only)
    # --------------------------------------------------------------------------
    def test_low_risk_read_only_commands(self):
        low_commands = [
            "ls -la /workspace",
            "cat /workspace/README.md",
            "grep -rn 'TODO' /workspace",
            "ps aux",
            "df -h",
            "du -sh /workspace",
            "pwd",
            "whoami",
            "uname -a",
            "uptime",
            "head -n 20 /workspace/main.py",
            "tail -f /workspace/app.log",
            "wc -l /workspace/data.csv",
            "find /workspace -name '*.py'"
        ]
        for cmd in low_commands:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.LOW, f"Command '{cmd}' should be LOW risk")
                self.assertEqual(res.approval_status, ApprovalStatus.AUTO_APPROVED)
                self.assertTrue(res.allowed)

    # --------------------------------------------------------------------------
    # MEDIUM Risk Tier (Notify: non-destructive writes & safe installs)
    # --------------------------------------------------------------------------
    def test_medium_risk_safe_workspace_writes(self):
        medium_commands = [
            "mkdir -p /workspace/build",
            "touch /workspace/new_module.py",
            "cp /workspace/fileA.txt /workspace/fileB.txt",
            "echo 'Hello World' > /workspace/output.txt",
            "git status",
            "python3 /workspace/script.py"
        ]
        for cmd in medium_commands:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.MEDIUM, f"Command '{cmd}' should be MEDIUM risk")
                self.assertEqual(res.approval_status, ApprovalStatus.NOTIFIED_ALLOWED)
                self.assertTrue(res.allowed)

    def test_medium_risk_safe_package_installs(self):
        package_installs = [
            "apk add curl python3",
            "apt-get install nginx",
            "pip install fastapi uvicorn",
            "npm install express",
            "cargo install ripgrep"
        ]
        for cmd in package_installs:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.MEDIUM, f"Command '{cmd}' should be MEDIUM risk")
                self.assertEqual(res.approval_status, ApprovalStatus.NOTIFIED_ALLOWED)
                self.assertTrue(res.allowed)

    # --------------------------------------------------------------------------
    # HIGH Risk Tier (Requires explicit user prompt)
    # --------------------------------------------------------------------------
    def test_high_risk_root_operations(self):
        root_commands = [
            "sudo apt-get update",
            "su - root",
            "doas apk upgrade",
            "chroot /mnt /bin/sh"
        ]
        for cmd in root_commands:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.HIGH, f"Command '{cmd}' should be HIGH risk")
                self.assertTrue(res.requires_prompt)
                self.assertFalse(res.allowed)

    def test_high_risk_package_removals(self):
        removal_commands = [
            "apk del alpine-base",
            "apt-get remove python3",
            "apt-get purge nginx",
            "dpkg -r openssh-server",
            "pacman -R linux"
        ]
        for cmd in removal_commands:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.HIGH, f"Command '{cmd}' should be HIGH risk")
                self.assertTrue(res.requires_prompt)

    def test_high_risk_network_socket_changes(self):
        net_commands = [
            "iptables -A INPUT -p tcp --dport 22 -j DROP",
            "nft add rule inet filter input drop",
            "ip route add default via 10.0.0.1",
            "ifconfig eth0 down"
        ]
        for cmd in net_commands:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.HIGH, f"Command '{cmd}' should be HIGH risk")
                self.assertTrue(res.requires_prompt)

    def test_high_risk_disk_and_destructive_deletions(self):
        destructive_commands = [
            "rm -rf /workspace/project",
            "rm /workspace/temp.txt",
            "fdisk /dev/sdb",
            "parted /dev/sdb",
            "kill -9 4567",
            "pkill node",
            "systemctl restart sshd"
        ]
        for cmd in destructive_commands:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.HIGH, f"Command '{cmd}' should be HIGH risk")
                self.assertTrue(res.requires_prompt)

    # --------------------------------------------------------------------------
    # BLOCKED Tier (Zero-Tolerance Catastrophic Disasters)
    # --------------------------------------------------------------------------
    def test_blocked_catastrophic_commands(self):
        catastrophic_commands = [
            "rm -rf /",
            "rm -rf /*",
            "rm -rf --no-preserve-root /",
            "mkfs.ext4 /dev/sda",
            "mkfs /dev/nvme0n1",
            "dd if=/dev/zero of=/dev/sda bs=1M",
            "> /dev/sda",
            ":(){ :|:& };:",
            "kill -9 1",
            "chmod -R 777 /"
        ]
        for cmd in catastrophic_commands:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.BLOCKED, f"Command '{cmd}' must be BLOCKED")
                self.assertEqual(res.approval_status, ApprovalStatus.BLOCKED_DISALLOWED)
                self.assertFalse(res.allowed)


class TestPathTraversalAndBoundaryEnforcement(unittest.TestCase):
    """Verifies strict boundary enforcement, directory isolation, and traversal blocking."""

    def setUp(self):
        self.evaluator = SecurityEvaluator()
        self.enforcer = self.evaluator.enforcer

    def test_critical_host_directory_modifications_blocked(self):
        critical_writes = [
            "touch /boot/vmlinuz-evil",
            "rm /etc/shadow",
            "mkdir /lib/modules/rootkit",
            "mkdir /lib64/trojan",
            "echo 'hacked' > /etc/shadow",
            "cp /workspace/lib.so /lib/",
            "rm -rf /usr/bin",
            "touch /dev/shm_exploit",
            "mkdir /root/.ssh"
        ]
        for cmd in critical_writes:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.BLOCKED, f"Write to critical dir '{cmd}' must be BLOCKED")
                self.assertFalse(res.allowed)
                self.assertTrue(len(res.critical_violations) > 0)

    def test_path_traversal_escaping_workspace_blocked(self):
        traversal_attacks = [
            "touch /workspace/../../etc/shadow",
            "rm -rf /workspace/../../boot",
            "echo 'evil' > /workspace/subdir/../../../etc/passwd",
            "mkdir /workspace/../etc/cron.d/evil_cron",
            "touch /workspace/sub/../../lib/exploit.so"
        ]
        for cmd in traversal_attacks:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.BLOCKED, f"Traversal attack '{cmd}' must be BLOCKED")
                self.assertFalse(res.allowed)

    def test_unauthorized_host_writes_blocked(self):
        unauthorized_writes = [
            "mkdir /opt/unauthorized",
            "touch /var/log/fake.log",
            "echo 'test' > /tmp_unallowed/out.txt"
        ]
        for cmd in unauthorized_writes:
            with self.subTest(command=cmd):
                res = self.evaluator.evaluate_command(cmd, cwd="/workspace")
                self.assertEqual(res.risk_level, RiskLevel.BLOCKED, f"Out of boundary write '{cmd}' must be BLOCKED")
                self.assertFalse(res.allowed)

    def test_authorized_workspace_boundary_resolution(self):
        valid_paths = [
            "/workspace/src/app.py",
            "/workspace/data/cache.json",
            "/home/user/workspace/test.txt"
        ]
        for p in valid_paths:
            in_bounds, _ = self.enforcer.is_within_allowed_boundary(p, cwd="/workspace")
            self.assertTrue(in_bounds, f"Path '{p}' should be within allowed boundary")


class TestTamperEvidentAuditTrail(unittest.TestCase):
    """Verifies cryptographic hash-chaining and audit log tamper detection."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.log_file = os.path.join(self.tmp_dir.name, "test_audit.log")
        self.logger = AuditLogger(log_path=self.log_file)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_audit_log_hash_chain_creation(self):
        # Log 3 events
        e1 = self.logger.log_event(
            command="ls -la",
            risk_level=RiskLevel.LOW,
            approval_status=ApprovalStatus.AUTO_APPROVED,
            execution_outcome=ExecutionOutcome.SUCCESS
        )
        self.assertEqual(e1.entry_id, 1)
        self.assertEqual(e1.prev_hash, GENESIS_HASH)

        e2 = self.logger.log_event(
            command="mkdir /workspace/test",
            risk_level=RiskLevel.MEDIUM,
            approval_status=ApprovalStatus.NOTIFIED_ALLOWED,
            execution_outcome=ExecutionOutcome.SUCCESS
        )
        self.assertEqual(e2.entry_id, 2)
        self.assertEqual(e2.prev_hash, e1.entry_hash)

        e3 = self.logger.log_event(
            command="rm -rf /workspace/test",
            risk_level=RiskLevel.HIGH,
            approval_status=ApprovalStatus.USER_APPROVED,
            execution_outcome=ExecutionOutcome.SUCCESS
        )
        self.assertEqual(e3.entry_id, 3)
        self.assertEqual(e3.prev_hash, e2.entry_hash)

        # Mathematical verification of valid chain
        is_valid, count, violations = AuditLogger.verify_audit_log(self.log_file)
        self.assertTrue(is_valid)
        self.assertEqual(count, 3)
        self.assertEqual(violations, [])

    def test_tamper_detection_modified_entry_payload(self):
        # Create events
        self.logger.log_event("cat /workspace/a", RiskLevel.LOW, ApprovalStatus.AUTO_APPROVED, ExecutionOutcome.SUCCESS)
        self.logger.log_event("rm -rf /", RiskLevel.BLOCKED, ApprovalStatus.BLOCKED_DISALLOWED, ExecutionOutcome.BLOCKED)

        # Adversary attempts to tamper with record #2 (changing BLOCKED to AUTO_APPROVED)
        with open(self.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        tampered_entry = json.loads(lines[1])
        tampered_entry["approval_status"] = ApprovalStatus.AUTO_APPROVED.value
        lines[1] = json.dumps(tampered_entry) + "\n"

        with open(self.log_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        is_valid, count, violations = AuditLogger.verify_audit_log(self.log_file)
        self.assertFalse(is_valid, "Tampered payload must fail verification")
        self.assertTrue(any("Cryptographic tampering detected" in v for v in violations))

    def test_tamper_detection_deleted_entry(self):
        # Create 3 events
        self.logger.log_event("cmd1", RiskLevel.LOW, ApprovalStatus.AUTO_APPROVED, ExecutionOutcome.SUCCESS)
        self.logger.log_event("cmd2", RiskLevel.HIGH, ApprovalStatus.USER_DENIED, ExecutionOutcome.DENIED)
        self.logger.log_event("cmd3", RiskLevel.LOW, ApprovalStatus.AUTO_APPROVED, ExecutionOutcome.SUCCESS)

        # Delete middle entry (cmd2)
        with open(self.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Remove line 2
        del lines[1]
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        is_valid, count, violations = AuditLogger.verify_audit_log(self.log_file)
        self.assertFalse(is_valid, "Missing middle entry must break hash chain")
        self.assertTrue(any("Hash chain link broken" in v for v in violations))


class TestSyscallGuardrails(unittest.TestCase):
    """Verifies kernel system call evaluation against security policies."""

    def setUp(self):
        self.evaluator = SecurityEvaluator()

    def test_blocked_dangerous_syscalls(self):
        blocked_syscalls = [
            "reboot", "kexec_load", "init_module", "delete_module",
            "bpf", "swapon", "swapoff", "sys_chroot", "ptrace"
        ]
        for sc in blocked_syscalls:
            with self.subTest(syscall=sc):
                res = self.evaluator.evaluate_syscall(sc)
                self.assertEqual(res.risk_level, RiskLevel.BLOCKED)
                self.assertFalse(res.allowed)

    def test_high_risk_privileged_syscalls(self):
        high_syscalls = ["mount", "umount2", "setuid", "setgid", "kill", "unlink", "unlinkat"]
        for sc in high_syscalls:
            with self.subTest(syscall=sc):
                res = self.evaluator.evaluate_syscall(sc)
                self.assertEqual(res.risk_level, RiskLevel.HIGH)
                self.assertTrue(res.requires_prompt)

    def test_low_risk_syscalls(self):
        low_syscalls = ["read", "stat", "fstat", "access", "getcwd"]
        for sc in low_syscalls:
            with self.subTest(syscall=sc):
                res = self.evaluator.evaluate_syscall(sc)
                self.assertEqual(res.risk_level, RiskLevel.LOW)
                self.assertTrue(res.allowed)


class TestSecurityDaemonExecution(unittest.TestCase):
    """Verifies end-to-end execution workflow, prompting callbacks, and audit capture."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.log_file = os.path.join(self.tmp_dir.name, "exec_audit.log")
        self.daemon = SecurityDaemon(audit_log_path=self.log_file)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_blocked_command_execution_prevented(self):
        executed, code, out, err = self.daemon.execute_with_guardrails(
            "rm -rf /", cwd=self.tmp_dir.name, interactive=False
        )
        self.assertFalse(executed)
        self.assertEqual(code, -1)
        self.assertIn("SECURITY VIOLATION", err)

        # Ensure recorded as BLOCKED in audit log
        is_valid, count, _ = AuditLogger.verify_audit_log(self.log_file)
        self.assertTrue(is_valid)
        self.assertEqual(count, 1)

    def test_high_risk_command_prompt_denied(self):
        # User rejects approval
        executed, code, out, err = self.daemon.execute_with_guardrails(
            "sudo systemctl restart nginx",
            user_approval_callback=lambda res: False,
            interactive=False
        )
        self.assertFalse(executed)
        self.assertEqual(code, -2)
        self.assertIn("GUARDRAIL DENIED", err)

    def test_high_risk_command_prompt_approved(self):
        # User approves execution
        with patch("subprocess.run") as mock_proc:
            mock_proc.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
            executed, code, out, err = self.daemon.execute_with_guardrails(
                "sudo systemctl restart nginx",
                cwd=self.tmp_dir.name,
                user_approval_callback=lambda res: True,
                interactive=False
            )
            self.assertTrue(executed)
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
