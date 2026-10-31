# Changelog (`CHANGELOG.md`)

All notable changes to the **First AI OS** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-alpha] - 2026-10-31

### Initial Public Release of First AI OS

#### Core Architecture & Distribution
- **Alpine Linux v3.21 Base:** Bootstrapped minimal distribution using official x86_64 minirootfs keeping uncompressed footprint under 500 MB.
- **Automated ISO Generation Script (`build_base_os.sh`):** Production-grade build system with automatic host package discovery (`apt-get`, `apk`, `pacman`), chroot isolation, and teardown cleanup traps.
- **Hybrid BIOS/MBR Bootloader:** Syslinux / ISOLINUX with El Torito and hybrid MBR partition record generated via `xorriso` and `isohdpfx.bin`.
- **Dual Kernel Support:** Packages both `linux-virt` (ultra-fast boot for VMware, VirtualBox, KVM) and `linux-lts` (broad hardware drivers for bare-metal machines).
- **Direct TTY1 Auto-Boot:** Configured `/etc/inittab` and OpenRC to automatically log in root on `tty1` and execute `/usr/bin/ai-os`.
- **OpenRC Daemon Service (`/etc/init.d/ai-os`):** Native OpenRC init service to manage background AI tasks and config synchronization.

#### The 19 Core Subsystems
- **`main_orchestrator.py`:** Master OS entry point coordinating hardware discovery, memory loading, security audits, and the interactive TTY interface.
- **`security_daemon.py`:** Enforces destructive command filters and immutable SHA-256 audit logs in `/var/log/ai_security_audit.json`.
- **`hardware_manager.py`:** Detects CPU vector extensions (AVX/AVX2/AVX512), GPU hardware (NVIDIA, AMD ROCm, Intel DRM), and sets inference tiers.
- **`personal_memory.py`:** Persistent user context, preference storage, and session recall across system reboots.
- **`model_router.py`:** Intelligent hybrid model gateway with DNS connectivity probing and seamless offline fallback to local Ollama.
- **`ai_cron_daemon.py`:** Autonomous background cron scheduler running periodic system care, project health checks, and data scraping.
- **`system_indexer.py`:** Multi-language AST parser (Python, TypeScript, Rust, Go, C/C++) storing symbol trees in SQLite for low-token LLM queries.
- **`ai_terminal_ui.py`:** Rich ANSI-colored split panes, progress bars, and Markdown formatting inside pure Linux TTY.
- **`ai_shell_agent.py`:** Natural language shell interpreter converting conversational prompts into guarded Linux commands.
- **`multimodal_gateway.py`:** Ingestion gateway for image analysis, screenshot inspection, voice capture, and speech synthesis.
- **`project_architect.py`:** Autonomous software generator translating natural language blueprints into complete repositories.
- **`self_healer.py`:** Automated testing, traceback isolation, unified diff generation, and backward patching verification loop.
- **`dependency_resolver.py`:** Dynamic package auto-healer supporting `apk`, `apt`, `pip`, `npm`, and `cargo`.
- **`sandbox_runner.py`:** Container execution sandbox dropping all capabilities (`--cap-drop=ALL`) and enforcing Seccomp syscall filtering.
- **`git_automator.py`:** Automated conventional commit generation, pre-patch safety checkpoints, and instant rollbacks.
- **`offline_docs_engine.py`:** Instant local documentation search with SQLite FTS5 across Linux man pages, Python, and Docker manuals.
- **`gui_expander.py` & `toggle_gui.sh`:** On-demand desktop switcher deploying Sway Wayland, Waybar status bar, and Foot terminal.
- **`system_updater.py`:** Atomic system updates, configuration snapshots, and rollback point manager.
- **`plugin_manager.py`:** Modular third-party plugin loader validated against JSON schema definitions.

#### Testing & CI/CD
- **Full Unit Test Suite:** 59 unit tests covering all 19 subsystems (`python -m unittest discover tests`).
- **GitHub Actions CI:** Automated multi-version Python matrix testing (3.10, 3.11, 3.12) with flake8 linting and configuration schema validation.
- **ISO Build Validation Workflow:** Automated syntax and tooling checks for `build_base_os.sh`.
- **Release Automation:** Tagged release builder with automatic SHA-256 checksum generation and GitHub asset attachment.
