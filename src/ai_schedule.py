#!/usr/bin/env python3
"""
ai_schedule.py - Task Manager CLI Tool for AI OS Background Cron Scheduler
Author: Linux System Daemon Architect and Automation Engineer

CLI Usage:
  ai-schedule list
  ai-schedule add "Nightly Maintenance" --schedule "Every day at 2 AM" --type system_care
  ai-schedule run <task_id>
  ai-schedule pause <task_id>
  ai-schedule resume <task_id>
  ai-schedule remove <task_id>
  ai-schedule status
  ai-schedule logs [--tail <lines>]
  ai-schedule notifications
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ai_cron_daemon import AICronDaemon, ScheduleParser, NotificationHub

# ==============================================================================
# ANSI Color Palette
# ==============================================================================
class Colors:
    CYAN = "\033[1;36m"
    BLUE = "\033[1;34m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    MAGENTA = "\033[1;35m"
    RED = "\033[1;31m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def format_table(headers: list, rows: list) -> str:
    """Formats rows into an aligned ANSI terminal table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            # Strip ANSI codes when calculating width
            raw = re_strip_ansi(str(cell))
            if len(raw) > col_widths[idx]:
                col_widths[idx] = len(raw)

    def row_str(cells, is_header=False):
        parts = []
        for idx, cell in enumerate(cells):
            raw = re_strip_ansi(str(cell))
            padding = " " * (col_widths[idx] - len(raw))
            if is_header:
                parts.append(f"{Colors.BOLD}{Colors.CYAN}{cell}{Colors.RESET}{padding}")
            else:
                parts.append(f"{cell}{padding}")
        return " | ".join(parts)

    divider = "-+-".join(["-" * w for w in col_widths])
    lines = [row_str(headers, is_header=True), divider]
    for r in rows:
        lines.append(row_str(r))
    return "\n".join(lines)


def re_strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\033\[[0-9;]*m", "", text)


# ==============================================================================
# CLI Actions
# ==============================================================================
def cmd_list(daemon: AICronDaemon, as_json: bool = False):
    tasks = daemon.load_tasks()
    if as_json:
        print(json.dumps([t.to_dict() for t in tasks], indent=2))
        return

    if not tasks:
        print(f"{Colors.YELLOW}[!] No scheduled tasks configured. Use 'ai-schedule add' to create one.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI OS SCHEDULED TASKS ({len(tasks)} CONFIGURED) ==={Colors.RESET}\n")

    headers = ["ID", "Name", "Type", "Schedule", "Status", "Next Run", "Last Run"]
    rows = []

    for t in tasks:
        status_color = Colors.GREEN if t.enabled else Colors.DIM
        status_txt = f"{status_color}{'ACTIVE' if t.enabled else 'PAUSED'}{Colors.RESET}"

        last_st = t.last_status.upper()
        if last_st == "SUCCESS":
            status_txt += f" {Colors.GREEN}(OK){Colors.RESET}"
        elif last_st == "FAILED":
            status_txt += f" {Colors.RED}(FAIL){Colors.RESET}"

        next_str = t.next_run[:16].replace("T", " ") if t.next_run else "N/A"
        last_str = t.last_run[:16].replace("T", " ") if t.last_run else "Never"

        rows.append([
            f"{Colors.MAGENTA}{t.id}{Colors.RESET}",
            f"{Colors.BOLD}{t.name[:25]}{Colors.RESET}",
            f"{Colors.BLUE}{t.task_type}{Colors.RESET}",
            f"{Colors.YELLOW}{t.natural_schedule[:22]}{Colors.RESET}",
            status_txt,
            f"{Colors.DIM}{next_str}{Colors.RESET}",
            f"{Colors.DIM}{last_str}{Colors.RESET}"
        ])

    print(format_table(headers, rows))
    print(f"\n{Colors.DIM}Tasks Config: {daemon.tasks_path}{Colors.RESET}\n")


def cmd_add(daemon: AICronDaemon, args):
    config = {}
    if args.config:
        try:
            config = json.loads(args.config)
        except Exception as e:
            print(f"{Colors.RED}[!] Invalid JSON config: {e}{Colors.RESET}")
            sys.exit(1)

    task = daemon.add_task(
        name=args.name,
        schedule_input=args.schedule,
        task_type=args.type,
        config=config,
        task_id=args.id
    )

    print(f"\n{Colors.GREEN}[OK] Successfully scheduled task:{Colors.RESET}")
    print(f"  {Colors.BOLD}ID:{Colors.RESET}       {task.id}")
    print(f"  {Colors.BOLD}Name:{Colors.RESET}     {task.name}")
    print(f"  {Colors.BOLD}Type:{Colors.RESET}     {task.task_type}")
    print(f"  {Colors.BOLD}Schedule:{Colors.RESET} {task.schedule} ({Colors.YELLOW}{task.natural_schedule}{Colors.RESET})")
    print(f"  {Colors.BOLD}Next Run:{Colors.RESET} {task.next_run}\n")


def cmd_run(daemon: AICronDaemon, task_id: str):
    tasks = daemon.load_tasks()
    match = [t for t in tasks if t.id == task_id]
    if not match:
        print(f"{Colors.RED}[!] Task not found with ID '{task_id}'.{Colors.RESET}")
        return

    task = match[0]
    print(f"{Colors.BLUE}[*] Triggering immediate execution of task: '{task.name}'...{Colors.RESET}")
    success, output = daemon.execute_task(task)

    # Update metadata
    now = datetime.now()
    task.last_run = now.isoformat()
    task.run_count += 1
    task.last_status = "success" if success else "failed"
    task.last_output = output
    task.next_run = ScheduleParser.calculate_next_run(task.schedule, from_dt=now).isoformat()
    daemon.save_tasks(tasks)

    if success:
        print(f"{Colors.GREEN}[OK] Task completed successfully!{Colors.RESET}")
        print(f"  Output: {output}")
    else:
        print(f"{Colors.RED}[!] Task failed:{Colors.RESET} {output}")


def cmd_toggle(daemon: AICronDaemon, task_id: str, enable: bool):
    ok = daemon.toggle_task(task_id, enable)
    if ok:
        action = "resumed (enabled)" if enable else "paused (disabled)"
        print(f"{Colors.GREEN}[OK] Task '{task_id}' {action}.{Colors.RESET}")
    else:
        print(f"{Colors.RED}[!] Task with ID '{task_id}' not found.{Colors.RESET}")


def cmd_remove(daemon: AICronDaemon, task_id: str):
    ok = daemon.remove_task(task_id)
    if ok:
        print(f"{Colors.GREEN}[OK] Task '{task_id}' removed successfully.{Colors.RESET}")
    else:
        print(f"{Colors.RED}[!] Task with ID '{task_id}' not found.{Colors.RESET}")


def cmd_status(daemon: AICronDaemon):
    tasks = daemon.load_tasks()
    active_count = len([t for t in tasks if t.enabled])
    paused_count = len(tasks) - active_count

    pid = None
    is_running = False
    if daemon.pid_path.exists():
        try:
            pid = int(daemon.pid_path.read_text().strip())
            # Check if process is alive
            if sys.platform == "win32":
                # Basic check
                is_running = True
            else:
                os.kill(pid, 0)
                is_running = True
        except Exception:
            is_running = False

    print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI CRON DAEMON STATUS ==={Colors.RESET}")
    status_str = f"{Colors.GREEN}RUNNING (PID: {pid}){Colors.RESET}" if is_running else f"{Colors.YELLOW}INACTIVE / STANDALONE{Colors.RESET}"
    print(f"  Daemon Service:     {status_str}")
    print(f"  Tasks File:         {daemon.tasks_path}")
    print(f"  Log File:           {daemon.log_path}")
    print(f"  Notification Queue: {daemon.notifications.path}")
    print(f"  Configured Tasks:   {len(tasks)} ({active_count} active, {paused_count} paused)\n")


def cmd_logs(daemon: AICronDaemon, tail_count: int = 20):
    if not daemon.log_path.exists():
        print(f"{Colors.YELLOW}[!] Log file does not exist yet at {daemon.log_path}.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI CRON DAEMON LOGS (LAST {tail_count} LINES) ==={Colors.RESET}\n")
    try:
        lines = daemon.log_path.read_text(encoding="utf-8").splitlines()
        for line in lines[-tail_count:]:
            try:
                rec = json.loads(line)
                lvl = rec.get("level", "INFO")
                color = Colors.GREEN if lvl == "INFO" else (Colors.RED if lvl in ("ERROR", "CRITICAL") else Colors.YELLOW)
                print(f"{Colors.DIM}{rec.get('timestamp')}{Colors.RESET} [{color}{lvl}{Colors.RESET}] {rec.get('message')}")
            except Exception:
                print(line)
        print()
    except Exception as e:
        print(f"{Colors.RED}[!] Error reading logs: {e}{Colors.RESET}")


def cmd_notifications(daemon: AICronDaemon):
    hub = daemon.notifications
    items = hub.get_all()
    if not items:
        print(f"{Colors.YELLOW}[!] No completion notifications in queue.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI OS TERMINAL NOTIFICATIONS ({len(items)} RECENT) ==={Colors.RESET}\n")
    for item in items[:15]:
        lvl = item.get("level", "info")
        color = Colors.GREEN if lvl == "success" else (Colors.RED if lvl == "error" else Colors.BLUE)
        read_badge = f"{Colors.DIM}[read]{Colors.RESET}" if item.get("read") else f"{Colors.BOLD}{Colors.YELLOW}[NEW]{Colors.RESET}"
        print(f"  {read_badge} {color}{item.get('title')}{Colors.RESET} ({Colors.DIM}{item.get('timestamp', '')[:16]}{Colors.RESET})")
        print(f"      {item.get('message')}\n")
    hub.mark_all_read()


# ==============================================================================
# Main Parser & Subcommand Dispatch
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        prog="ai-schedule",
        description="Autonomous Task Scheduler & Background Cron Manager for AI OS"
    )
    subparsers = parser.add_subparsers(dest="command")

    # list
    p_list = subparsers.add_parser("list", help="List all scheduled background tasks")
    p_list.add_argument("--json", action="store_true", help="Output raw JSON array")

    # add
    p_add = subparsers.add_parser("add", help="Schedule a new background AI task")
    p_add.add_argument("name", help="Human-readable task name")
    p_add.add_argument("--schedule", "-s", required=True, help="Cron syntax or natural schedule (e.g. '0 2 * * *' or 'Every day at 2 AM')")
    p_add.add_argument("--type", "-t", default="system_care", choices=["system_care", "project_health", "research_scrape", "custom_command"], help="Task category")
    p_add.add_argument("--config", "-c", help="Task configuration JSON string")
    p_add.add_argument("--id", help="Optional explicit task ID")

    # run
    p_run = subparsers.add_parser("run", help="Trigger a task immediately")
    p_run.add_argument("task_id", help="ID of the task to execute")

    # pause & resume
    p_pause = subparsers.add_parser("pause", help="Pause a scheduled task")
    p_pause.add_argument("task_id", help="ID of the task to pause")

    p_resume = subparsers.add_parser("resume", help="Resume a paused task")
    p_resume.add_argument("task_id", help="ID of the task to resume")

    # remove
    p_rm = subparsers.add_parser("remove", help="Remove a scheduled task")
    p_rm.add_argument("task_id", help="ID of the task to delete")

    # status
    subparsers.add_parser("status", help="Show daemon PID and scheduler status")

    # logs
    p_logs = subparsers.add_parser("logs", help="Display daemon execution logs")
    p_logs.add_argument("--tail", "-n", type=int, default=20, help="Number of lines to show")

    # notifications
    subparsers.add_parser("notifications", help="View task completion notifications")

    args = parser.parse_args()
    daemon = AICronDaemon()

    if not args.command or args.command == "list":
        cmd_list(daemon, as_json=getattr(args, "json", False))
    elif args.command == "add":
        cmd_add(daemon, args)
    elif args.command == "run":
        cmd_run(daemon, args.task_id)
    elif args.command == "pause":
        cmd_toggle(daemon, args.task_id, enable=False)
    elif args.command == "resume":
        cmd_toggle(daemon, args.task_id, enable=True)
    elif args.command == "remove":
        cmd_remove(daemon, args.task_id)
    elif args.command == "status":
        cmd_status(daemon)
    elif args.command == "logs":
        cmd_logs(daemon, tail_count=args.tail)
    elif args.command == "notifications":
        cmd_notifications(daemon)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
