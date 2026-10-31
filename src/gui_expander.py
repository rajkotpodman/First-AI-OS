#!/usr/bin/env python3
"""
gui_expander.py - On-Demand Dynamic GUI Installer & Desktop Switcher for AI OS
Author: Linux Desktop Environment & Display Server Engineer

Enables zero-to-GUI dynamic transition on-demand using Sway / Wayland, Waybar,
and Foot terminal, preserving a lightweight pure TTY CLI by default.
"""

import os
import sys
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_TEMPLATES_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "configs", "sway"))

REQUIRED_SYSTEM_PACKAGES = [
    "sway",
    "xwayland",
    "waybar",
    "foot",
    "swaybg",
    "dmenu",
    "mesa-dri-gallium",
    "dbus",
    "font-dejavu"
]

GUI_TRIGGER_PATTERNS = [
    r"\b(?:give\s+me|open|start|launch|switch\s+to|enable)\s+(?:gui|desktop|wayland|sway)\b",
    r"\b(?:i\s+need|open|launch)\s+(?:a\s+)?(?:browser|visual|graphical\s+interface)\b",
    r"^gui\s+(--enable|start|on)$"
]

GUI_DISABLE_PATTERNS = [
    r"\b(?:exit|close|stop|disable|kill|revert)\s+(?:gui|desktop|wayland|sway)\b",
    r"^gui\s+(--disable|stop|off|exit)$"
]

GRAPHICAL_APPS = {
    "chromium", "firefox", "gimp", "vlc", "feh", "code", "wireshark",
    "libreoffice", "gedit", "thunar", "pcmanfm"
}


class GUIExpander:
    """Manages on-demand Wayland/Sway installation, configuration, and session switching."""

    def __init__(self, templates_dir: Optional[str] = None):
        self.templates_dir = templates_dir or (
            CONFIG_TEMPLATES_DIR if os.path.exists(CONFIG_TEMPLATES_DIR) else "/etc/ai_os/sway"
        )

    def is_gui_trigger(self, text: str) -> bool:
        """Evaluates whether user input requests a graphical desktop."""
        text_lower = text.strip().lower()

        # Check regex phrases
        for pat in GUI_TRIGGER_PATTERNS:
            if re.search(pat, text_lower):
                return True

        # Check if launching a graphical desktop app directly
        first_token = text_lower.split()[0] if text_lower else ""
        if first_token in GRAPHICAL_APPS:
            return True

        return False

    def is_gui_disable_trigger(self, text: str) -> bool:
        """Evaluates whether user input requests terminating the GUI."""
        text_lower = text.strip().lower()
        for pat in GUI_DISABLE_PATTERNS:
            if re.search(pat, text_lower):
                return True
        return False

    def is_gui_running(self) -> bool:
        """Checks if a Wayland display server or Sway session is currently active."""
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("SWAYSOCK"):
            return True
        try:
            res = subprocess.run(["pgrep", "-x", "sway"], capture_output=True, text=True)
            return res.returncode == 0
        except Exception:
            return False

    def verify_packages(self) -> Tuple[bool, List[str]]:
        """Checks if all necessary Wayland/Sway packages and tools are installed."""
        missing = []
        for pkg in ["sway", "waybar", "foot"]:
            if not shutil.which(pkg):
                missing.append(pkg)
        return (len(missing) == 0), missing

    def install_gui_stack(self) -> bool:
        """Downloads and installs Sway, Waybar, Foot, and graphics drivers."""
        print("\033[1;36m[*] Zero-to-GUI: Installing Sway/Wayland minimal desktop stack...\033[0m")

        # Try using dependency_resolver if present
        try:
            sys.path.insert(0, SCRIPT_DIR)
            from dependency_resolver import DependencyResolver
            resolver = DependencyResolver()
            for pkg in REQUIRED_SYSTEM_PACKAGES:
                print(f"    Installing: {pkg}...")
                resolver.adapter.install_system_package(pkg)
            return True
        except Exception:
            pass

        # Fallback to direct native package manager
        pm_cmd = None
        if shutil.which("apk"):
            pm_cmd = ["apk", "add", "--no-cache"] + REQUIRED_SYSTEM_PACKAGES
        elif shutil.which("apt-get"):
            pm_cmd = ["apt-get", "install", "-y", "sway", "xwayland", "waybar", "foot", "swaybg", "dmenu"]
        elif shutil.which("pacman"):
            pm_cmd = ["pacman", "-S", "--noconfirm", "sway", "xorg-xwayland", "waybar", "foot", "swaybg", "dmenu"]

        if not pm_cmd:
            print("\033[1;31m[!] No supported package manager found to install GUI stack.\033[0m")
            return False

        if os.geteuid() != 0 if hasattr(os, "geteuid") else False:
            if shutil.which("sudo"):
                pm_cmd = ["sudo"] + pm_cmd

        try:
            res = subprocess.run(pm_cmd, check=True)
            return res.returncode == 0
        except Exception as e:
            print(f"\033[1;31m[!] Error installing GUI packages: {e}\033[0m")
            return False

    def deploy_user_configurations(self) -> bool:
        """Generates modern minimal user config files in ~/.config/."""
        home = Path.home()
        sway_dir = home / ".config" / "sway"
        waybar_dir = home / ".config" / "waybar"
        foot_dir = home / ".config" / "foot"

        sway_dir.mkdir(parents=True, exist_ok=True)
        waybar_dir.mkdir(parents=True, exist_ok=True)
        foot_dir.mkdir(parents=True, exist_ok=True)

        tmpl_path = Path(self.templates_dir)

        # 1. Sway Config
        src_sway = tmpl_path / "config"
        dst_sway = sway_dir / "config"
        if src_sway.exists():
            shutil.copyfile(src_sway, dst_sway)
        else:
            self._write_default_sway_config(dst_sway)

        # 2. Waybar Config & Style
        src_wb_cfg = tmpl_path / "waybar_config.json"
        dst_wb_cfg = waybar_dir / "config"
        if src_wb_cfg.exists():
            shutil.copyfile(src_wb_cfg, dst_wb_cfg)

        src_wb_style = tmpl_path / "waybar_style.css"
        dst_wb_style = waybar_dir / "style.css"
        if src_wb_style.exists():
            shutil.copyfile(src_wb_style, dst_wb_style)

        # 3. Foot Terminal Config
        src_foot = tmpl_path / "foot.ini"
        dst_foot = foot_dir / "foot.ini"
        if src_foot.exists():
            shutil.copyfile(src_foot, dst_foot)

        print("\033[1;32m[OK] User desktop configurations deployed (~/.config/sway, waybar, foot).\033[0m")
        return True

    def _write_default_sway_config(self, target_path: Path):
        """Fallback minimal configuration writer."""
        cfg = """set $mod Mod4
set $term foot
output * bg #0f141c solid_color
bindsym $mod+Return exec $term
bindsym $mod+Shift+q kill
bindsym $mod+Shift+e exec swaymsg exit
bar {
    swaybar_command waybar
}
"""
        target_path.write_text(cfg, encoding="utf-8")

    def enable_gui(self) -> bool:
        """Transitions system from TTY to Sway/Wayland Graphical Desktop."""
        if self.is_gui_running():
            print("\033[1;33m[!] GUI Desktop is already active.\033[0m")
            return True

        # 1. Package verification & auto-install
        installed, missing = self.verify_packages()
        if not installed:
            print(f"\033[1;33m[!] Missing GUI packages: {missing}\033[0m")
            success = self.install_gui_stack()
            if not success:
                print("\033[1;31m[!] Failed to install GUI dependencies.\033[0m")
                return False

        # 2. Deploy configs
        self.deploy_user_configurations()

        # 3. Setup runtime environment variables
        uid = os.getuid() if hasattr(os, "getuid") else 1000
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/runtime-{uid}"
        os.makedirs(xdg_runtime, exist_ok=True)
        os.chmod(xdg_runtime, 0o700)

        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = xdg_runtime
        env["WLR_NO_HARDWARE_CURSORS"] = "1"  # Vital for QEMU & VMs
        env["XDG_CURRENT_DESKTOP"] = "sway"

        print("\033[1;32m[*] Booting Wayland Compositor (dbus-run-session sway)...\033[0m")
        try:
            # Transition to GUI
            subprocess.run(["dbus-run-session", "sway"], env=env)
            print("\033[1;34m[*] Returned from Graphical Desktop to TTY.\033[0m")
            return True
        except FileNotFoundError:
            try:
                subprocess.run(["sway"], env=env)
                return True
            except Exception as e:
                print(f"\033[1;31m[!] Failed to launch Sway: {e}\033[0m")
                return False
        except Exception as e:
            print(f"\033[1;31m[!] Compositor runtime error: {e}\033[0m")
            return False

    def disable_gui(self) -> bool:
        """Terminates running Sway sessions and reverts back to low-resource TTY."""
        print("\033[1;33m[*] Stopping Graphical Desktop compositor...\033[0m")
        # 1. Try IPC exit command
        try:
            res = subprocess.run(["swaymsg", "exit"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                print("\033[1;32m[OK] Sway session closed gracefully.\033[0m")
                return True
        except Exception:
            pass

        # 2. Fallback to process termination
        try:
            subprocess.run(["pkill", "-TERM", "-x", "sway"], capture_output=True)
            subprocess.run(["pkill", "-TERM", "-x", "waybar"], capture_output=True)
            print("\033[1;32m[OK] GUI processes terminated. Back in low-resource TTY mode.\033[0m")
            return True
        except Exception as e:
            print(f"\033[1;31m[!] Error stopping GUI: {e}\033[0m")
            return False

    def toggle_gui(self) -> bool:
        """Toggles GUI desktop between active and stopped states."""
        if self.is_gui_running():
            return self.disable_gui()
        else:
            return self.enable_gui()


# ==============================================================================
# CLI Entry Point
# ==============================================================================
if __name__ == "__main__":
    expander = GUIExpander()

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--enable", "start", "on"):
            expander.enable_gui()
            sys.exit(0)
        elif arg in ("--disable", "stop", "off", "exit"):
            expander.disable_gui()
            sys.exit(0)
        elif arg in ("--status", "status"):
            active = expander.is_gui_running()
            print(f"GUI Active: {active}")
            sys.exit(0 if active else 1)

    print("Usage: python gui_expander.py {--enable | --disable | --status}")
