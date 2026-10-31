# First AI OS — Complete Operational Handbook & User Guide (`HOWTOUSE.md`)

Welcome to the definitive user handbook for **First AI OS**, an autonomous, hardened, minimal Linux operating system engineered specifically for edge AI agents, local Large Language Model (LLM) execution, zero-to-GUI desktop switching, autonomous project architecture, and self-healing software development.

---

## Table of Contents
1. [System Overview & Operating Philosophy](#1-system-overview--operating-philosophy)
2. [First Boot & System Initialization](#2-first-boot--system-initialization)
3. [Global CLI Command Suite Reference](#3-global-cli-command-suite-reference)
4. [In-Depth Guide to the 19 Core Subsystems](#4-in-depth-guide-to-the-19-core-subsystems)
   - [Subsystem 1: Master OS Orchestrator](#subsystem-1-master-os-orchestrator-main_orchestratorpy)
   - [Subsystem 2: Security Daemon & Audit Logging](#subsystem-2-security-daemon--audit-logging-security_daemonpy)
   - [Subsystem 3: Hardware Acceleration & Inference Tiers](#subsystem-3-hardware-acceleration--inference-tiers-hardware_managerpy)
   - [Subsystem 4: Personal Memory & Context Engine](#subsystem-4-personal-memory--context-engine-personal_memorypy)
   - [Subsystem 5: Hybrid Model Router & Network Fallback](#subsystem-5-hybrid-model-router--network-fallback-model_routerpy)
   - [Subsystem 6: Autonomous Cron & Task Scheduler](#subsystem-6-autonomous-cron--task-scheduler-ai_cron_daemonpy)
   - [Subsystem 7: Knowledge Graph & AST Symbol Indexer](#subsystem-7-knowledge-graph--ast-symbol-indexer-system_indexerpy)
   - [Subsystem 8: Rich Interactive Terminal UI](#subsystem-8-rich-interactive-terminal-ui-ai_terminal_uipy)
   - [Subsystem 9: Natural Language Shell Agent](#subsystem-9-natural-language-shell-agent-ai_shell_agentpy)
   - [Subsystem 10: Multimodal Voice & Vision Gateway](#subsystem-10-multimodal-voice--vision-gateway-multimodal_gatewaypy)
   - [Subsystem 11: Autonomous Project Architect](#subsystem-11-autonomous-project-architect-project_architectpy)
   - [Subsystem 12: Automated Self-Debugging & Code Healer](#subsystem-12-automated-self-debugging--code-healer-self_healerpy)
   - [Subsystem 13: Auto-Healing Dependency Resolver](#subsystem-13-auto-healing-dependency-resolver-dependency_resolverpy)
   - [Subsystem 14: Isolated Container Sandbox Runner](#subsystem-14-isolated-container-sandbox-runner-sandbox_runnerpy)
   - [Subsystem 15: Autonomous Git Automator](#subsystem-15-autonomous-git-automator-git_automatorpy)
   - [Subsystem 16: Instant Offline Documentation Engine](#subsystem-16-instant-offline-documentation-engine-offline_docs_enginepy)
   - [Subsystem 17: On-Demand Dynamic GUI Switcher](#subsystem-17-on-demand-dynamic-gui-switcher-gui_expanderpy--toggle_guish)
   - [Subsystem 18: System Updater, Backup & Rollback Engine](#subsystem-18-system-updater-backup--rollback-engine-system_updaterpy)
   - [Subsystem 19: Modular Plugin Manager](#subsystem-19-modular-plugin-manager-plugin_managerpy)
5. [End-to-End Practical Walkthroughs](#5-end-to-end-practical-walkthroughs)
   - [Walkthrough A: Generating a Full Software Project](#walkthrough-a-generating-a-full-software-project)
   - [Walkthrough B: Automated Bug Injection & Self-Healing](#walkthrough-b-automated-bug-injection--self-healing)
   - [Walkthrough C: Hardware Diagnostics & Local LLM Optimization](#walkthrough-c-hardware-diagnostics--local-llm-optimization)
   - [Walkthrough D: Launching the Sway Wayland GUI On-Demand](#walkthrough-d-launching-the-sway-wayland-gui-on-demand)
   - [Walkthrough E: Sandboxing Untrusted Scripts with Seccomp](#walkthrough-e-sandboxing-untrusted-scripts-with-seccomp)
6. [Configuration Reference (`config.yaml`)](#6-configuration-reference-configyaml)
7. [Recovery Consoles, Troubleshooting & FAQs](#7-recovery-consoles-troubleshooting--faqs)

---

## 1. System Overview & Operating Philosophy

First AI OS re-envisions the operating system from the ground up:

- **TTY-First, Zero-Overhead Kernel Architecture:** The system boots directly into an interactive AI agent on `tty1` within seconds. By omitting heavy desktop environments (X11/GNOME/KDE) from the default runlevel, the entire root filesystem stays under **500 MB uncompressed**, leaving maximum host RAM and VRAM dedicated to LLM context and neural execution.
- **OverlayFS Persistence:** The live environment provides persistent storage for `/workspace`, `/home`, `/var/lib/docker`, and `/etc/ai_os` using dynamic OverlayFS layers.
- **Dual-Plane Intelligence:** Integrates an offline-first Ollama runtime engine for complete privacy, coupled with an automated cloud failover gateway when internet connectivity is active and API keys are configured.
- **Guarded Execution:** All shell actions are vetted by an immutable cryptographic security policy engine before execution.

---

## 2. First Boot & System Initialization

### Bootloader Screen
When you power on a physical machine or virtual machine (VMware, VirtualBox, QEMU) loaded with `ai-os-3.21-x86_64.iso`, the ISOLINUX boot screen appears with a 3-second countdown:

```text
================================================================
          First AI Operating System (Alpine 3.21 x86_64)
================================================================
 [1] Boot AI OS (Virtual Kernel - Fast Boot)          [DEFAULT]
 [2] Boot AI OS (LTS Kernel - Bare Metal Hardware)
 [3] Boot AI OS (Verbose Debug Mode)
================================================================
```
- **Option 1 (Virtual Kernel):** Recommended for VMware, VirtualBox, KVM, and QEMU. Uses the lightweight `linux-virt` kernel.
- **Option 2 (LTS Kernel):** Recommended for physical laptops, desktops, and bare-metal servers for broad hardware driver support.

### Direct TTY1 Auto-Login
Upon loading the kernel and initramfs, OpenRC starts core services (`devfs`, `mdev`, `networking`, `docker`, `ai-os`). `inittab` automatically authenticates root on `tty1` and launches `/usr/bin/ai-os`, presenting the Master OS banner:

```text
 ╔════════════════════════════════════════════════════════════════╗
 ║              FIRST AI OPERATING SYSTEM v1.0.0                  ║
 ║      Autonomous Hardened Alpine Linux Intelligence Core        ║
 ╚════════════════════════════════════════════════════════════════╝
 [*] System Audit: OK | Hardware: Tier 1 (NVIDIA 12GB) | Net: ONLINE
 [*] Memory: Loaded 4 profile parameters | Workspaces: /workspace
 [AI-OS:root ~]# 
```

---

## 3. Global CLI Command Suite Reference

First AI OS exposes dedicated binaries pre-linked into `/usr/local/bin` and `/usr/bin`. All commands can be run from the master shell or fallback bash consoles:

| Command | Subsystem Link | Primary Purpose |
| :--- | :--- | :--- |
| `ai-os` | `main_orchestrator.py` | Launches the interactive Master OS Orchestrator shell. |
| `ai-os-shell` | `ai_shell_agent.py` | Direct natural language command interpreter and execution agent. |
| `ai-hw` | `hardware_manager.py` | Hardware diagnostics, GPU detection, and Ollama tier configuration. |
| `ai-index` | `system_indexer.py` | Filesystem AST scanner, code search, and symbol reference finder. |
| `ai-router` | `model_router.py` | Network reachability tester, prompt router, and offline model invoker. |
| `ai-doc` | `ai_doc.py` / `offline_docs` | High-speed offline technical documentation engine with FTS5 search. |
| `ai-plugin` | `plugin_manager.py` | Discovery, installation, inspection, and verification of AI OS plugins. |
| `ai-schedule`| `ai_cron_daemon.py` | Autonomous background cron daemon management and scheduled task creation. |
| `ai-vision` | `multimodal_gateway.py` | Multimodal image and visual asset analysis. |
| `ai-voice` | `multimodal_gateway.py` | Voice transcription, audio capture, and speech synthesis gateway. |
| `ai-dashboard`| `web_dashboard.py` | Launches local monitoring web UI at `http://localhost:8080`. |
| `gui` | `toggle_gui.sh` | Dynamically provisions and launches the Sway Wayland GUI desktop. |

---

## 4. In-Depth Guide to the 19 Core Subsystems

### Subsystem 1: Master OS Orchestrator (`main_orchestrator.py`)
- **Role:** The central nervous system of AI OS. Initializes all 19 subsystems on boot in their proper dependency order.
- **Boot Sequence:**
  1. Bootstraps `SecurityDaemon` and verifies system file integrity.
  2. Runs `HardwareManager` to probe CPU cores, AVX vectors, and GPU VRAM.
  3. Loads `PersonalMemoryEngine` session data from `/workspace/.ai_os/memory.json`.
  4. Probes network DNS resolvers via `ModelRouter` to set `ONLINE` or `OFFLINE` status.
  5. Starts background `AICronDaemon` workers.
  6. Presents the rich interactive TTY interface.
- **Interactive Commands inside `ai-os`:**
  - `help` — Displays all available commands.
  - `status` — Real-time health matrix of all 19 subsystems.
  - `project <description>` — Triggers the Autonomous Project Architect.
  - `heal <path>` — Runs the automated Self-Debugging loop on a codebase.
  - `index <dir>` — Updates the AST knowledge graph.
  - `gui` — Transitions system from TTY to Sway Wayland desktop.
  - `exit` — Cleanly flushes personal memory, commits Git checkpoints, and halts.

### Subsystem 2: Security Daemon & Audit Logging (`security_daemon.py`)
- **Role:** Enforces mandatory guardrails and immutable SHA-256 audit trails.
- **Features:**
  - Blocks dangerous destructive operations (e.g., `rm -rf /`, `mkfs`, raw drive writes).
  - Validates container seccomp syscall filters before sandbox execution.
  - Logs every executed command, timestamp, and exit code to `/var/log/ai_security_audit.json`.
- **Usage:**
  ```bash
  python3 -c "from security_daemon import SecurityDaemon; sd = SecurityDaemon(); print(sd.audit_system())"
  ```

### Subsystem 3: Hardware Acceleration & Inference Tiers (`hardware_manager.py`)
- **Role:** Automatically selects the optimal local LLM based on detected hardware.
- **Optimization Tiers:**
  - **Tier 1 (High GPU, VRAM ≥ 8 GB):** Model `llama3.1:8b` or `qwen2.5:14b`, 99 GPU layers offloaded, 8192 context window.
  - **Tier 2 (Hybrid, VRAM 2–6 GB):** Model `llama3.2:3b` quantized, 28 GPU layers offloaded, 4096 context window.
  - **Tier 3 (CPU Only / RAM < 8 GB):** Model `llama3.2:1b`, 0 GPU layers, thread count matched to physical CPU cores, 2048 context window.
- **Commands:**
  ```bash
  ai-hw              # Full hardware acceleration summary
  ai-hw --metrics    # Expose real-time CPU/RAM/VRAM JSON metrics
  ai-hw --configure  # Regenerate /etc/ai_os/ollama.env configuration
  ```

### Subsystem 4: Personal Memory & Context Engine (`personal_memory.py`)
- **Role:** Maintains persistent user preferences, past project blueprints, coding conventions, and session history across reboots.
- **Storage:** Persisted at `/workspace/.ai_os/memory.json`.
- **API & Usage:**
  ```python
  from personal_memory import PersonalMemoryEngine
  memory = PersonalMemoryEngine()
  memory.store_preference("preferred_language", "Python")
  memory.record_interaction("Created FastAPI project for user")
  ```

### Subsystem 5: Hybrid Model Router & Network Fallback (`model_router.py`)
- **Role:** Routes inference queries between local models (Ollama) and cloud APIs (Anthropic, OpenAI, Gemini).
- **Routing Rules:**
  - Sensitive tokens (passwords, private keys, `/etc/shadow`) -> **Strictly Local Ollama**.
  - Simple shell syntax / low token counts -> **Local Ollama**.
  - Complex multi-file architectural blueprints -> **Cloud Provider** (if online & configured).
  - Cloud API failure, timeout, or HTTP 429 -> **Instant Local Fallback**.
- **Commands:**
  ```bash
  ai-router --status                 # Display network status & active model providers
  ai-router --prompt "Explain B-Trees"
  ai-router --offline "List files"   # Force strictly local offline inference
  ```

### Subsystem 6: Autonomous Cron & Task Scheduler (`ai_cron_daemon.py`)
- **Role:** Manages periodic background agent tasks without human intervention.
- **Built-in Tasks:**
  - System Care: Clears stale `/tmp` artifacts, rotates logs, and reindexes modified code.
  - Project Health: Runs automated test suites on `/workspace/projects/*` every 6 hours.
  - Custom Web/Data Scraping & Model Sync.
- **Commands:**
  ```bash
  ai-schedule --list       # Display active background tasks
  ai-schedule --run-now    # Force immediate execution of all tasks
  ```

### Subsystem 7: Knowledge Graph & AST Symbol Indexer (`system_indexer.py`)
- **Role:** Parses Python, TypeScript, Rust, Go, and C/C++ ASTs to provide token-efficient symbol lookups to the LLM without reading full files.
- **Commands:**
  ```bash
  ai-index --scan /workspace/projects
  ai-index --symbol calculate_metrics
  ai-index --query "FastAPI"
  ai-index --tree /workspace/projects/my_api
  ```

### Subsystem 8: Rich Interactive Terminal UI (`ai_terminal_ui.py`)
- **Role:** Renders ANSI-colored split panes, progress bars, Markdown code formatting, and telemetry dashboards inside the Linux TTY console without requiring X11.

### Subsystem 9: Natural Language Shell Agent (`ai_shell_agent.py`)
- **Role:** Translates English natural language instructions into guarded Linux shell commands.
- **Example:**
  ```bash
  ai-os-shell "Find all files modified in the last 24 hours larger than 10MB"
  ```
  AI OS interprets the prompt, displays the proposed `find / -mtime -1 -size +10M` command, asks for confirmation if destructive, and presents formatted output.

### Subsystem 10: Multimodal Voice & Vision Gateway (`multimodal_gateway.py`)
- **Role:** Ingests images and audio streams.
- **Capabilities:**
  - Inspects PNG/JPG diagrams, UI mockups, or error screenshots.
  - Voice transcription and text-to-speech feedback via lightweight edge models.

### Subsystem 11: Autonomous Project Architect (`project_architect.py`)
- **Role:** Generates full, production-ready software repositories from high-level natural language prompts.
- **Lifecycle:**
  1. Translates prompt into a JSON blueprint (`project_blueprint_schema.json`).
  2. Scaffolds modular directories under `/workspace/projects/<name>`.
  3. Writes application code, unit tests, `Dockerfile`, `Makefile`, and `README.md`.
  4. Automatically initializes Git and creates the first commit.
  5. Triggers `self_healer.py` to verify unit tests pass.

### Subsystem 12: Automated Self-Debugging & Code Healer (`self_healer.py`)
- **Role:** Detects, isolates, and patches failing code.
- **Mechanism:**
  1. Executes test suite (`pytest`, `unittest`, `cargo test`, `jest`).
  2. Captures stack tracebacks and isolates failing file name and line number.
  3. Asks local AI model for a unified diff (`diff -u`).
  4. Applies diff backwards to preserve file offsets.
  5. Re-runs tests until all tests pass (up to 5 iterations).

### Subsystem 13: Auto-Healing Dependency Resolver (`dependency_resolver.py`)
- **Role:** Automatically resolves and installs missing system and language packages (`apk`, `apt`, `pip`, `npm`, `cargo`).
- **Example:** If a Python script fails with `ModuleNotFoundError: No module named 'fastapi'`, `dependency_resolver` detects the error and executes `pip install fastapi` automatically.

### Subsystem 14: Isolated Container Sandbox Runner (`sandbox_runner.py`)
- **Role:** Safely executes untrusted user or generated code inside disposable Docker/Podman containers.
- **Security Policies:**
  - Drops all Linux capabilities (`--cap-drop=ALL`).
  - Implements custom Seccomp syscall filter ([`configs/seccomp_profile.json`](file:///e:/AI%20OS/configs/seccomp_profile.json)).
  - Enforces resource limits: 2 CPU cores, 2 GB RAM, 256 max PIDs, and read-only rootfs.

### Subsystem 15: Autonomous Git Automator (`git_automator.py`)
- **Role:** Autonomous source control management for `/workspace/projects/`.
- **Features:**
  - Generates conventional commits (`feat:`, `fix:`, `refactor:`) based on code diff analysis.
  - Creates automated safety checkpoints before applying experimental self-healing diffs.
  - Enables one-command rollbacks (`git_automator.rollback()`).

### Subsystem 16: Instant Offline Documentation Engine (`offline_docs_engine.py`)
- **Role:** Full-text SQLite FTS5 search across offline Linux man pages, Python docs, Docker manuals, and Alpine packages.
- **Command:**
  ```bash
  ai-doc "docker container resource constraints"
  ```

### Subsystem 17: On-Demand Dynamic GUI Switcher (`gui_expander.py` & `toggle_gui.sh`)
- **Role:** Seamlessly switches the display from minimal TTY1 to a modern Wayland/Sway desktop environment on demand.
- **Included Desktop Components:**
  - **Sway:** Wayland tiling window manager configured in [`configs/sway/config`](file:///e:/AI%20OS/configs/sway/config).
  - **Waybar:** Top status monitoring bar with CPU, RAM, battery, and AI model stats.
  - **Foot:** Fast, lightweight Wayland terminal emulator.
- **Commands:**
  ```bash
  gui           # Launches Sway Wayland desktop
  gui --disable # Closes GUI and returns cleanly to TTY1
  ```

### Subsystem 18: System Updater, Backup & Rollback Engine (`system_updater.py`)
- **Role:** Manages atomic updates of AI OS configuration files, models, and core scripts.
- **Backup Location:** `/backups/ai_os/`
- **Commands:**
  ```bash
  python3 /opt/ai-os/system_updater.py --backup
  python3 /opt/ai-os/system_updater.py --rollback
  ```

### Subsystem 19: Modular Plugin Manager (`plugin_manager.py`)
- **Role:** Discovers and registers custom third-party extensions located in `/opt/ai-os/plugins/`.
- **Schema:** Validated against [`configs/plugin_manifest_schema.json`](file:///e:/AI%20OS/configs/plugin_manifest_schema.json).
- **Commands:**
  ```bash
  ai-plugin --list
  ai-plugin --info github_status_plugin
  ```

---

## 5. End-to-End Practical Walkthroughs

### Walkthrough A: Generating a Full Software Project
To build an entire REST API project autonomously:
1. Open the AI OS prompt:
   ```bash
   ai-os
   ```
2. Type:
   ```text
   project Build a real-time IoT sensor telemetry API with FastAPI and SQLite database
   ```
3. Watch AI OS:
   - Generate project blueprint under `/workspace/projects/iot_sensor_api/`.
   - Scaffold directories: `src/`, `models/`, `routers/`, `tests/`.
   - Write all code, `Dockerfile`, `Makefile`, and `requirements.txt`.
   - Initialize a local Git repository with commit `"feat: initial scaffold of IoT sensor API"`.
   - Run tests inside the isolated container sandbox to guarantee functionality.

### Walkthrough B: Automated Bug Injection & Self-Healing
1. In your project, suppose a syntax error or logic failure occurs:
   ```bash
   ai-os
   heal /workspace/projects/iot_sensor_api
   ```
2. AI OS runs `pytest`, detects `AssertionError: Expected 200 but received 404 in test_sensor_readings()`, parses the stack trace, computes a unified diff, patches `src/routers/sensors.py`, and re-runs the tests until all tests pass.

### Walkthrough C: Hardware Diagnostics & Local LLM Optimization
1. Run the hardware diagnostic tool:
   ```bash
   ai-hw
   ```
2. Review the output:
   ```text
   [+] CPU: Intel(R) Core(TM) i7-10750H (12 Cores) | AVX2: Supported
   [+] GPU: NVIDIA GeForce RTX 3060 Laptop GPU (6144 MB VRAM)
   [+] System RAM: 16384 MB (Free: 11200 MB)
   [*] Active Optimization: TIER 1 ACCELERATION
   [*] Recommended Model : llama3.1:8b (99 GPU Layers offloaded)
   ```
3. Generate the Ollama configuration file automatically:
   ```bash
   ai-hw --configure
   ```

### Walkthrough D: Launching the Sway Wayland GUI On-Demand
1. If you need multiple graphical windows, terminal splits, or a web browser:
   ```bash
   gui
   ```
2. Sway launches instantly with Waybar showing system telemetry.
3. Useful Keybindings:
   - <kbd>Super</kbd> + <kbd>Enter</kbd> — Open Foot terminal.
   - <kbd>Super</kbd> + <kbd>Shift</kbd> + <kbd>Q</kbd> — Close focused window.
   - <kbd>Super</kbd> + <kbd>Shift</kbd> + <kbd>E</kbd> — Exit Sway and return to TTY1.

### Walkthrough E: Sandboxing Untrusted Scripts with Seccomp
1. To safely test untrusted code without risking the host filesystem:
   ```bash
   python3 -c "
   from sandbox_runner import SandboxRunner
   runner = SandboxRunner()
   res = runner.run_code('print(10 + 20)', language='python')
   print(res)
   "
   ```

---

## 6. Configuration Reference (`config.yaml`)

The central operating system configuration file sits at `/etc/ai_os/config.yaml`:

```yaml
version: "1.0.0"

system:
  hostname: "ai-os"
  workspace_dir: "/workspace"
  log_level: "INFO"
  default_tty: "/dev/tty1"

inference:
  default_provider: "local"     # local | hybrid | cloud
  local_engine: "ollama"
  local_host: "http://localhost:11434"
  default_model: "llama3.2:3b"
  timeout_seconds: 30

security:
  enforce_seccomp: true
  seccomp_profile: "/etc/ai_os/seccomp_profile.json"
  audit_logging: true
  audit_file: "/var/log/ai_security_audit.json"
  drop_capabilities: true

gui:
  enabled_on_demand: true
  window_manager: "sway"
  bar: "waybar"
  terminal: "foot"

cron:
  enabled: true
  task_file: "/etc/ai_os/tasks.json"
  tick_interval_seconds: 60
```

---

## 7. Recovery Consoles, Troubleshooting & FAQs

### Secondary Recovery Consoles
If a command hangs or you need standard root bash access:
- Press <kbd>Alt</kbd> + <kbd>F2</kbd> to switch to **TTY2**.
- Press <kbd>Alt</kbd> + <kbd>F3</kbd> to switch to **TTY3**.
- Press <kbd>Alt</kbd> + <kbd>F1</kbd> to return to **TTY1** (Master AI OS).

### Common Questions & Answers

**Q: Where are my projects and files saved across reboots?**  
A: All files stored in `/workspace/` and `/home/` reside on persistent OverlayFS storage. They persist across reboots when booting from USB or configured virtual disk images.

**Q: Can I use AI OS completely offline without an internet connection?**  
A: Yes! The offline model router automatically redirects all inference queries to the local Ollama engine, and all documentation is indexed locally in SQLite FTS5.

**Q: How do I pull new models for offline use?**  
A: Connect to a network and execute:
```bash
ollama pull llama3.2:3b
ollama pull qwen2.5-coder:7b
```
The models are stored on persistent storage in `/workspace/.ollama/models`.

**Q: How do I shut down or restart safely?**  
A: From the `ai-os` prompt, type `exit` or run standard OpenRC power commands:
```bash
poweroff    # Gracefully unmounts OverlayFS and halts system
reboot      # Restarts the machine
```
