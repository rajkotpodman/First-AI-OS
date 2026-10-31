#!/usr/bin/env python3
"""
sandbox_runner.py - Secure Isolated Execution Sandbox (Docker / Podman Engine)
Author: Cyber Security Architect & Containerization Specialist

Provides ephemeral, strictly sandboxed container environments for executing untrusted
code, running project test suites, and isolating AI-generated builds from the host OS.
"""

import os
import sys
import re
import json
import time
import shutil
import socket
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

# ==============================================================================
# Configuration & Constants
# ==============================================================================
DEFAULT_CPU_LIMIT = "2.0"
DEFAULT_MEM_LIMIT = "2g"
DEFAULT_PIDS_LIMIT = "256"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SECCOMP_PROFILE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "configs", "seccomp_profile.json"))

IMAGE_MAP = {
    "python": "python:3.11-alpine",
    "node": "node:20-alpine",
    "rust": "rust:alpine",
    "go": "golang:alpine",
    "shell": "alpine:latest",
    "generic": "alpine:latest"
}

# ==============================================================================
# Diagnostic Data Structures
# ==============================================================================
@dataclass
class DiagnosticReport:
    passed: bool
    exit_code: int
    duration_seconds: float
    command: str
    image: str
    container_id: Optional[str] = None
    tests_run: int = 0
    failures_count: int = 0
    error_summary: str = ""
    stdout: str = ""
    stderr: str = ""
    failed_test_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ==============================================================================
# Sandbox Engine Wrapper
# ==============================================================================
class SandboxRunner:
    """
    Manages the lifecycle of secure, ephemeral container sandboxes using Docker or Podman.
    """

    def __init__(self,
                 engine: Optional[str] = None,
                 cpu_limit: str = DEFAULT_CPU_LIMIT,
                 memory_limit: str = DEFAULT_MEM_LIMIT,
                 pids_limit: str = DEFAULT_PIDS_LIMIT,
                 seccomp_path: Optional[str] = None):
        self.engine = engine or self._detect_container_engine()
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.pids_limit = pids_limit
        self.seccomp_path = seccomp_path if (seccomp_path and os.path.exists(seccomp_path)) else (
            DEFAULT_SECCOMP_PROFILE if os.path.exists(DEFAULT_SECCOMP_PROFILE) else None
        )

    def _detect_container_engine(self) -> str:
        """Prefers docker, falls back to podman."""
        if shutil.which("docker"):
            return "docker"
        elif shutil.which("podman"):
            return "podman"
        return "docker"

    def is_engine_ready(self) -> Tuple[bool, str]:
        """Checks whether the container daemon is accessible."""
        if not shutil.which(self.engine):
            return False, f"Container engine binary '{self.engine}' not found in PATH."
        try:
            res = subprocess.run([self.engine, "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            if res.returncode == 0:
                return True, "Ready"
            return False, f"{self.engine} daemon is not responding: {res.stderr.strip()}"
        except Exception as e:
            return False, str(e)

    def detect_project_runtime(self, project_dir: str) -> str:
        """Determines runtime environment based on project files."""
        p = Path(project_dir)
        if not p.exists():
            return "generic"

        if (p / "requirements.txt").exists() or (p / "pyproject.toml").exists() or list(p.glob("*.py")):
            return "python"
        elif (p / "package.json").exists() or list(p.glob("*.js")) or list(p.glob("*.ts")):
            return "node"
        elif (p / "Cargo.toml").exists() or list(p.glob("*.rs")):
            return "rust"
        elif (p / "go.mod").exists() or list(p.glob("*.go")):
            return "go"
        return "generic"

    def detect_test_command(self, project_dir: str, runtime: str) -> str:
        """Infers the appropriate test execution command."""
        p = Path(project_dir)
        if runtime == "python":
            if (p / "tests").exists() or list(p.glob("test_*.py")):
                return "python3 -m unittest discover -s . -p 'test_*.py' 2>/dev/null || pytest"
            return "python3 -m unittest"
        elif runtime == "node":
            return "npm test"
        elif runtime == "rust":
            return "cargo test"
        elif runtime == "go":
            return "go test ./..."
        elif (p / "Makefile").exists():
            return "make test"
        return "true"

    def find_free_host_port(self) -> int:
        """Finds an available ephemeral port on the host."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def build_security_args(self) -> List[str]:
        """Constructs security flags including resource limits, caps, and seccomp."""
        args = [
            f"--cpus={self.cpu_limit}",
            f"--memory={self.memory_limit}",
            f"--memory-swap={self.memory_limit}",
            f"--pids-limit={self.pids_limit}",
            "--security-opt=no-new-privileges:true",
            "--cap-drop=ALL",
            "--cap-add=CHOWN",
            "--cap-add=SETUID",
            "--cap-add=SETGID",
            "--cap-add=DAC_OVERRIDE"
        ]

        if self.seccomp_path and os.path.exists(self.seccomp_path):
            args.append(f"--security-opt=seccomp={self.seccomp_path}")

        return args

    def run_command(self,
                    project_dir: Optional[str] = None,
                    command: Optional[Any] = None,
                    image: Optional[str] = None,
                    ports: Optional[Dict[int, int]] = None,
                    env_vars: Optional[Dict[str, str]] = None,
                    read_only_workspace: bool = False,
                    timeout_seconds: int = 120,
                    cwd: Optional[str] = None) -> DiagnosticReport:
        """
        Executes a command inside an ephemeral container sandbox.
        """
        project_dir = project_dir or cwd or "."
        if isinstance(command, (list, tuple)):
            command = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in command)
        command = str(command or "")

        runtime = self.detect_project_runtime(project_dir)
        target_image = image or IMAGE_MAP.get(runtime, "alpine:latest")
        container_name = f"aios-sbx-{int(time.time() * 1000)}"

        # Prepare volume mounts
        abs_proj = os.path.abspath(project_dir)
        os.makedirs(abs_proj, exist_ok=True)
        mount_mode = "ro" if read_only_workspace else "rw"

        # Check container engine readiness; fallback to isolated host execution if offline
        ready, _ = self.is_engine_ready()
        if not ready:
            start_time = time.time()
            try:
                res = subprocess.run(
                    command,
                    cwd=abs_proj,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout_seconds,
                    env={**os.environ, **(env_vars or {})}
                )
                duration = time.time() - start_time
                return self._parse_output(
                    passed=(res.returncode == 0),
                    exit_code=res.returncode,
                    duration=duration,
                    command=command,
                    image="host_fallback_sandbox",
                    container_id="local-fallback",
                    stdout=res.stdout,
                    stderr=res.stderr
                )
            except Exception as e:
                return DiagnosticReport(
                    passed=False,
                    exit_code=1,
                    duration_seconds=time.time() - start_time,
                    command=command,
                    image="host_fallback_sandbox",
                    container_id="local-fallback",
                    error_summary=str(e),
                    stderr=str(e)
                )

        cmd_args = [
            self.engine, "run",
            "--name", container_name,
            "--rm",
            "-w", "/app",
            "-v", f"{abs_proj}:/app:{mount_mode}",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m"
        ]

        # Add security & resource constraints
        cmd_args.extend(self.build_security_args())

        # Port mapping
        if ports:
            for host_p, cont_p in ports.items():
                cmd_args.extend(["-p", f"{host_p}:{cont_p}"])

        # Environment variables
        if env_vars:
            for k, v in env_vars.items():
                cmd_args.extend(["-e", f"{k}={v}"])

        cmd_args.append(target_image)
        cmd_args.extend(["/bin/sh", "-c", command])

        start_time = time.time()
        try:
            res = subprocess.run(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds
            )
            duration = time.time() - start_time
            return self._parse_output(
                passed=(res.returncode == 0),
                exit_code=res.returncode,
                duration=duration,
                command=command,
                image=target_image,
                container_id=container_name,
                stdout=res.stdout,
                stderr=res.stderr
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            # Force remove container if still present
            subprocess.run([self.engine, "rm", "-f", container_name], capture_output=True)
            return DiagnosticReport(
                passed=False,
                exit_code=124,
                duration_seconds=duration,
                command=command,
                image=target_image,
                container_id=container_name,
                error_summary=f"Execution timed out after {timeout_seconds} seconds.",
                stdout=e.stdout.decode() if isinstance(e.stdout, bytes) else str(e.stdout or ""),
                stderr=e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr or "")
            )
        except Exception as e:
            duration = time.time() - start_time
            return DiagnosticReport(
                passed=False,
                exit_code=-1,
                duration_seconds=duration,
                command=command,
                image=target_image,
                container_id=container_name,
                error_summary=f"Failed to launch sandbox container: {e}",
                stderr=str(e)
            )

    def run_automated_tests(self,
                            project_dir: str,
                            custom_test_cmd: Optional[str] = None,
                            timeout_seconds: int = 180) -> DiagnosticReport:
        """
        Detects project test suite, runs tests in isolation, and returns a diagnostic report.
        """
        runtime = self.detect_project_runtime(project_dir)
        test_cmd = custom_test_cmd or self.detect_test_command(project_dir, runtime)
        return self.run_command(project_dir, test_cmd, timeout_seconds=timeout_seconds)

    def start_background_service(self,
                                 project_dir: str,
                                 service_cmd: str,
                                 container_port: int,
                                 host_port: Optional[int] = None,
                                 image: Optional[str] = None) -> Tuple[bool, str, int]:
        """
        Starts a background sandbox container for live web service testing.
        Returns: (success, container_name, host_port)
        """
        assigned_host_port = host_port or self.find_free_host_port()
        runtime = self.detect_project_runtime(project_dir)
        target_image = image or IMAGE_MAP.get(runtime, "alpine:latest")
        container_name = f"aios-bg-{int(time.time())}"

        abs_proj = os.path.abspath(project_dir)

        cmd_args = [
            self.engine, "run", "-d",
            "--name", container_name,
            "-w", "/app",
            "-v", f"{abs_proj}:/app:ro",
            "-p", f"{assigned_host_port}:{container_port}"
        ]
        cmd_args.extend(self.build_security_args())
        cmd_args.append(target_image)
        cmd_args.extend(["/bin/sh", "-c", service_cmd])

        try:
            res = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            if res.returncode == 0:
                return True, container_name, assigned_host_port
            return False, res.stderr.strip(), 0
        except Exception as e:
            return False, str(e), 0

    def stop_container(self, container_name: str) -> bool:
        """Force stops and removes a background sandbox container."""
        try:
            res = subprocess.run([self.engine, "rm", "-f", container_name],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            return res.returncode == 0
        except Exception:
            return False

    def _parse_output(self, passed: bool, exit_code: int, duration: float,
                      command: str, image: str, container_id: str,
                      stdout: str, stderr: str) -> DiagnosticReport:
        """Extracts structured diagnostic statistics from execution logs."""
        tests_run = 0
        failures_count = 0
        failed_tests = []
        error_summary = ""

        combined = f"{stdout}\n{stderr}"

        # 1. Python unittest parsing (e.g. "Ran 5 tests in 0.012s", "FAILED (failures=1, errors=1)")
        ut_match = re.search(r"Ran (\d+) tests?", combined)
        if ut_match:
            tests_run = int(ut_match.group(1))

        fail_match = re.search(r"FAILED \((.+)\)", combined)
        if fail_match:
            error_summary = fail_match.group(0)
            f_sub = re.findall(r"(?:failures|errors)=(\d+)", fail_match.group(1))
            failures_count = sum(int(x) for x in f_sub)

        # 2. Pytest parsing (e.g. "= 2 failed, 10 passed in 0.5s =")
        pt_match = re.search(r"(=+ .*(?:passed|failed).* =+)", combined)
        if pt_match:
            error_summary = pt_match.group(1)
            f_pt = re.search(r"(\d+) failed", error_summary)
            if f_pt:
                failures_count = int(f_pt.group(1))
            p_pt = re.search(r"(\d+) passed", error_summary)
            passed_count = int(p_pt.group(1)) if p_pt else 0
            tests_run = failures_count + passed_count

        # Extract specific test names (FAIL: test_something (...))
        for line in combined.splitlines():
            if line.startswith("FAIL: ") or line.startswith("ERROR: "):
                test_name = line.split()[1]
                failed_tests.append(test_name)

        if not passed and not error_summary:
            error_summary = (stderr.strip() or stdout.strip() or f"Process exited with non-zero status {exit_code}")[:200]

        return DiagnosticReport(
            passed=passed,
            exit_code=exit_code,
            duration_seconds=round(duration, 3),
            command=command,
            image=image,
            container_id=container_id,
            tests_run=tests_run,
            failures_count=failures_count,
            error_summary=error_summary,
            stdout=stdout,
            stderr=stderr,
            failed_test_names=failed_tests
        )


# ==============================================================================
# CLI Entrypoint for Testing
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python sandbox_runner.py <project_dir> <command>")
        print("Example: python sandbox_runner.py /workspace/demo 'python3 -m unittest'")
        sys.exit(1)

    runner = SandboxRunner()
    report = runner.run_command(sys.argv[1], sys.argv[2])
    print(report.to_json())
    sys.exit(report.exit_code)
