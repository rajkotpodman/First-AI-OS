#!/usr/bin/env python3
"""
ai_plugin.py - Extension & Plugin Manager CLI Tool for AI OS
Author: Software Platform Architect and Plugin Framework Engineer

CLI Usage:
  ai-plugin list
  ai-plugin info <plugin_name>
  ai-plugin run <plugin_name> [args...]
  ai-plugin enable <plugin_name>
  ai-plugin disable <plugin_name>
  ai-plugin install <path_to_plugin_folder>
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from plugin_manager import PluginManager, USER_PLUGINS_DIR, LOCAL_PLUGINS_DIR

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
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
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
def cmd_list(pm: PluginManager, as_json: bool = False):
    plugins = pm.list_plugins()
    if as_json:
        print(json.dumps(plugins, indent=2))
        return

    if not plugins:
        print(f"{Colors.YELLOW}[!] No plugins found in plugin search paths.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI OS EXTENSIONS & PLUGINS ({len(plugins)} INSTALLED) ==={Colors.RESET}\n")

    headers = ["Plugin Name", "Ver", "Status", "Triggers", "Permissions", "Description"]
    rows = []

    for p in plugins:
        status_badge = f"{Colors.GREEN}ACTIVE{Colors.RESET}" if p.get("enabled", True) else f"{Colors.DIM}DISABLED{Colors.RESET}"
        trigs = ", ".join(p.get("triggers", [])[:3])
        if len(p.get("triggers", [])) > 3:
            trigs += "..."
        perms = ", ".join(p.get("permissions", []))

        rows.append([
            f"{Colors.MAGENTA}{p['name']}{Colors.RESET}",
            f"{Colors.DIM}{p['version']}{Colors.RESET}",
            status_badge,
            f"{Colors.YELLOW}{trigs}{Colors.RESET}",
            f"{Colors.BLUE}{perms}{Colors.RESET}",
            f"{p.get('description', '')[:30]}"
        ])

    print(format_table(headers, rows))
    print(f"\n{Colors.DIM}Plugin directories: {', '.join(str(d) for d in pm.plugin_dirs)}{Colors.RESET}\n")


def cmd_info(pm: PluginManager, plugin_name: str):
    if plugin_name not in pm.plugins:
        print(f"{Colors.RED}[!] Plugin '{plugin_name}' is not loaded.{Colors.RESET}")
        return

    p = pm.plugins[plugin_name].manifest
    print(f"\n{Colors.BOLD}{Colors.CYAN}=== PLUGIN METADATA: {p.name} ==={Colors.RESET}")
    print(f"  {Colors.BOLD}Name:{Colors.RESET}        {p.name}")
    print(f"  {Colors.BOLD}Version:{Colors.RESET}     {p.version}")
    print(f"  {Colors.BOLD}Author:{Colors.RESET}      {p.author}")
    print(f"  {Colors.BOLD}Directory:{Colors.RESET}   {p.plugin_dir}")
    print(f"  {Colors.BOLD}Entrypoint:{Colors.RESET}  {p.entrypoint}")
    print(f"  {Colors.BOLD}Enabled:{Colors.RESET}     {'Yes' if p.enabled else 'No'}")
    print(f"  {Colors.BOLD}Triggers:{Colors.RESET}    {', '.join(p.triggers)}")
    print(f"  {Colors.BOLD}Permissions:{Colors.RESET} {', '.join(p.permissions)}")
    print(f"  {Colors.BOLD}Description:{Colors.RESET} {p.description}")
    if p.config:
        print(f"  {Colors.BOLD}Config:{Colors.RESET}      {json.dumps(p.config)}")
    print()


def cmd_run(pm: PluginManager, plugin_name: str, args: list):
    res = pm.execute_by_name(plugin_name, args=args)
    if res.success:
        print(f"\n{res.content}\n")
    else:
        print(f"{Colors.RED}[!] Plugin execution failed:{Colors.RESET} {res.content}")


def cmd_toggle(pm: PluginManager, plugin_name: str, enable: bool):
    if plugin_name not in pm.plugins:
        print(f"{Colors.RED}[!] Plugin '{plugin_name}' not found.{Colors.RESET}")
        return

    p = pm.plugins[plugin_name].manifest
    manifest_file = p.plugin_dir / "manifest.json"
    if manifest_file.exists():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            data["enabled"] = enable
            manifest_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            state_str = "enabled" if enable else "disabled"
            print(f"{Colors.GREEN}[OK] Plugin '{plugin_name}' {state_str}.{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[!] Failed modifying manifest: {e}{Colors.RESET}")


def cmd_install(source_path: str):
    src = Path(source_path).resolve()
    if not src.exists() or not src.is_dir():
        print(f"{Colors.RED}[!] Plugin source folder does not exist: {source_path}{Colors.RESET}")
        return

    manifest_file = src / "manifest.json"
    if not manifest_file.exists():
        print(f"{Colors.RED}[!] Source folder missing 'manifest.json'.{Colors.RESET}")
        return

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        p_name = data.get("name", src.name)
        target_dir = Path(USER_PLUGINS_DIR) / p_name
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(src, target_dir)
        print(f"{Colors.GREEN}[OK] Successfully installed plugin '{p_name}' to {target_dir}{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}[!] Plugin installation failed: {e}{Colors.RESET}")


def main():
    parser = argparse.ArgumentParser(
        prog="ai-plugin",
        description="Modular Extension & Plugin Manager for AI OS"
    )
    subparsers = parser.add_subparsers(dest="command")

    # list
    p_list = subparsers.add_parser("list", help="List all installed plugins and permissions")
    p_list.add_argument("--json", action="store_true", help="Output raw JSON array")

    # info
    p_info = subparsers.add_parser("info", help="Show detailed plugin metadata and permissions")
    p_info.add_argument("name", help="Plugin name")

    # run
    p_run = subparsers.add_parser("run", help="Execute a plugin directly")
    p_run.add_argument("name", help="Plugin name")
    p_run.add_argument("args", nargs="*", help="Optional arguments for the plugin")

    # enable & disable
    p_en = subparsers.add_parser("enable", help="Enable a plugin")
    p_en.add_argument("name", help="Plugin name")

    p_dis = subparsers.add_parser("disable", help="Disable a plugin")
    p_dis.add_argument("name", help="Plugin name")

    # install
    p_inst = subparsers.add_parser("install", help="Install a plugin from directory")
    p_inst.add_argument("path", help="Path to plugin directory containing manifest.json")

    args = parser.parse_args()
    pm = PluginManager()

    if not args.command or args.command == "list":
        cmd_list(pm, as_json=getattr(args, "json", False))
    elif args.command == "info":
        cmd_info(pm, args.name)
    elif args.command == "run":
        cmd_run(pm, args.name, args.args)
    elif args.command == "enable":
        cmd_toggle(pm, args.name, True)
    elif args.command == "disable":
        cmd_toggle(pm, args.name, False)
    elif args.command == "install":
        cmd_install(args.path)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
