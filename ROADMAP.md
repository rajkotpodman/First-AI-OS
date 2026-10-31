# Technical Roadmap (`ROADMAP.md`)

This roadmap outlines the planned technical milestones for **First AI OS** across upcoming release cycles.

---

## 🎯 Milestone 1: Core Hardening & Distribution (v1.0.x — Current)
- [x] Bootable Alpine Linux v3.21 minirootfs hybrid ISO (`ai-os-3.21-x86_64.iso`).
- [x] Integrated 19 autonomous subsystems with master orchestrator.
- [x] Dual-kernel setup: `linux-virt` and `linux-lts`.
- [x] Direct auto-login on `tty1` into the Python TTY AI agent.
- [x] On-demand Sway Wayland GUI desktop switcher.
- [x] Docker/Podman container sandboxing with custom Seccomp filters.
- [x] Automated self-debugging and unified diff patching loop.
- [x] Comprehensive 59-test automated unit test suite.
- [x] Full operational handbook (`HOWTOUSE.md`) and deployment guides.

---

## 🚀 Milestone 2: Hardware Acceleration & Modern Firmware (v1.1.0 — Q1 2027)
- [ ] **Native UEFI & Secure Boot Support:**
  - Add GRUB2 EFI x86_64 bootloader alongside ISOLINUX for native UEFI machines without CSM.
  - Sign bootloader binaries with machine owner keys (MOK).
- [ ] **Direct NPU (Neural Processing Unit) Acceleration:**
  - Support Intel NPU (OpenVINO / NPU driver) and AMD Ryzen AI XDNA acceleration.
  - Qualcomm Snapdragon X Elite Snapdragon NPU drivers.
- [ ] **Quantization Pipeline Integration:**
  - Built-in one-command GGUF quantization tool (`ai-quantize`) using `llama.cpp` for edge models.

---

## 🌐 Milestone 3: ARM64 & Single-Board Computers (v1.2.0 — Q2 2027)
- [ ] **AArch64 / ARM64 Live Images:**
  - Pre-built bootable SD card and NVMe images for Raspberry Pi 5 (8 GB).
  - Support for Rockchip RK3588 (Orange Pi 5 Plus) utilizing its 6 TOPS embedded NPU.
  - Apple Silicon virtualization image for UTM / Parallels on macOS.
- [ ] **Voice Wake-Word Engine:**
  - Always-listening lightweight offline wake-word detector (e.g. "Hey OS") running on low-power CPU core.

---

## ⚡ Milestone 4: Distributed Agent Swarm & Mesh (v2.0.0 — Q3 2027)
- [ ] **AI OS Swarm Clustering:**
  - Peer-to-peer discovery using mDNS/Avahi across local LAN.
  - Offload heavy multi-agent compilation and project generation tasks to neighboring AI OS nodes.
- [ ] **Visual Live Canvas inside Sway GUI:**
  - Native Wayland floating widget for real-time model token streaming and interactive AST graph visualization.
- [ ] **Zero-Knowledge Encrypted Personal Memory:**
  - Hardware TPM 2.0 / USB security token cryptographic sealing of `/workspace/.ai_os/memory.json`.

