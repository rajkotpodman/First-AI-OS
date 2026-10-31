#!/usr/bin/env python3
"""
system_updater.py - Root wrapper for AI OS System Maintenance & Rollback Engine
"""
import os
import sys

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from system_updater import (
    SnapshotManifest,
    HealthCheckReport,
    SystemUpdater,
    main
)

if __name__ == "__main__":
    main()
