#!/usr/bin/env python3
"""
security_daemon.py - Root wrapper for AI OS Security Guardrail & Permission Manager Subsystem
"""
import os
import sys

# Add src to python path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
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
    main
)

if __name__ == "__main__":
    main()
