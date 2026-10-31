# First AI OS v1.0.0 — Official Hybrid Bootable ISO Release

Welcome to the initial official release of **First AI OS** (`ai-os-3.21-x86_64.iso`), an autonomous, hardened, minimal Linux operating system engineered specifically for edge AI agents, local Large Language Model (LLM) execution, zero-to-GUI desktop switching, autonomous project architecture, and self-healing software development.

---

### Release Highlights
- **Base Distribution:** Alpine Linux v3.21 Minirootfs (x86_64).
- **Kernel Flavors Included:** `linux-virt` (ultra-fast virtualization) & `linux-lts` (bare-metal hardware).
- **Footprint:** Strictly under 500 MB uncompressed rootfs (~291 MB live bootable hybrid ISO).
- **Default Shell:** Boots directly into `/usr/bin/ai-os` (Master OS Orchestrator) on `tty1` without X11 overhead.
- **On-Demand GUI:** Sway Wayland tiling window manager, Waybar, and Foot terminal via `gui`.
- **Security:** Seccomp syscall filtering, capabilities dropping, and cryptographic SHA-256 audit trails.
- **Subsystems:** Complete suite of 19 autonomous AI subsystems.

---

### Download & Checksum Verification
- **File:** `ai-os-3.21-x86_64.iso` (Attached below)
- **Target Architecture:** `x86_64` (BIOS & Hybrid MBR bootable)

Verify the SHA-256 checksum after downloading:
```bash
# On Linux / WSL:
sha256sum ai-os-3.21-x86_64.iso

# On Windows PowerShell:
Get-FileHash -Algorithm SHA256 .\ai-os-3.21-x86_64.iso
```

---

### Quick Installation & Boot
- **VMware / VirtualBox:** Select Guest OS: *Linux -> Other Linux 5.x kernel 64-bit*, allocate 2–4 GB RAM, attach ISO, and power on.
- **USB Flash Drive:** Flash with Ventoy, Rufus (DD mode), BalenaEtcher, or Linux `dd`:
  ```bash
  sudo dd if=ai-os-3.21-x86_64.iso of=/dev/sdX bs=4M status=progress conv=fsync
  ```
- **QEMU:**
  ```bash
  qemu-system-x86_64 -m 4G -smp 4 -enable-kvm -cdrom ai-os-3.21-x86_64.iso -boot d -net nic -net user
  ```

For detailed operational guidance, see [HOWTOUSE.md](https://github.com/rajkotpodman/First-AI-OS/blob/main/HOWTOUSE.md) and [INSTALLATION.md](https://github.com/rajkotpodman/First-AI-OS/blob/main/INSTALLATION.md).

