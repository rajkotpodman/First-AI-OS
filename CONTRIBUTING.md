# Contributing to First AI OS (`CONTRIBUTING.md`)

Thank you for your interest in contributing to **First AI OS**! We are building the world's premier minimal, autonomous Linux distribution engineered specifically for local edge AI, autonomous coding agents, and zero-to-GUI desktop paradigms.

---

## Table of Contents
1. [Code of Conduct](#1-code-of-conduct)
2. [Development Environment Setup](#2-development-environment-setup)
3. [Repository Layout](#3-repository-layout)
4. [Running the Test Suite](#4-running-the-test-suite)
5. [Code Quality & Style Standards](#5-code-quality--style-standards)
6. [Subsystem Development Guidelines](#6-subsystem-development-guidelines)
7. [Testing ISO Builds Locally](#7-testing-iso-builds-locally)
8. [Git Commit Conventions & Pull Request Workflow](#8-git-commit-conventions--pull-request-workflow)

---

## 1. Code of Conduct
By participating in this project, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md). Please treat all contributors with respect, empathy, and professional courtesy.

---

## 2. Development Environment Setup

First AI OS can be developed and tested on Linux, macOS, or Windows (via WSL2 or container):

### Prerequisites
- **Python:** Version 3.10, 3.11, or 3.12.
- **Git:** Version 2.25+.
- **Docker or Podman:** For testing sandbox containers and running `docker-compose`.
- **Build Tools (for ISO testing):** `xorriso`, `syslinux`, `squashfs-tools`, `mtools`, `curl`, `tar`.

### Clone & Environment Initialization
```bash
# Clone the repository
git clone https://github.com/rajkotpodman/First-AI-OS.git
cd First-AI-OS

# Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install development and testing dependencies
pip install --upgrade pip setuptools wheel
pip install flake8 pytest pytest-cov pyyaml bandit pre-commit

# Install pre-commit hooks
pre-commit install
```

---

## 3. Repository Layout

```text
First-AI-OS/
├── build_base_os.sh               # Master automated Alpine v3.21 ISO generation script
├── toggle_gui.sh                  # CLI script to switch between TTY1 and Sway Wayland
├── docker-compose.yml             # Containerized development & Ollama mock environment
├── configs/                       # System initialization, bootloader & daemon configs
│   ├── ai-os.initd                # OpenRC background services definition
│   ├── inittab                    # TTY1 auto-boot configuration
│   ├── isolinux.cfg               # Syslinux bootloader menu
│   ├── seccomp_profile.json       # Hardened container syscall filters
│   └── sway/                      # Minimal Sway, Waybar, and Foot configurations
├── src/                           # The 19 Core Autonomous AI OS Subsystems
│   ├── main_orchestrator.py       # Master OS entrypoint & event loop
│   ├── ai_shell_agent.py          # Natural language CLI interpreter
│   ├── hardware_manager.py        # Hardware acceleration & GPU detection
│   ├── personal_memory.py         # Persistent user memory & context
│   ├── model_router.py            # Hybrid offline/online AI model gateway
│   ├── project_architect.py       # Autonomous software scaffolder
│   ├── self_healer.py             # Automated testing & unified diff patcher
│   ├── sandbox_runner.py          # Isolated Docker/Podman execution sandbox
│   ├── system_indexer.py          # SQLite FTS5 & AST code knowledge graph
│   └── ...                        # Additional core subsystems
├── plugins/                       # Modular third-party plugin directory
├── tests/                         # Complete automated unit & integration test suite
│   ├── test_master_orchestrator.py
│   ├── test_hardware_manager.py
│   ├── test_self_healer.py
│   └── ...
└── docs/                          # Architectural and operational documentation
```

---

## 4. Running the Test Suite

First AI OS maintains a comprehensive automated test suite covering all 19 subsystems (59+ unit tests). All tests must pass before submitting a Pull Request:

### Run Full Test Suite via unittest:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Run Full Test Suite via pytest with Coverage:
```bash
pytest tests/ --cov=src --cov-report=term-missing
```

### Run Specific Subsystem Tests:
```bash
# Test the self-debugging healer loop
python -m unittest tests/test_self_healer.py

# Test the hardware detection engine
python -m unittest tests/test_hardware_manager.py

# Test container sandbox isolation
python -m unittest tests/test_sandbox_runner.py
```

---

## 5. Code Quality & Style Standards

1. **Python Standards:** Follow **PEP 8** style conventions.
2. **Type Annotations:** All new functions and methods must include Python type hints (`typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`).
3. **Docstrings:** Use Google or Sphinx style docstrings for all modules, classes, and public functions.
4. **Error Handling:** Never swallow exceptions with bare `except: pass`. Log or handle specific exceptions with graceful fallbacks.
5. **Path Resolution:** Always resolve paths dynamically using `os.path.realpath(__file__)` or `pathlib.Path` so that scripts execute correctly whether called directly or via symlink in `/usr/bin/`.

### Run Linters:
```bash
flake8 src tests --count --max-line-length=120 --statistics
```

---

## 6. Subsystem Development Guidelines

When modifying existing subsystems or introducing new capabilities:
- **Zero-Crash Resilience:** All subsystems must employ fallback import blocks (`try: ... except ImportError: ... = None`) so that missing optional dependencies do not prevent the master OS orchestrator from booting into TTY1.
- **Resource Constraints:** The rootfs uncompressed size must stay strictly under **500 MB**. Do not introduce large, heavy dependencies unless wrapped in a containerized plugin.
- **Persistence Guarantees:** Any data that should survive a reboot must be written under `/workspace/` or `/etc/ai_os/`.

---

## 7. Testing ISO Builds Locally

If you modify `build_base_os.sh`, kernel configurations, or OpenRC init scripts:
1. Validate shell syntax:
   ```bash
   bash -n build_base_os.sh
   ```
2. Build the ISO locally (requires Linux or WSL with sudo):
   ```bash
   sudo ./build_base_os.sh
   ```
3. Test the generated `ai-os-3.21-x86_64.iso` in QEMU:
   ```bash
   qemu-system-x86_64 -m 2G -smp 2 -cdrom ai-os-3.21-x86_64.iso -boot d -net nic -net user
   ```

---

## 8. Git Commit Conventions & Pull Request Workflow

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` A new feature or subsystem enhancement (e.g., `feat: add ROCm GPU telemetry to hardware_manager`)
- `fix:` A bug fix (e.g., `fix: resolve symlink path evaluation in main_orchestrator`)
- `docs:` Documentation improvements (e.g., `docs: expand HOWTOUSE.md walkthrough examples`)
- `test:` Adding or refactoring unit tests (e.g., `test: add coverage for git_automator checkpoint rollback`)
- `refactor:` Code improvements without functional changes (e.g., `refactor: optimize SQLite AST index queries`)
- `ci:` Changes to GitHub Actions workflows (e.g., `ci: add Python 3.12 to matrix build`)

### Pull Request Steps:
1. Fork the repository and create your feature branch:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Commit your changes with clear, descriptive commit messages.
3. Ensure all 59+ unit tests pass:
   ```bash
   python -m unittest discover tests
   ```
4. Push your branch to GitHub and open a Pull Request against the `main` branch.
5. Fill out the PR template checklist completely.

