#!/usr/bin/env python3
"""
git_automator.py - Autonomous Git & Version Control Subsystem for AI OS
Author: Version Control Architect and DevOps Automation Engineer

Provides automated repository initialization, stack-tailored .gitignore generation,
AI-powered conventional commit generation, isolated feature branching, checkpoints,
and programmatic rollbacks for AI-generated projects.
"""

import os
import sys
import re
import json
import time
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Optional GitPython import with fallback to subprocess runner
try:
    import git
    HAS_GITPYTHON = True
except ImportError:
    git = None
    HAS_GITPYTHON = False


# ==============================================================================
# Standard Stack-Tailored .gitignore Templates
# ==============================================================================
GITIGNORE_TEMPLATES: Dict[str, str] = {
    "python": """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Distribution / packaging
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Testing & Coverage
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/
.hypothesis/
.mypy_cache/

# Logs & Databases
*.log
*.sqlite
*.sqlite3
.ai_blueprint.json
""",

    "node": """# Dependency directories
node_modules/
jspm_packages/

# Production build outputs
dist/
build/
out/
.next/
.nuxt/
.cache/

# Logs
npm-debug.log*
yarn-debug.log*
yarn-error.log*
lerna-debug.log*
.pnpm-debug.log*

# Environment files
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# OS & Editor
.DS_Store
Thumbs.db
.ai_blueprint.json
""",

    "rust": """# Generated target directories
/target/
**/*.rs.bk
*.pdb

# Backup files
*.bk
*.orig

# Local environment
.env
.ai_blueprint.json
""",

    "go": """# Binaries for programs and plugins
*.exe
*.exe~
*.dll
*.so
*.dylib
bin/
pkg/

# Test binaries
*.test
*.out

# Go workspace
go.work
go.work.sum

# Dependency directory
vendor/
.env
.ai_blueprint.json
""",

    "c": """# Compiled Object files
*.slo
*.lo
*.o
*.obj

# Precompiled Headers
*.gch
*.pch

# Compiled Dynamic / Static libraries
*.so
*.dylib
*.dll
*.a
*.lib
*.la
*.lai

# Executables
*.exe
*.out
*.app
bin/
build/
cmake-build-*/
compile_commands.json
.env
.ai_blueprint.json
""",

    "cpp": """# Compiled Object files
*.o
*.obj
*.so
*.dylib
*.dll
*.a
*.lib

# Executables & Build
bin/
build/
cmake-build-*/
compile_commands.json
.cache/
.env
.ai_blueprint.json
""",

    "generic": """# AI OS Generic Project Ignore
.env
*.log
*.tmp
*.temp
.DS_Store
Thumbs.db
.vscode/
.idea/
.ai_blueprint.json
"""
}


COMMIT_MESSAGE_SYSTEM_PROMPT = """You are an expert DevOps engineer and Git version control specialist.
Generate a concise, high-quality Conventional Commit message based on the provided Git diff and task context.

CONVENTIONS:
Format: <type>(<scope>): <short summary in imperative mood>

Types:
- feat: A new feature or endpoint
- fix: A bug fix or error correction
- test: Adding or updating test cases
- refactor: Code restructuring without changing external behavior
- docs: Documentation or comment updates
- style: Formatting or linting fixes
- chore: Build process, dependencies, or configuration changes

RULES:
1. Provide ONLY the commit message (one line subject, optionally followed by blank line and bullet points).
2. Keep the first line under 72 characters.
3. No code blocks, no quotes around the output, no commentary.
"""


@dataclass
class GitStatusResult:
    is_repo: bool
    current_branch: str
    staged_files: List[str]
    unstaged_files: List[str]
    untracked_files: List[str]
    clean: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GitCheckpoint:
    commit_sha: str
    tag_name: str
    branch: str
    timestamp: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GitAutomator:
    """
    Autonomous Git & Version Control Manager.
    Handles repository initialization, conventional commits, branching,
    safety checkpoints, and test-failure rollbacks.
    """

    def __init__(self, router: Optional[Any] = None):
        self.router = router
        self.config = {}
        if self.router is None:
            try:
                from ai_shell_agent import AIRouter, ConfigManager
                self.config = ConfigManager.load() if ConfigManager else {}
                self.router = AIRouter(self.config) if AIRouter else None
            except ImportError:
                self.router = None
        self.git_bin = shutil.which("git")

    def _run_git(self, project_path: Path, args: List[str], check: bool = True) -> Tuple[int, str, str]:
        """Runs a git CLI command inside the target project directory."""
        if not self.git_bin:
            return 1, "", "Git binary not found in system PATH."

        cmd = [self.git_bin] + args
        try:
            res = subprocess.run(
                cmd,
                cwd=str(project_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=check
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else str(e)
        except Exception as e:
            return 1, "", str(e)

    def is_git_repo(self, project_path: Path) -> bool:
        """Verifies if the directory is an active git repository."""
        code, stdout, _ = self._run_git(project_path, ["rev-parse", "--is-inside-work-tree"], check=False)
        return (code == 0 and stdout == "true")

    def init_repository(self,
                        project_path: Path,
                        stack: str = "generic",
                        default_branch: str = "main",
                        initial_commit: bool = True,
                        project_name: Optional[str] = None,
                        project_type: Optional[str] = None) -> Tuple[bool, str]:
        """
        Initializes a new Git repository, configures default identity,
        generates stack-tailored .gitignore, and creates the initial commit.
        """
        stack = project_type or stack
        proj = Path(project_path).resolve()
        proj.mkdir(parents=True, exist_ok=True)

        # 1. git init with default branch
        init_args = ["init"]
        if default_branch:
            init_args.extend(["-b", default_branch])

        code, out, err = self._run_git(proj, init_args, check=False)
        if code != 0:
            # Older git versions might not support -b in init
            code, out, err = self._run_git(proj, ["init"], check=False)
            if code != 0:
                return False, f"Failed to initialize git repository: {err}"
            if default_branch:
                self._run_git(proj, ["checkout", "-b", default_branch], check=False)

        # 2. Ensure local git config has identity
        self._run_git(proj, ["config", "--local", "user.name", "AI OS Developer"], check=False)
        self._run_git(proj, ["config", "--local", "user.email", "developer@ai-os.local"], check=False)

        # 3. Generate stack-tailored .gitignore
        self.generate_gitignore(proj, stack)

        # 4. Create Initial Commit
        if initial_commit:
            name = project_name or proj.name
            stage_ok, stage_msg = self.stage_all(proj)
            if stage_ok:
                commit_msg = f"feat(init): initialize {name} repository scaffold [{stack}]"
                code, c_out, c_err = self._run_git(proj, ["commit", "-m", commit_msg], check=False)
                if code == 0:
                    return True, f"Repository initialized with initial commit on branch '{default_branch}'."
                else:
                    return True, f"Repository initialized (nothing to commit yet: {c_err})."

        return True, f"Repository initialized on branch '{default_branch}'."

    initialize_repository = init_repository

    def generate_gitignore(self, project_path: Path, stack: str = "generic") -> str:
        """Writes or updates .gitignore tailored to the tech stack."""
        norm_stack = stack.lower().strip()
        template = GITIGNORE_TEMPLATES.get(norm_stack, GITIGNORE_TEMPLATES["generic"])

        gitignore_file = project_path / ".gitignore"
        if gitignore_file.exists():
            existing = gitignore_file.read_text(encoding="utf-8")
            # If template entries not in existing, append
            if template.strip() not in existing:
                updated = existing.rstrip() + "\n\n" + template
                gitignore_file.write_text(updated, encoding="utf-8")
        else:
            gitignore_file.write_text(template, encoding="utf-8")

        return str(gitignore_file)

    def get_status(self, project_path: Path) -> GitStatusResult:
        """Returns structured status of working directory and staging area."""
        proj = Path(project_path).resolve()
        if not self.is_git_repo(proj):
            return GitStatusResult(False, "", [], [], [], True)

        # Branch
        _, branch, _ = self._run_git(proj, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)

        # Porcelain status
        _, out, _ = self._run_git(proj, ["status", "--porcelain"], check=False)

        staged = []
        unstaged = []
        untracked = []

        for line in out.splitlines():
            if len(line) < 3:
                continue
            index_status = line[0]
            worktree_status = line[1]
            file_path = line[3:].strip()

            if index_status in ("A", "M", "R", "D", "C"):
                staged.append(file_path)
            if worktree_status in ("M", "D"):
                unstaged.append(file_path)
            elif index_status == "?" and worktree_status == "?":
                untracked.append(file_path)

        clean = (len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0)
        return GitStatusResult(
            is_repo=True,
            current_branch=branch or "HEAD",
            staged_files=staged,
            unstaged_files=unstaged,
            untracked_files=untracked,
            clean=clean
        )

    def stage_all(self, project_path: Path) -> Tuple[bool, str]:
        """Stages all working directory changes (git add -A)."""
        code, out, err = self._run_git(project_path, ["add", "-A"], check=False)
        return (code == 0), (out if code == 0 else err)

    def get_diff(self, project_path: Path, staged: bool = True) -> str:
        """Returns the unified diff of staged or working tree changes."""
        args = ["diff", "--cached"] if staged else ["diff"]
        code, out, _ = self._run_git(project_path, args, check=False)
        return out if code == 0 else ""

    def generate_conventional_commit_message(self,
                                             project_path: Path,
                                             task_context: Optional[str] = None,
                                             diff_text: Optional[str] = None) -> str:
        """
        Analyzes code diff and task context to produce an intelligent
        Conventional Commit message. Uses local LLM with rule-based fallback.
        """
        diff = diff_text if diff_text is not None else self.get_diff(project_path, staged=True)
        status = self.get_status(project_path)
        all_changed = status.staged_files or status.unstaged_files

        # 1. Try LLM Generation via AIRouter
        if self.router and (diff.strip() or task_context):
            user_prompt = f"TASK CONTEXT:\n{task_context or 'Code updates'}\n\nCHANGED FILES:\n{', '.join(all_changed[:10])}\n\nSTAGED DIFF:\n{diff[:3000]}"
            try:
                success, response = self.router.query(COMMIT_MESSAGE_SYSTEM_PROMPT, user_prompt)
                if success and response.strip():
                    cleaned = response.strip().splitlines()[0].strip().strip('"').strip("'")
                    # Verify Conventional Commit format: type(scope): message or type: message
                    if re.match(r"^(feat|fix|test|refactor|docs|style|chore|perf|ci)(\([a-zA-Z0-9_\-\.]+\))?:\s+.+", cleaned, re.IGNORECASE):
                        return cleaned
            except Exception:
                pass

        # 2. Rule-based Heuristic Fallback
        return self._heuristic_commit_message(all_changed, task_context, diff)

    def _heuristic_commit_message(self, changed_files: List[str], task_context: Optional[str], diff: str) -> str:
        """Rule-based conventional commit generator."""
        if task_context:
            tc_lower = task_context.lower()
            if "fix" in tc_lower or "bug" in tc_lower or "repair" in tc_lower or "heal" in tc_lower:
                clean_desc = re.sub(r"^(fixed|fix|repair|healed)\s*", "", task_context, flags=re.IGNORECASE).strip()
                return f"fix: {clean_desc[:60]}"
            elif "test" in tc_lower:
                return f"test: {task_context[:60]}"
            elif "add" in tc_lower or "create" in tc_lower or "implement" in tc_lower:
                return f"feat: {task_context[:60]}"

        if not changed_files:
            return "chore: update project files"

        # Inspect file extensions and paths
        has_tests = any("test" in f.lower() for f in changed_files)
        has_docs = any(f.lower().endswith((".md", ".txt", ".rst", ".doc")) for f in changed_files)
        has_config = any(f.lower().endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".gitignore")) for f in changed_files)

        primary = changed_files[0]
        scope = Path(primary).stem

        if has_tests and len(changed_files) == 1:
            return f"test({scope}): update test assertions"
        elif has_docs and len(changed_files) == 1:
            return f"docs({scope}): update documentation"
        elif has_config and len(changed_files) == 1:
            return f"chore({scope}): update configuration"

        # Check diff keywords
        if "def test_" in diff or "describe(" in diff or "it(" in diff:
            return f"test({scope}): add automated verification tests"
        elif "except " in diff or "catch " in diff or "return err" in diff:
            return f"fix({scope}): handle runtime error condition"
        elif "+" in diff:
            return f"feat({scope}): implement component logic in {len(changed_files)} file(s)"

        return f"chore: update {len(changed_files)} project file(s)"

    def auto_commit(self,
                    project_path: Path,
                    custom_message: Optional[str] = None,
                    stage_all: bool = True,
                    task_context: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        Stages changes, generates conventional commit message, and commits.
        Returns: (success, commit_message, commit_sha)
        """
        proj = Path(project_path).resolve()
        if not self.is_git_repo(proj):
            return False, "Not a valid git repository", ""

        if stage_all:
            self.stage_all(proj)

        status = self.get_status(proj)
        if not status.staged_files:
            return False, "No staged changes to commit", ""

        msg = custom_message
        if not msg:
            diff = self.get_diff(proj, staged=True)
            msg = self.generate_conventional_commit_message(proj, task_context=task_context, diff_text=diff)

        code, out, err = self._run_git(proj, ["commit", "-m", msg], check=False)
        if code != 0:
            return False, f"Git commit failed: {err}", ""

        # Get the commit SHA
        _, sha, _ = self._run_git(proj, ["rev-parse", "HEAD"], check=False)
        return True, msg, sha

    def create_checkpoint(self, project_path: Path, reason: str = "safety-checkpoint") -> GitCheckpoint:
        """
        Creates an immutable safety checkpoint before potentially destructive actions.
        Stages and commits any uncommitted edits, then creates an annotated Git tag.
        """
        proj = Path(project_path).resolve()
        status = self.get_status(proj)

        # If dirty, create an auto-commit for the checkpoint
        if not status.clean:
            self.stage_all(proj)
            self.auto_commit(proj, custom_message=f"chore(checkpoint): pre-action snapshot for {reason}")

        # Get current HEAD SHA and branch
        _, sha, _ = self._run_git(proj, ["rev-parse", "HEAD"], check=False)
        _, branch, _ = self._run_git(proj, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)

        timestamp_str = str(int(time.time()))
        safe_reason = re.sub(r"[^a-zA-Z0-9_\-]", "-", reason).strip("-")[:30]
        tag_name = f"checkpoint-{timestamp_str}-{safe_reason}"

        # Create tag
        self._run_git(proj, ["tag", "-a", tag_name, "-m", f"AI OS Checkpoint: {reason}"], check=False)

        return GitCheckpoint(
            commit_sha=sha,
            tag_name=tag_name,
            branch=branch or "main",
            timestamp=timestamp_str,
            reason=reason
        )

    def rollback_to_commit(self, project_path: Path, target_ref_or_sha: str, hard: bool = True) -> Tuple[bool, str]:
        """
        Rolls back the working tree and index to a specific commit SHA or checkpoint tag.
        """
        proj = Path(project_path).resolve()
        if not self.is_git_repo(proj):
            return False, "Not a valid git repository"

        reset_mode = "--hard" if hard else "--mixed"
        code, out, err = self._run_git(proj, ["reset", reset_mode, target_ref_or_sha], check=False)
        if code == 0:
            # Clean any leftover untracked build artifacts
            if hard:
                self._run_git(proj, ["clean", "-fd"], check=False)
            return True, f"Successfully rolled back to ref '{target_ref_or_sha}'."
        return False, f"Rollback failed: {err}"

    def create_feature_branch(self, project_path: Path, branch_name: str, checkout: bool = True) -> Tuple[bool, str]:
        """Creates and optionally checks out an isolated feature or bug-fix branch."""
        proj = Path(project_path).resolve()
        clean_branch = re.sub(r"[^a-zA-Z0-9_\-\/\.]", "-", branch_name)

        args = ["checkout", "-b", clean_branch] if checkout else ["branch", clean_branch]
        code, out, err = self._run_git(proj, args, check=False)
        if code == 0:
            return True, f"Branch '{clean_branch}' created and active."
        return False, f"Failed to create branch: {err}"

    def checkout_branch(self, project_path: Path, branch_name: str) -> Tuple[bool, str]:
        """Switches to the specified branch."""
        proj = Path(project_path).resolve()
        code, out, err = self._run_git(proj, ["checkout", branch_name], check=False)
        return (code == 0), (out if code == 0 else err)

    def merge_branch(self, project_path: Path, source_branch: str, target_branch: str = "main") -> Tuple[bool, str]:
        """Merges source branch into target branch."""
        proj = Path(project_path).resolve()
        # 1. Switch to target
        ok, msg = self.checkout_branch(proj, target_branch)
        if not ok:
            return False, f"Cannot switch to target branch '{target_branch}': {msg}"

        # 2. Merge
        code, out, err = self._run_git(proj, ["merge", "--no-ff", "-m", f"chore: merge '{source_branch}' into {target_branch}", source_branch], check=False)
        if code == 0:
            return True, f"Successfully merged '{source_branch}' into '{target_branch}'."
        return False, f"Merge conflict or failure: {err}"

    def get_history(self, project_path: Path, limit: int = 10) -> List[Dict[str, str]]:
        """Returns structured commit history."""
        proj = Path(project_path).resolve()
        code, out, _ = self._run_git(proj, ["log", f"-n{limit}", "--pretty=format:%H%x09%an%x09%ar%x09%s"], check=False)
        if code != 0 or not out:
            return []

        commits = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 4:
                commits.append({
                    "sha": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "subject": parts[3]
                })
        return commits

    def list_checkpoints(self, project_path: Path) -> List[Dict[str, str]]:
        """Lists all safety checkpoints and tags in the repository."""
        proj = Path(project_path).resolve()
        code, out, _ = self._run_git(proj, ["tag", "-l", "checkpoint-*", "-n1"], check=False)
        if code != 0 or not out:
            return []

        checkpoints = []
        for line in out.splitlines():
            parts = line.strip().split(maxsplit=1)
            if parts:
                tag = parts[0]
                desc = parts[1] if len(parts) > 1 else ""
                checkpoints.append({"tag": tag, "description": desc})
        return checkpoints


# ==============================================================================
# CLI Entrypoint for Testing / Direct Invocation
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python git_automator.py <command> [args...]")
        print("Commands:")
        print("  init <project_dir> [stack]    - Initialize repo with stack .gitignore")
        print("  status <project_dir>          - Get status of project")
        print("  commit <project_dir> [msg]    - Auto-commit staged changes")
        print("  checkpoint <project_dir> [reason] - Create safety snapshot checkpoint")
        print("  rollback <project_dir> <ref>  - Rollback to commit or checkpoint")
        print("  history <project_dir>         - View recent commits")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    automator = GitAutomator()

    if cmd == "init" and len(sys.argv) >= 3:
        p = Path(sys.argv[2])
        st = sys.argv[3] if len(sys.argv) > 3 else "generic"
        ok, msg = automator.init_repository(p, stack=st)
        print(f"[{'OK' if ok else 'ERR'}] {msg}")

    elif cmd == "status" and len(sys.argv) >= 3:
        p = Path(sys.argv[2])
        status = automator.get_status(p)
        print(json.dumps(status.to_dict(), indent=2))

    elif cmd == "commit" and len(sys.argv) >= 3:
        p = Path(sys.argv[2])
        m = sys.argv[3] if len(sys.argv) > 3 else None
        ok, msg, sha = automator.auto_commit(p, custom_message=m)
        print(f"[{'OK' if ok else 'ERR'}] {msg} ({sha})")

    elif cmd == "checkpoint" and len(sys.argv) >= 3:
        p = Path(sys.argv[2])
        r = sys.argv[3] if len(sys.argv) > 3 else "manual"
        cp = automator.create_checkpoint(p, reason=r)
        print(f"[OK] Checkpoint created: {cp.tag_name} (SHA: {cp.commit_sha})")

    elif cmd == "rollback" and len(sys.argv) >= 4:
        p = Path(sys.argv[2])
        ref = sys.argv[3]
        ok, msg = automator.rollback_to_commit(p, ref)
        print(f"[{'OK' if ok else 'ERR'}] {msg}")

    elif cmd == "history" and len(sys.argv) >= 3:
        p = Path(sys.argv[2])
        h = automator.get_history(p)
        print(json.dumps(h, indent=2))
