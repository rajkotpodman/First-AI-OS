#!/usr/bin/env python3
"""
dependency_resolver.py - Dynamic Dependency & Package Resolver Engine for AI OS
Author: Lead Systems Programmer & Linux Package Management Specialist

Features:
- Multi-tier package manager abstraction (apk, apt, pacman, pip, npm, cargo, go)
- Real-time stderr / stdout error interception (command not found, ModuleNotFoundError, etc.)
- Project manifest parser (package.json, requirements.txt, Cargo.toml, go.mod, Makefile)
- Auto-healing execution loop with post-install verification and re-execution
- Persistent audit logging to /var/log/ai_deps.log
"""

import os
import sys
import re
import shutil
import subprocess
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# ==============================================================================
# Configuration & Constants
# ==============================================================================
DEFAULT_LOG_PATH = "/var/log/ai_deps.log"
FALLBACK_LOG_PATH = os.path.expanduser("~/.aios/ai_deps.log")

# Common CLI command to system package mappings
COMMAND_TO_SYSTEM_PKG = {
    # Command -> { "apk": pkg, "apt": pkg, "pacman": pkg }
    "curl": {"apk": "curl", "apt": "curl", "pacman": "curl"},
    "git": {"apk": "git", "apt": "git", "pacman": "git"},
    "make": {"apk": "make", "apt": "build-essential", "pacman": "make"},
    "gcc": {"apk": "build-base", "apt": "gcc", "pacman": "gcc"},
    "g++": {"apk": "build-base", "apt": "g++", "pacman": "gcc"},
    "clang": {"apk": "clang", "apt": "clang", "pacman": "clang"},
    "python": {"apk": "python3", "apt": "python3", "pacman": "python"},
    "python3": {"apk": "python3", "apt": "python3", "pacman": "python"},
    "pip": {"apk": "py3-pip", "apt": "python3-pip", "pacman": "python-pip"},
    "pip3": {"apk": "py3-pip", "apt": "python3-pip", "pacman": "python-pip"},
    "node": {"apk": "nodejs", "apt": "nodejs", "pacman": "nodejs"},
    "npm": {"apk": "npm", "apt": "npm", "pacman": "npm"},
    "yarn": {"apk": "yarn", "apt": "yarnpkg", "pacman": "yarn"},
    "cargo": {"apk": "cargo", "apt": "cargo", "pacman": "rust"},
    "rustc": {"apk": "rust", "apt": "rustc", "pacman": "rust"},
    "go": {"apk": "go", "apt": "golang-go", "pacman": "go"},
    "docker": {"apk": "docker", "apt": "docker.io", "pacman": "docker"},
    "jq": {"apk": "jq", "apt": "jq", "pacman": "jq"},
    "tar": {"apk": "tar", "apt": "tar", "pacman": "tar"},
    "unzip": {"apk": "unzip", "apt": "unzip", "pacman": "unzip"},
    "zip": {"apk": "zip", "apt": "zip", "pacman": "zip"},
    "wget": {"apk": "wget", "apt": "wget", "pacman": "wget"},
    "tree": {"apk": "tree", "apt": "tree", "pacman": "tree"},
    "htop": {"apk": "htop", "apt": "htop", "pacman": "htop"},
    "tmux": {"apk": "tmux", "apt": "tmux", "pacman": "tmux"},
    "rsync": {"apk": "rsync", "apt": "rsync", "pacman": "rsync"},
    "ffmpeg": {"apk": "ffmpeg", "apt": "ffmpeg", "pacman": "ffmpeg"},
    "ollama": {"apk": "curl", "apt": "curl", "pacman": "curl"}
}

# ==============================================================================
# Logger Setup
# ==============================================================================
class DependencyLogger:
    """Manages audit trails for package resolutions with fallback locations."""
    def __init__(self, log_path: str = DEFAULT_LOG_PATH):
        self.log_path = log_path
        self._ensure_log_file()

    def _ensure_log_file(self):
        try:
            log_dir = os.path.dirname(self.log_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"--- AI-OS Dependency Resolver Initialized {datetime.datetime.now().isoformat()} ---\n")
        except (PermissionError, OSError):
            self.log_path = FALLBACK_LOG_PATH
            fallback_dir = os.path.dirname(self.log_path)
            os.makedirs(fallback_dir, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"--- AI-OS Dependency Resolver Fallback Log Initialized {datetime.datetime.now().isoformat()} ---\n")

    def log(self, level: str, message: str, meta: Optional[Dict[str, Any]] = None):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level.upper()}] {message}"
        if meta:
            entry += f" | {meta}"
        entry += "\n"
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except OSError:
            pass
        # Echo to stderr if debug or warning
        if level in ("WARN", "ERROR"):
            sys.stderr.write(f"\033[1;33m[DependencyResolver:{level}]\033[0m {message}\n")

# ==============================================================================
# Package Manager Abstraction
# ==============================================================================
class PackageManagerAdapter:
    """Abstract interface and detection for platform package managers."""
    def __init__(self, logger: DependencyLogger):
        self.logger = logger
        self.system_pm = self._detect_system_pm()

    def _detect_system_pm(self) -> str:
        """Detect the underlying host system package manager."""
        if shutil.which("apk"):
            return "apk"
        elif shutil.which("apt-get"):
            return "apt"
        elif shutil.which("pacman"):
            return "pacman"
        elif shutil.which("dnf"):
            return "dnf"
        return "apk"  # Default assumption for AI-OS

    def is_available(self, tool: str) -> bool:
        return shutil.which(tool) is not None

    def install_system_package(self, pkg_name: str) -> bool:
        """Installs a system package using the native package manager."""
        pm = self.system_pm
        self.logger.log("INFO", f"Installing system package '{pkg_name}' via '{pm}'")

        if pm == "apk":
            cmd = ["apk", "add", "--no-cache", pkg_name]
        elif pm == "apt":
            cmd = ["apt-get", "install", "-y", pkg_name]
        elif pm == "pacman":
            cmd = ["pacman", "-S", "--noconfirm", pkg_name]
        elif pm == "dnf":
            cmd = ["dnf", "install", "-y", pkg_name]
        else:
            self.logger.log("ERROR", f"Unsupported system package manager: {pm}")
            return False

        # Add sudo if not root
        if os.geteuid() != 0 if hasattr(os, "geteuid") else False:
            if shutil.which("sudo"):
                cmd = ["sudo"] + cmd

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if res.returncode == 0:
                self.logger.log("INFO", f"Successfully installed system package: {pkg_name}")
                return True
            else:
                self.logger.log("ERROR", f"Failed to install system package: {pkg_name}", {"stderr": res.stderr})
                return False
        except Exception as e:
            self.logger.log("ERROR", f"Exception installing system package {pkg_name}: {e}")
            return False

    def install_pip_package(self, pkg_name: str) -> bool:
        """Installs a Python package using pip."""
        pip_cmd = "pip3" if shutil.which("pip3") else "pip"
        if not shutil.which(pip_cmd):
            self.logger.log("WARN", "pip binary not found. Bootstrapping pip first...")
            if not self.install_system_package(COMMAND_TO_SYSTEM_PKG["pip"].get(self.system_pm, "py3-pip")):
                return False

        cmd = [pip_cmd, "install", "--break-system-packages", pkg_name]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            if res.returncode == 0:
                self.logger.log("INFO", f"Successfully installed Python package: {pkg_name}")
                return True
            # Retry without --break-system-packages if unrecognized
            if "--break-system-packages" in res.stderr:
                cmd.remove("--break-system-packages")
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
                if res.returncode == 0:
                    self.logger.log("INFO", f"Successfully installed Python package (standard mode): {pkg_name}")
                    return True
            self.logger.log("ERROR", f"Pip install failed for {pkg_name}", {"stderr": res.stderr})
            return False
        except Exception as e:
            self.logger.log("ERROR", f"Exception installing pip package {pkg_name}: {e}")
            return False

    def install_npm_package(self, pkg_name: str, is_global: bool = False) -> bool:
        """Installs a Node.js package using npm/pnpm/yarn."""
        npm_cmd = "npm"
        if not shutil.which(npm_cmd):
            self.logger.log("WARN", "npm not found. Installing nodejs and npm...")
            if not self.install_system_package(COMMAND_TO_SYSTEM_PKG["npm"].get(self.system_pm, "npm")):
                return False

        args = [npm_cmd, "install"]
        if is_global:
            args.append("-g")
        args.append(pkg_name)

        try:
            res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            return res.returncode == 0
        except Exception as e:
            self.logger.log("ERROR", f"Exception installing npm package {pkg_name}: {e}")
            return False

    def install_cargo_package(self, crate_name: str) -> bool:
        """Installs a Rust binary/crate using cargo."""
        if not shutil.which("cargo"):
            self.install_system_package(COMMAND_TO_SYSTEM_PKG["cargo"].get(self.system_pm, "cargo"))
        try:
            res = subprocess.run(["cargo", "install", crate_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
            return res.returncode == 0
        except Exception as e:
            self.logger.log("ERROR", f"Cargo install failed for {crate_name}: {e}")
            return False

# ==============================================================================
# Error Pattern Detector & Classifier
# ==============================================================================
class ErrorPatternDetector:
    """Interprets stderr/stdout streams to extract missing tools and libraries."""

    PATTERNS = [
        # 1. Shell Command Not Found
        (re.compile(r"(?:command not found|not found):\s*['\"]?([a-zA-Z0-9_\-\.]+)", re.IGNORECASE), "command"),
        (re.compile(r"\/bin\/sh:\s*['\"]?([a-zA-Z0-9_\-\.]+)['\"]?:\s*not found", re.IGNORECASE), "command"),
        (re.compile(r"bash:\s*([a-zA-Z0-9_\-\.]+):\s*command not found", re.IGNORECASE), "command"),
        (re.compile(r"^['\"]?([a-zA-Z0-9_\-\.]+)['\"]?:\s*command not found", re.IGNORECASE), "command"),
        (re.compile(r"['\"]?([a-zA-Z0-9_\-\.]+)['\"]?\s+is not recognized as an internal or external command", re.IGNORECASE), "command"),

        # 2. Python ModuleNotFoundError / ImportError
        (re.compile(r"ModuleNotFoundError:\s*No module named\s*['\"]([a-zA-Z0-9_\.]+)['\"]", re.IGNORECASE), "python_module"),
        (re.compile(r"ImportError:\s*cannot import name .* from\s*['\"]([a-zA-Z0-9_\.]+)['\"]", re.IGNORECASE), "python_module"),
        (re.compile(r"ImportError:\s*No module named\s*['\"]([a-zA-Z0-9_\.]+)['\"]", re.IGNORECASE), "python_module"),

        # 3. Node.js Cannot Find Module
        (re.compile(r"Cannot find module\s*['\"]([a-zA-Z0-9_\-@\/]+)['\"]", re.IGNORECASE), "node_module"),
        (re.compile(r"Error:\s*Cannot find module\s*['\"]([a-zA-Z0-9_\-@\/]+)['\"]", re.IGNORECASE), "node_module"),

        # 4. C/C++ Missing Headers
        (re.compile(r"fatal error:\s*([a-zA-Z0-9_\-\/\.]+)\.h:\s*No such file or directory", re.IGNORECASE), "c_header")
    ]

    # Python module aliases (import name -> pip package name)
    PY_MODULE_TO_PKG = {
        "yaml": "PyYAML",
        "requests": "requests",
        "PIL": "Pillow",
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "bs4": "beautifulsoup4",
        "dotenv": "python-dotenv",
        "jwt": "PyJWT",
        "psutil": "psutil",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "flask": "flask",
        "pydantic": "pydantic",
        "ollama": "ollama",
        "aiohttp": "aiohttp"
    }

    @classmethod
    def identify_missing(cls, stderr_output: str, stdout_output: str = "") -> List[Tuple[str, str]]:
        """
        Parses text and returns list of (category, target_name).
        Categories: 'command', 'python_module', 'node_module', 'c_header'
        """
        combined = f"{stderr_output}\n{stdout_output}"
        detected = []

        for pattern, category in cls.PATTERNS:
            for match in pattern.finditer(combined):
                target = match.group(1).strip()
                if category == "python_module":
                    root_mod = target.split(".")[0]
                    target = cls.PY_MODULE_TO_PKG.get(root_mod, root_mod)
                if (category, target) not in detected:
                    detected.append((category, target))

        return detected

# ==============================================================================
# Project Manifest Scanner
# ==============================================================================
class ProjectManifestScanner:
    """Scans repository manifests and determines required toolchains & dependencies."""

    @staticmethod
    def scan_directory(project_path: str) -> Dict[str, List[str]]:
        """Returns dependencies grouped by manager: {'pip': [...], 'npm': [...], ...}"""
        results = {"pip": [], "npm": [], "cargo": [], "go": [], "system": []}
        base = Path(project_path)
        if not base.exists():
            return results

        # 1. Python requirements.txt
        req_file = base / "requirements.txt"
        if req_file.exists():
            try:
                with open(req_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            results["pip"].append(line)
            except Exception:
                pass

        # 2. Node.js package.json
        pkg_json = base / "package.json"
        if pkg_json.exists():
            results["npm"].append("install")  # Trigger npm install

        # 3. Rust Cargo.toml
        cargo_toml = base / "Cargo.toml"
        if cargo_toml.exists():
            results["cargo"].append("build")

        # 4. Go go.mod
        go_mod = base / "go.mod"
        if go_mod.exists():
            results["go"].append("tidy")

        # 5. Makefile
        makefile = base / "Makefile"
        if makefile.exists():
            results["system"].append("make")

        return results

# ==============================================================================
# Auto-Healing Execution Engine
# ==============================================================================
class DependencyResolver:
    """
    Main controller for dynamic dependency resolution, auto-healing command execution,
    and post-install environment verification.
    """
    def __init__(self, log_path: str = DEFAULT_LOG_PATH, max_retries: int = 2):
        self.logger = DependencyLogger(log_path)
        self.adapter = PackageManagerAdapter(self.logger)
        self.max_retries = max_retries

    def resolve_missing(self, category: str, target: str) -> bool:
        """Resolves and installs a single missing dependency by category."""
        self.logger.log("INFO", f"Attempting resolution for [{category}] '{target}'")

        if category == "command":
            # Match to known system package
            sys_info = COMMAND_TO_SYSTEM_PKG.get(target)
            if sys_info:
                pkg_name = sys_info.get(self.adapter.system_pm, target)
            else:
                pkg_name = target
            success = self.adapter.install_system_package(pkg_name)
            if success and self.verify_binary_in_path(target):
                return True
            # If not in system PM, maybe it's a python tool (e.g. uvicorn, black, pytest)
            if not success:
                self.logger.log("INFO", f"Trying fallback python package for tool '{target}'")
                return self.adapter.install_pip_package(target)
            return success

        elif category == "python_module":
            return self.adapter.install_pip_package(target)

        elif category == "node_module":
            return self.adapter.install_npm_package(target)

        elif category == "c_header":
            # Install build-base/build-essential
            return self.adapter.install_system_package("build-base")

        return False

    def verify_binary_in_path(self, binary_name: str) -> bool:
        """Verifies that an installed executable is present in PATH."""
        # Refresh common search directories
        extra_paths = ["/usr/local/bin", "/usr/bin", "/bin", "/sbin", "/usr/sbin", os.path.expanduser("~/.local/bin"), os.path.expanduser("~/.cargo/bin")]
        current_path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for ep in extra_paths:
            if os.path.exists(ep) and ep not in current_path_dirs:
                os.environ["PATH"] = f"{ep}{os.pathsep}{os.environ.get('PATH', '')}"

        found = shutil.which(binary_name) is not None
        if found:
            self.logger.log("INFO", f"Verified binary '{binary_name}' in PATH ({shutil.which(binary_name)})")
        else:
            self.logger.log("WARN", f"Binary '{binary_name}' not immediately found in current PATH.")
        return found

    def intercept_and_heal(self, exit_code: int, stderr: str, stdout: str, original_cmd: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
        """
        Hook to evaluate a failed execution.
        Returns: (healed_success, message_or_new_output)
        """
        if exit_code == 0:
            return True, "Command succeeded without errors."

        missing_items = ErrorPatternDetector.identify_missing(stderr, stdout)
        if not missing_items:
            return False, "No resolvable missing dependencies detected in error stream."

        self.logger.log("WARN", f"Auto-heal triggered for command '{original_cmd}'. Missing: {missing_items}")
        all_resolved = True

        for category, target in missing_items:
            resolved = self.resolve_missing(category, target)
            if not resolved:
                all_resolved = False

        if all_resolved:
            return True, f"Resolved dependencies: {[item[1] for item in missing_items]}"
        return False, "Some dependencies could not be resolved."

    def run_with_autoheal(self, command: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
        """
        High-level execution hook. Runs command, catches missing dependencies,
        installs them, and automatically re-executes.
        """
        retries = 0
        current_env = os.environ.copy()
        if env:
            current_env.update(env)

        while retries <= self.max_retries:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                env=current_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if proc.returncode == 0:
                return proc.returncode, proc.stdout, proc.stderr

            # Error occurred: Attempt interception & healing
            healed, msg = self.intercept_and_heal(proc.returncode, proc.stderr, proc.stdout, command, cwd)
            if not healed:
                # Could not heal, return final result
                return proc.returncode, proc.stdout, proc.stderr

            retries += 1
            self.logger.log("INFO", f"Re-executing healed command (attempt {retries}/{self.max_retries}): '{command}'")

        return proc.returncode, proc.stdout, proc.stderr

    def install_project_dependencies(self, project_dir: str) -> Dict[str, Any]:
        """Scans project directory and installs all declared dependencies."""
        manifest = ProjectManifestScanner.scan_directory(project_dir)
        results = {"success": True, "details": {}}

        # System dependencies
        for sys_dep in manifest.get("system", []):
            ok = self.adapter.install_system_package(sys_dep)
            results["details"][f"sys_{sys_dep}"] = ok
            if not ok: results["success"] = False

        # Python dependencies
        for pip_dep in manifest.get("pip", []):
            ok = self.adapter.install_pip_package(pip_dep)
            results["details"][f"pip_{pip_dep}"] = ok
            if not ok: results["success"] = False

        # Node dependencies
        if manifest.get("npm"):
            npm_ok = subprocess.run(["npm", "install"], cwd=project_dir, shell=True).returncode == 0
            results["details"]["npm_install"] = npm_ok
            if not npm_ok: results["success"] = False

        return results

# ==============================================================================
# CLI Entrypoint for Standalone / Shell Testing
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dependency_resolver.py <command_to_run_with_autoheal>")
        print("Example: python dependency_resolver.py 'python -c \"import requests\"'")
        sys.exit(1)

    cmd_to_run = " ".join(sys.argv[1:])
    resolver = DependencyResolver()
    code, out, err = resolver.run_with_autoheal(cmd_to_run)
    if out: sys.stdout.write(out)
    if err: sys.stderr.write(err)
    sys.exit(code)
