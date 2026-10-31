# First AI OS — Autonomous Minimal Hardened Linux Operating System

<div align="center">

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Base OS](https://img.shields.io/badge/Base-Alpine_Linux_v3.21-0D597F.svg?logo=alpinelinux)](https://alpinelinux.org/)
[![Target Arch](https://img.shields.io/badge/Arch-x86__64-orange.svg)](#)
[![Footprint](https://img.shields.io/badge/Rootfs-%3C_500MB-green.svg)](#)
[![Python Version](https://img.shields.io/badge/Python-3.10_%7C_3.11_%7C_3.12-3776AB.svg?logo=python)](https://python.org/)
[![Test Suite](https://img.shields.io/badge/Tests-59_Passed-brightgreen.svg)](#)
[![Boot Interface](https://img.shields.io/badge/Boot-Direct_TTY1_%2B_On--Demand_GUI-purple.svg)](#)

<p align="center">
  <b>A standalone, hardened, bootable Linux distribution engineered specifically for edge AI agents, local LLM execution, autonomous software generation, and zero-to-GUI desktop environments.</b>
</p>

[Download ISO Release](https://github.com/rajkotpodman/First-AI-OS/releases) • [Operational Handbook (HOWTOUSE.md)](HOWTOUSE.md) • [System Architecture](ARCHITECTURE.md) • [Installation Guide](INSTALLATION.md)

</div>

---

## 🌟 What is First AI OS?

**First AI OS** is an operating system built from the kernel up for the artificial intelligence era. Built on top of **Alpine Linux v3.21 Minirootfs**, it dispenses with traditional multi-gigabyte desktop bloat, booting within seconds directly into a powerful **Natural Language TTY Agent** on `tty1`.

With an uncompressed root filesystem strictly under **500 MB** (~200–300 MB compressed hybrid ISO), First AI OS dedicates virtually all system RAM and GPU VRAM to what matters: **running high-performance local AI models, generating complete software projects, and executing self-healing development loops**.

```text
 ╔════════════════════════════════════════════════════════════════╗
 ║              FIRST AI OPERATING SYSTEM v1.0.0                  ║
 ║      Autonomous Hardened Alpine Linux Intelligence Core        ║
 ╚════════════════════════════════════════════════════════════════╝
 [*] System Audit: OK | Hardware: Tier 1 (NVIDIA 12GB) | Net: ONLINE
 [*] Memory: Loaded 4 profile parameters | Workspaces: /workspace
 [AI-OS:root ~]# project Build a real-time chat server with WebSockets
 [*] Scaffolding /workspace/projects/chat_server...
 [*] Writing backend code, tests, Dockerfile, Makefile...
 [*] Running verification test suite in isolated sandbox...
 [✓] Tests Passed: 12/12! Project ready at /workspace/projects/chat_server
```

---

## ⚡ Core Highlights & Architectural Features

- **Direct TTY1 Boot:** Boots straight into the Python Master Orchestrator without X11 or desktop overhead.
- **On-Demand Sway Wayland GUI:** Need graphical windows or web browsing? Type `gui` to instantly launch Sway, Waybar, and Foot terminal without rebooting. Type `gui --disable` to drop back to pure TTY.
- **19 Autonomous Subsystems:** Cohesive integration spanning AST indexing, autonomous project generation, self-debugging code repair, memory context, hardware discovery, and security audit logs.
- **Dynamic Hardware Tiers:** Probes CPU vector extensions (AVX/AVX2/AVX512) and GPU VRAM (NVIDIA CUDA, AMD ROCm, Intel DRM) to automatically tune Ollama thread counts and offloaded model layers.
- **Hybrid AI Router & Network Fallback:** Runs locally by default (privacy-first). Seamlessly fails over between local models and cloud providers if network connectivity is active and API keys are present.
- **Hardened Sandboxed Containers:** Untrusted code execution runs in disposable containers with `--cap-drop=ALL` and custom Seccomp syscall filters.
- **Dual Kernel Support:** Ships with both `linux-virt` (ultra-fast virtualization kernel for VMware, VirtualBox, KVM) and `linux-lts` (long-term support kernel for bare-metal hardware).
- **Hybrid BIOS/MBR Bootable ISO:** Bootable on legacy BIOS, hybrid MBR USB drives, and modern virtualization hypervisors.

---

## 📚 Complete Documentation Suite

| Document | Purpose & Contents |
| :--- | :--- |
| **[HOWTOUSE.md](HOWTOUSE.md)** | **Exhaustive Operational Handbook:** Detailed guide for every command, all 19 subsystems, walkthrough scenarios, Ollama setup, and recovery consoles. |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | **Deep-Dive Architecture Spec:** Bootloader flow, kernel stages, OverlayFS persistence topology, security model, and process trees. |
| **[INSTALLATION.md](INSTALLATION.md)** | **Hypervisor & Bare-Metal Guide:** Step-by-step setup for VMware Workstation, VirtualBox, QEMU/KVM, Proxmox, and USB flashing tools (Ventoy, Rufus, `dd`). |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | **Contributor Guidelines:** Development environment setup, running 59+ unit tests, code style standards, and PR workflows. |
| **[SECURITY.md](SECURITY.md)** | **Security Policy:** Threat model, Seccomp-BPF syscall filters, capability dropping, and vulnerability disclosure SLAs. |
| **[CHANGELOG.md](CHANGELOG.md)** | **Release History:** Detailed breakdown of features, subsystems, and fixes in version `1.0.0-alpha`. |
| **[ROADMAP.md](ROADMAP.md)** | **Future Roadmap:** Planned milestones for UEFI Secure Boot, ARM64/Pi 5 support, NPU acceleration, and agent swarm meshes. |

---

## 🧩 The 19 Core Subsystems

| # | Subsystem Module | CLI Binary | Primary Capability |
| :-: | :--- | :--- | :--- |
| **1** | [`main_orchestrator.py`](src/main_orchestrator.py) | `ai-os` | Master OS entrypoint, lifecycle manager, and TTY command loop. |
| **2** | [`security_daemon.py`](src/security_daemon.py) | *Daemon* | Command guardrails, regex destructive filter, and cryptographic audit logging. |
| **3** | [`hardware_manager.py`](src/hardware_manager.py) | `ai-hw` | Hardware discovery (CPU, GPU, RAM, VRAM) and Ollama acceleration tier generation. |
| **4** | [`personal_memory.py`](src/personal_memory.py) | *Engine* | Persistent user context, coding preferences, and cross-session memory recall. |
| **5** | [`model_router.py`](src/model_router.py) | `ai-router` | Hybrid offline/online model router, DNS connectivity probe, and cloud failover. |
| **6** | [`ai_cron_daemon.py`](src/ai_cron_daemon.py) | `ai-schedule`| Autonomous background scheduler for system care, health checks, and sync tasks. |
| **7** | [`system_indexer.py`](src/system_indexer.py) | `ai-index` | AST symbol extractor (Python, TS, Rust, Go, C) and low-token SQLite knowledge graph. |
| **8** | [`ai_terminal_ui.py`](src/ai_terminal_ui.py) | *UI Layer* | Rich ANSI split panes, progress bars, and Markdown formatting in pure Linux TTY. |
| **9** | [`ai_shell_agent.py`](src/ai_shell_agent.py) | `ai-os-shell`| Natural language command interpreter translating English queries into safe shell calls. |
| **10**| [`multimodal_gateway.py`](src/multimodal_gateway.py)| `ai-vision`/`ai-voice`| Multimodal gateway for diagram inspection, screen analysis, voice input, and TTS. |
| **11**| [`project_architect.py`](src/project_architect.py) | *Subsystem* | Autonomous software generator from natural language prompts to verified repositories. |
| **12**| [`self_healer.py`](src/self_healer.py) | *Subsystem* | Automated test runner, stack traceback parser, unified diff patcher, and repair loop. |
| **13**| [`dependency_resolver.py`](src/dependency_resolver.py)| *Subsystem* | Dynamic multi-manager package auto-healer (`apk`, `apt`, `pip`, `npm`, `cargo`). |
| **14**| [`sandbox_runner.py`](src/sandbox_runner.py) | *Sandbox* | Hardened container runner dropping all capabilities with custom Seccomp filters. |
| **15**| [`git_automator.py`](src/git_automator.py) | *Subsystem* | Conventional commit generator, pre-patch safety checkpoints, and instant rollbacks. |
| **16**| [`offline_docs_engine.py`](src/offline_docs_engine.py)| `ai-doc` | High-speed offline technical documentation engine with SQLite FTS5 search. |
| **17**| [`gui_expander.py`](src/gui_expander.py) | `gui` | On-demand dynamic desktop switcher deploying Sway Wayland, Waybar, and Foot. |
| **18**| [`system_updater.py`](src/system_updater.py) | *Subsystem* | Atomic system updates, configuration snapshots, and rollback point manager. |
| **19**| [`plugin_manager.py`](src/plugin_manager.py) | `ai-plugin` | Modular plugin discovery, validation against JSON schema, and execution sandbox. |

---

## 🚀 Quickstart: Booting & Running First AI OS

### Option A: Boot Pre-Compiled ISO in QEMU
```bash
qemu-system-x86_64 \
  -m 4G -smp 4 -enable-kvm \
  -cdrom ai-os-3.21-x86_64.iso \
  -boot d -net nic,model=virtio -net user
```

### Option B: Boot in VMware Workstation or VirtualBox
Follow the detailed step-by-step walkthrough in **[INSTALLATION.md](INSTALLATION.md)**:
1. Create a 64-bit Linux VM with 2–4 GB RAM.
2. Attach `ai-os-3.21-x86_64.iso` as the CD/DVD drive.
3. Power on to reach the TTY1 prompt within 3 seconds.

### Option C: Build the ISO from Source (WSL / Linux)
```bash
# 1. Clone repository
git clone https://github.com/rajkotpodman/First-AI-OS.git
cd First-AI-OS

# 2. Make build script executable & run with sudo
chmod +x build_base_os.sh
sudo ./build_base_os.sh

# Output: ai-os-3.21-x86_64.iso ready in root directory!
```

---

## 🧪 Running the Unit Test Suite

Run the full automated test suite across all 19 subsystems (59 unit tests):

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

```text
test_execute_guarded_command_success (tests.test_ai_shell_agent.TestAIShellAgent) ... ok
test_detect_hardware_profiles (tests.test_hardware_manager.TestHardwareManager) ... ok
test_apply_unified_diff_and_verify (tests.test_self_healer.TestSelfHealer) ... ok
test_sandbox_capability_drop (tests.test_sandbox_runner.TestSandboxRunner) ... ok
test_ast_symbol_extraction (tests.test_system_indexer.TestSystemIndexer) ... ok
test_model_router_fallback_to_local (tests.test_model_router.TestModelRouter) ... ok
...
----------------------------------------------------------------------
Ran 59 tests in 3.412s

OK
```

---

## 📄 License

First AI OS is licensed under the **[Apache License 2.0](LICENSE)**.

Copyright © 2026 First AI OS Project Contributors. All rights reserved.
