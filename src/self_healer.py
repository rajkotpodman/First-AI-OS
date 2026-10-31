#!/usr/bin/env python3
"""
self_healer.py - Automated Testing, Verification & Self-Debugging Loop
Author: Senior QA Automation Architect and Site Reliability Engineer

Monitors builds and tests inside sandbox containers or local environments,
intercepts stack traces, diagnoses root causes with AI models, applies unified
diffs or code replacements, and loops iteratively until all tests pass.
"""

import os
import sys
import re
import json
import shutil
import difflib
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Subsystem dependencies
try:
    from ai_shell_agent import AIRouter, ConfigManager
except ImportError:
    AIRouter = None
    ConfigManager = None

try:
    from sandbox_runner import SandboxRunner, DiagnosticReport
except ImportError:
    SandboxRunner = None
    DiagnosticReport = None

try:
    from git_automator import GitAutomator
except ImportError:
    GitAutomator = None

try:
    from offline_docs_engine import OfflineDocsEngine
except ImportError:
    OfflineDocsEngine = None


# ==============================================================================
# Diff & Patch Resolution Engine
# ==============================================================================
class DiffPatcher:
    """Robust engine for applying unified diffs and code replacements."""

    @staticmethod
    def apply_unified_diff(original_text: str, patch_text: str) -> Tuple[bool, str, str]:
        """
        Parses and applies a unified diff to original text.
        Returns: (success, updated_text, error_message)
        """
        orig_lines = original_text.splitlines(keepends=True)
        patch_lines = patch_text.strip().splitlines(keepends=True)

        # Parse hunks
        hunk_header_re = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")
        hunks = []
        current_hunk = None

        for line in patch_lines:
            if line.startswith("---") or line.startswith("+++"):
                continue
            m = hunk_header_re.match(line)
            if m:
                if current_hunk:
                    hunks.append(current_hunk)
                orig_start = int(m.group(1))
                orig_len = int(m.group(2)) if m.group(2) else 1
                new_start = int(m.group(3))
                new_len = int(m.group(4)) if m.group(4) else 1
                current_hunk = {
                    "orig_start": orig_start,
                    "orig_len": orig_len,
                    "new_start": new_start,
                    "new_len": new_len,
                    "lines": []
                }
            elif current_hunk is not None:
                current_hunk["lines"].append(line)

        if current_hunk:
            hunks.append(current_hunk)

        if not hunks:
            return False, original_text, "No valid unified diff hunks found in patch."

        # Apply hunks backwards to avoid line index corruption
        modified_lines = list(orig_lines)
        for hunk in reversed(hunks):
            # Line numbers in diffs are 1-based
            start_idx = max(0, hunk["orig_start"] - 1)
            hunk_orig_lines = []
            hunk_new_lines = []

            for h_line in hunk["lines"]:
                if h_line.startswith("+"):
                    hunk_new_lines.append(h_line[1:])
                elif h_line.startswith("-"):
                    hunk_orig_lines.append(h_line[1:])
                elif h_line.startswith(" "):
                    hunk_orig_lines.append(h_line[1:])
                    hunk_new_lines.append(h_line[1:])

            # Verify context match; if line offset shifted, try search window
            target_slice = modified_lines[start_idx:start_idx + len(hunk_orig_lines)]
            match_found = False

            if "".join(target_slice).strip() == "".join(hunk_orig_lines).strip():
                match_found = True
            else:
                # Search nearby context (up to +/- 20 lines)
                for offset in range(-20, 21):
                    trial_idx = start_idx + offset
                    if trial_idx >= 0 and trial_idx + len(hunk_orig_lines) <= len(modified_lines):
                        trial_slice = modified_lines[trial_idx:trial_idx + len(hunk_orig_lines)]
                        if "".join(trial_slice).strip() == "".join(hunk_orig_lines).strip():
                            start_idx = trial_idx
                            match_found = True
                            break

            if not match_found and len(hunk_orig_lines) > 0:
                return False, original_text, f"Diff context mismatch at line {hunk['orig_start']}"

            # Replace slice with new lines
            modified_lines[start_idx:start_idx + len(hunk_orig_lines)] = hunk_new_lines

        return True, "".join(modified_lines), "Patch applied successfully."

    @staticmethod
    def extract_patch_from_response(llm_response: str) -> Dict[str, Any]:
        """
        Extracts patch metadata (target_file, unified_diff or new_content)
        from model response in JSON or Markdown format.
        """
        cleaned = llm_response.strip()

        # 1. Try JSON parsing
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        try:
            bracket_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if bracket_match:
                data = json.loads(bracket_match.group(1))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

        # 2. Try raw diff block
        diff_match = re.search(r"```(?:diff)?\s*(---.*?```)", cleaned, re.DOTALL)
        if diff_match:
            raw_diff = diff_match.group(1).rstrip("`").strip()
            # Extract target file from +++ line
            file_match = re.search(r"\+\+\+\s+[b/]*(.*)", raw_diff)
            target = file_match.group(1).strip() if file_match else ""
            return {"target_file": target, "unified_diff": raw_diff}

        # 3. Fallback: markdown code block with language
        code_match = re.search(r"```(?:python|javascript|rust|go)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if code_match:
            return {"new_content": code_match.group(1)}

        return {}


# ==============================================================================
# Error Log Analyzer
# ==============================================================================
@dataclass
class ErrorContext:
    error_summary: str
    failed_file: Optional[str]
    line_number: Optional[int]
    exception_type: str
    stack_trace: str
    current_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ErrorAnalyzer:
    """Extracts failure coordinates, stack traces, and relevant file contents."""

    # Python traceback pattern: File "...", line X, in Y
    PY_TRACE_RE = re.compile(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+(\w+))?', re.MULTILINE)
    PY_EXC_RE = re.compile(r"^([a-zA-Z_]+Error|[a-zA-Z_]+Exception|AssertionError):\s*(.*)", re.MULTILINE)

    # Node.js error pattern: at ... (file.js:line:col)
    NODE_TRACE_RE = re.compile(r'at\s+.*(?:\(([^:\n]+):(\d+):(\d+)\)|([^\s:\n]+):(\d+):(\d+))', re.MULTILINE)

    @classmethod
    def analyze_failure(cls, project_dir: Path, stderr: str, stdout: str) -> ErrorContext:
        combined = f"{stdout}\n{stderr}"
        failed_file = None
        line_num = None
        exc_type = "RuntimeError"
        summary = ""

        # 1. Inspect Python Tracebacks
        py_traces = list(cls.PY_TRACE_RE.finditer(combined))
        if py_traces:
            # Pick the last frame in user project directory
            for match in reversed(py_traces):
                candidate_path = match.group(1)
                # Ignore standard library / site-packages if possible
                if "site-packages" not in candidate_path and "lib/python" not in candidate_path:
                    failed_file = candidate_path
                    line_num = int(match.group(2))
                    break
            if not failed_file:
                failed_file = py_traces[-1].group(1)
                line_num = int(py_traces[-1].group(2))

        # Check Python exception message
        exc_match = cls.PY_EXC_RE.search(combined)
        if exc_match:
            exc_type = exc_match.group(1)
            summary = f"{exc_type}: {exc_match.group(2)}"

        # 2. Inspect Node.js Error
        if not failed_file:
            node_traces = list(cls.NODE_TRACE_RE.finditer(combined))
            if node_traces:
                last_node = node_traces[0]
                failed_file = last_node.group(1) or last_node.group(4)
                line_num = int(last_node.group(2) or last_node.group(5))
                summary = "Node.js Execution Error"

        if not summary:
            # Extract last non-empty line of stderr
            lines = [l.strip() for l in combined.splitlines() if l.strip()]
            summary = lines[-1] if lines else "Process failed with non-zero exit status"

        # Resolve real file path and load current code
        current_code = ""
        resolved_file = None
        if failed_file:
            # Try absolute or relative to project_dir
            candidates = [
                Path(failed_file),
                project_dir / failed_file,
                project_dir / os.path.basename(failed_file)
            ]
            for c in candidates:
                if c.exists() and c.is_file():
                    resolved_file = str(c.relative_to(project_dir.resolve())) if c.is_relative_to(project_dir.resolve()) else str(c)
                    try:
                        current_code = c.read_text(encoding="utf-8")
                    except Exception:
                        pass
                    break

        return ErrorContext(
            error_summary=summary,
            failed_file=resolved_file or failed_file,
            line_number=line_num,
            exception_type=exc_type,
            stack_trace=combined[-2000:],  # Tail 2000 chars of stack
            current_code=current_code
        )


# ==============================================================================
# Self-Healing Debugger Controller
# ==============================================================================
SELF_DEBUG_SYSTEM_PROMPT = """You are the Senior Site Reliability & QA Self-Debugging Engineer for AI OS.
Your mission is to diagnose test failures and generate an exact code patch to fix the bug.

You will be given:
1. Error Summary and Stack Trace
2. The failing file path and line number
3. Current source code of the failing file

INSTRUCTIONS:
Respond STRICTLY with a JSON object in this format:
{
  "target_file": "relative/path/to/file.ext",
  "root_cause": "Clear 1-sentence explanation of why the failure occurred",
  "unified_diff": "--- a/file.ext\\n+++ b/file.ext\\n@@ -10,3 +10,3 @@\\n- broken code\\n+ fixed code",
  "new_content": "Alternatively, the full corrected file content if a diff is inconvenient"
}
Do NOT include commentary outside the JSON block.
"""

@dataclass
class PatchAttempt:
    iteration: int
    failed_file: Optional[str]
    error_summary: str
    root_cause: str
    patch_applied: bool
    test_passed_after: bool


@dataclass
class DebugSummary:
    resolved: bool
    iterations_run: int
    max_iterations: int
    original_error: str
    final_error: str
    attempts: List[PatchAttempt] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class SelfHealer:
    """Autonomous debugging and iterative test-patch-verify loop."""

    def __init__(self,
                 max_retries: int = 3,
                 router: Optional[Any] = None,
                 sandbox: Optional[Any] = None,
                 git_automator: Optional[Any] = None,
                 docs_engine: Optional[Any] = None):
        self.max_retries = max_retries
        self.config = ConfigManager.load() if ConfigManager else {}
        self.router = router or (AIRouter(self.config) if AIRouter else None)
        self.sandbox = sandbox or (SandboxRunner() if SandboxRunner else None)
        self.git_automator = git_automator or (GitAutomator(router=self.router) if GitAutomator else None)
        self.docs_engine = docs_engine or (OfflineDocsEngine() if OfflineDocsEngine else None)

    def run_tests(self, project_dir: Path, custom_cmd: Optional[str] = None) -> Tuple[bool, int, str, str]:
        """Runs tests either inside sandbox container or via local subprocess."""
        if self.sandbox:
            engine_ready, _ = self.sandbox.is_engine_ready()
            if engine_ready:
                report = self.sandbox.run_automated_tests(str(project_dir), custom_test_cmd=custom_cmd)
                return report.passed, report.exit_code, report.stdout, report.stderr

        # Local execution fallback
        test_cmd = custom_cmd
        if not test_cmd:
            py_bin = sys.executable if sys.executable else ("python3" if shutil.which("python3") else "python")
            if (project_dir / "tests").exists() or list(project_dir.glob("test_*.py")):
                test_cmd = f'"{py_bin}" -m unittest discover -s . -p "test_*.py"'
            elif (project_dir / "package.json").exists():
                test_cmd = "npm test"
            else:
                test_cmd = f'"{py_bin}" -m unittest'

        res = subprocess.run(
            test_cmd,
            cwd=project_dir,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return (res.returncode == 0), res.returncode, res.stdout, res.stderr

    def apply_patch(self, project_dir: Path, patch_data: Dict[str, Any], default_target: Optional[str]) -> Tuple[bool, str]:
        """Applies unified diff or full replacement content to target file."""
        target_rel = patch_data.get("target_file") or default_target
        if not target_rel:
            return False, "No target file specified for patch."

        file_path = project_dir / target_rel
        if not file_path.exists():
            return False, f"Target file does not exist: {target_rel}"

        original_content = file_path.read_text(encoding="utf-8")

        # 1. Check if unified diff is supplied
        unified_diff = patch_data.get("unified_diff")
        if unified_diff:
            ok, updated, msg = DiffPatcher.apply_unified_diff(original_content, unified_diff)
            if ok:
                file_path.write_text(updated, encoding="utf-8")
                return True, f"Unified diff applied: {msg}"
            # If diff failed but new_content is also provided, try fallback

        # 2. Check if new full content is supplied
        new_content = patch_data.get("new_content")
        if new_content and len(new_content.strip()) > 0:
            file_path.write_text(new_content, encoding="utf-8")
            return True, "Full file replacement applied successfully."

        return False, "Could not apply unified diff or replacement content."

    def auto_heal_project(self, project_dir: str, custom_test_cmd: Optional[str] = None) -> DebugSummary:
        """
        Main autonomous loop: Run tests -> Analyze Error -> Query LLM -> Patch -> Re-verify.
        """
        proj_path = Path(project_dir).resolve()
        attempts = []

        print(f"\033[1;36m[*] Self-Healer: Running initial verification tests for '{proj_path.name}'...\033[0m")
        passed, code, stdout, stderr = self.run_tests(proj_path, custom_test_cmd)

        if passed:
            print("\033[1;32m[OK] All tests passed cleanly on initial run! No healing required.\033[0m")
            return DebugSummary(
                resolved=True,
                iterations_run=0,
                max_iterations=self.max_retries,
                original_error="None",
                final_error="None",
                attempts=[]
            )

        # Ensure Git repository and baseline checkpoint exist before attempting repairs
        baseline_cp = None
        base_branch = "main"
        if self.git_automator:
            if not self.git_automator.is_git_repo(proj_path):
                self.git_automator.init_repository(proj_path, stack="generic", initial_commit=True)
            status = self.git_automator.get_status(proj_path)
            base_branch = status.current_branch or "main"
            baseline_cp = self.git_automator.create_checkpoint(proj_path, reason="pre-healing-baseline")
            print(f"\033[1;34m[*] Git Automator: Created baseline checkpoint '{baseline_cp.tag_name}'\033[0m")

        # Analyze initial error
        err_ctx = ErrorAnalyzer.analyze_failure(proj_path, stderr, stdout)
        initial_error = err_ctx.error_summary
        current_error = initial_error
        print(f"\033[1;31m[!] Initial test failure detected: {initial_error}\033[0m")

        for iteration in range(1, self.max_retries + 1):
            print(f"\n\033[1;33m--- Self-Healing Loop: Iteration {iteration}/{self.max_retries} ---\033[0m")
            print(f"Targeting: {err_ctx.failed_file} (Line {err_ctx.line_number})")

            # Check if router is available
            if not self.router:
                print("\033[1;31m[!] AI Router unavailable for autonomous code repair.\033[0m")
                break

            # 1. Query Offline Docs Engine for official API specifications
            doc_context = ""
            if self.docs_engine:
                doc_context = self.docs_engine.get_doc_context_for_error(
                    err_ctx.error_summary,
                    failed_code=err_ctx.current_code
                )
                if doc_context:
                    print("\033[1;36m[*] Offline Docs Engine: Injected official API specifications into prompt context.\033[0m")

            prompt_payload = json.dumps(err_ctx.to_dict(), indent=2)
            user_prompt = f"Fix this error:\n{prompt_payload}"
            if doc_context:
                user_prompt = f"{user_prompt}\n\n{doc_context}"

            # 2. Branching & Safety Checkpoint before code modification
            iter_branch = f"ai-fix/attempt-{iteration}"
            iter_cp = None
            if self.git_automator:
                self.git_automator.create_feature_branch(proj_path, iter_branch, checkout=True)
                iter_cp = self.git_automator.create_checkpoint(proj_path, reason=f"pre-patch-iteration-{iteration}")

            print("\033[1;34m[*] Requesting diagnosis and unified patch from AI...\033[0m")
            ok, response_text = self.router.query(SELF_DEBUG_SYSTEM_PROMPT, user_prompt)

            if not ok:
                print(f"\033[1;31m[!] Model query failed: {response_text}\033[0m")
                if self.git_automator and iter_cp:
                    self.git_automator.rollback_to_commit(proj_path, iter_cp.commit_sha, hard=True)
                    self.git_automator.checkout_branch(proj_path, base_branch)
                break

            patch_data = DiffPatcher.extract_patch_from_response(response_text)
            root_cause = patch_data.get("root_cause", "Automated bug patch")

            print(f"\033[1;35m[*] Root Cause Diagnosed:\033[0m {root_cause}")
            patch_applied, patch_msg = self.apply_patch(proj_path, patch_data, err_ctx.failed_file)

            if not patch_applied:
                print(f"\033[1;31m[!] Failed to apply patch: {patch_msg}\033[0m")
                if self.git_automator and iter_cp:
                    self.git_automator.rollback_to_commit(proj_path, iter_cp.commit_sha, hard=True)
                    self.git_automator.checkout_branch(proj_path, base_branch)
                attempts.append(PatchAttempt(
                    iteration=iteration,
                    failed_file=err_ctx.failed_file,
                    error_summary=current_error,
                    root_cause=root_cause,
                    patch_applied=False,
                    test_passed_after=False
                ))
                continue

            print(f"\033[1;32m[OK] {patch_msg}\033[0m")
            print("\033[1;34m[*] Re-running test suite in sandbox...\033[0m")
            re_passed, re_code, re_stdout, re_stderr = self.run_tests(proj_path, custom_test_cmd)

            attempts.append(PatchAttempt(
                iteration=iteration,
                failed_file=err_ctx.failed_file,
                error_summary=current_error,
                root_cause=root_cause,
                patch_applied=True,
                test_passed_after=re_passed
            ))

            if re_passed:
                print(f"\033[1;32m[OK] SUCCESS! Bug resolved and all tests passed on iteration {iteration}!\033[0m")
                # Auto-commit the fix and merge isolated fix branch back to base branch
                if self.git_automator:
                    commit_ctx = f"fix: {root_cause} (resolves {initial_error})"
                    c_ok, c_msg, c_sha = self.git_automator.auto_commit(proj_path, task_context=commit_ctx)
                    print(f"\033[1;32m[*] Git Automator: Created fix commit [{c_sha[:8]}]: {c_msg}\033[0m")
                    m_ok, m_msg = self.git_automator.merge_branch(proj_path, source_branch=iter_branch, target_branch=base_branch)
                    if m_ok:
                        print(f"\033[1;32m[*] Git Automator: Merged '{iter_branch}' into '{base_branch}'\033[0m")

                summary = DebugSummary(
                    resolved=True,
                    iterations_run=iteration,
                    max_iterations=self.max_retries,
                    original_error=initial_error,
                    final_error="None",
                    attempts=attempts
                )
                self._save_report(proj_path, summary)
                return summary

            # Rollback failed patch cleanly before next attempt
            if self.git_automator and iter_cp:
                print(f"\033[1;33m[*] Git Automator: Tests still failing; rolling back bad patch to checkpoint {iter_cp.tag_name}...\033[0m")
                self.git_automator.rollback_to_commit(proj_path, iter_cp.commit_sha, hard=True)
                self.git_automator.checkout_branch(proj_path, base_branch)

            # Prepare context for next iteration
            err_ctx = ErrorAnalyzer.analyze_failure(proj_path, re_stderr, re_stdout)
            current_error = err_ctx.error_summary
            print(f"\033[1;33m[!] Tests failed after patch: {current_error}\033[0m")

        print(f"\033[1;31m[!] Max iterations ({self.max_retries}) reached without full resolution.\033[0m")
        # Final safety rollback to pristine baseline
        if self.git_automator and baseline_cp:
            print(f"\033[1;33m[*] Git Automator: Safely rolling back project to pre-healing baseline checkpoint...\033[0m")
            self.git_automator.rollback_to_commit(proj_path, baseline_cp.commit_sha, hard=True)
            self.git_automator.checkout_branch(proj_path, base_branch)

        summary = DebugSummary(
            resolved=False,
            iterations_run=self.max_retries,
            max_iterations=self.max_retries,
            original_error=initial_error,
            final_error=current_error,
            attempts=attempts
        )
        self._save_report(proj_path, summary)
        return summary

    def _save_report(self, project_dir: Path, summary: DebugSummary):
        report_file = project_dir / "debug_summary.json"
        try:
            report_file.write_text(summary.to_json(), encoding="utf-8")
            print(f"[*] Diagnostic report saved to {report_file}")
        except Exception:
            pass


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python self_healer.py <project_directory> [test_command]")
        print("Example: python self_healer.py /workspace/projects/my_app 'pytest'")
        sys.exit(1)

    proj = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else None
    healer = SelfHealer()
    res = healer.auto_heal_project(proj, custom_test_cmd=cmd)
    print(res.to_json())
    sys.exit(0 if res.resolved else 1)
