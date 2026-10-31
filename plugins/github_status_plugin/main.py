#!/usr/bin/env python3
"""
main.py - GitHub & Repository Status Plugin for AI OS
Author: AI OS DevOps Team

Checks GitHub infrastructure status (API, Git Operations, Webhooks, Actions)
and queries active repository state (current branch, commit history, dirty status).
Handles offline execution gracefully with cached/local fallback data.
"""

import os
import sys
import json
import urllib.request
import urllib.error
from typing import Dict, Any


def execute(context) -> Dict[str, Any]:
    """
    Standard Plugin Entrypoint invoked by PluginManager.
    :param context: PluginContext providing sandboxed runner, logger, config, and permissions.
    :return: dict with 'success', 'content', and optional 'data'.
    """
    context.logger.info("GitHub Status Plugin execution initiated.")

    config = context.config or {}
    endpoint = config.get("status_endpoint", "https://www.githubstatus.com/api/v2/status.json")
    timeout = config.get("timeout_seconds", 4)

    # 1. Fetch GitHub Global Service Status (if network permission granted)
    service_status = "UNKNOWN"
    service_desc = "No network response"
    components_info = []

    if context.has_permission("network"):
        try:
            req = urllib.request.Request(
                endpoint,
                headers={"User-Agent": "AI-OS-Plugin-System/1.0", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    service_status = data.get("status", {}).get("indicator", "none").upper()
                    service_desc = data.get("status", {}).get("description", "All Systems Operational")
        except Exception as e:
            context.logger.warn(f"GitHub Status API unavailable or offline: {e}")
            service_status = "OFFLINE"
            service_desc = "Offline mode - Cannot reach githubstatus.com"
    else:
        service_status = "RESTRICTED"
        service_desc = "Network permission not granted to plugin"

    # 2. Query Local Repository Status via sandboxed runner
    repo_branch = "N/A"
    repo_status_summary = "Not inside a Git repository"
    recent_commits = []

    if context.has_permission("execute_command"):
        # Check current branch
        code, branch_out, _ = context.runner.run("git rev-parse --abbrev-ref HEAD")
        if code == 0 and branch_out.strip():
            repo_branch = branch_out.strip()

            # Check status
            _, st_out, _ = context.runner.run("git status --short")
            modified_count = len([l for l in st_out.splitlines() if l.strip()])
            repo_status_summary = "Clean working directory" if modified_count == 0 else f"{modified_count} uncommitted modification(s)"

            # Check recent commits
            _, log_out, _ = context.runner.run("git log -n 3 --pretty=format:%h|%an|%s")
            for line in log_out.splitlines():
                parts = line.split("|")
                if len(parts) >= 3:
                    recent_commits.append({"sha": parts[0], "author": parts[1], "message": parts[2]})

    # Format human-readable output report
    indicator_badge = "[OPERATIONAL]" if service_status in ("NONE", "OPERATIONAL") else ("[STATUS]" if service_status == "MINOR" else "[OFFLINE]")
    report_lines = [
        "### GitHub & Repository Status Report",
        f"- **GitHub Cloud Status:** {indicator_badge} `{service_status}` ({service_desc})",
        f"- **Local Active Branch:** `{repo_branch}`",
        f"- **Working Tree Status:** {repo_status_summary}"
    ]

    if recent_commits:
        report_lines.append("\n**Recent Commits:**")
        for c in recent_commits:
            report_lines.append(f"  • [`{c['sha']}`] **{c['author']}**: {c['message']}")

    report_lines.append("\n*Report generated autonomously by `github_status_plugin`.*")

    return {
        "success": True,
        "content": "\n".join(report_lines),
        "data": {
            "github_service_status": service_status,
            "github_service_description": service_desc,
            "branch": repo_branch,
            "working_tree": repo_status_summary,
            "recent_commits": recent_commits
        }
    }
