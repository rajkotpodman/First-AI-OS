# First AI OS — Complete Installation & Hypervisor Deployment Guide (`INSTALLATION.md`)

This guide provides end-to-end instructions for deploying **First AI OS** across bare-metal physical machines, USB flash drives, and all major virtualization hypervisors (VMware Workstation, Oracle VirtualBox, QEMU/KVM, and Proxmox VE).

---

## Table of Contents
1. [System Requirements](#1-system-requirements)
2. [Obtaining the Bootable ISO Image](#2-obtaining-the-bootable-iso-image)
3. [Creating a Bootable USB Flash Drive (Bare Metal)](#3-creating-a-bootable-usb-flash-drive-bare-metal)
   - [Method A: Ventoy (Recommended for Multiboot)](#method-a-ventoy-multiboot-recommended)
   - [Method B: Rufus (Windows)](#method-b-rufus-windows)
   - [Method C: Linux `dd` CLI Utility](#method-c-linux-dd-command)
   - [Method D: BalenaEtcher (Cross-Platform)](#method-d-balenaetcher-cross-platform)
4. [Virtual Machine Setup: VMware Workstation](#4-virtual-machine-setup-vmware-workstation)
5. [Virtual Machine Setup: Oracle VirtualBox](#5-virtual-machine-setup-oracle-virtualbox)
6. [Virtual Machine Setup: QEMU / KVM](#6-virtual-machine-setup-qemu--kvm)
7. [Virtual Machine Setup: Proxmox VE](#7-virtual-machine-setup-proxmox-ve)
8. [Configuring Permanent Storage Persistence](#8-configuring-permanent-storage-persistence)
9. [Post-Installation Verification Checklist](#9-post-installation-verification-checklist)

---

## 1. System Requirements

First AI OS is engineered for extreme efficiency. Below are the minimum and recommended hardware specifications:

| Hardware Component | Minimum Requirement (CPU TTY Inference) | Recommended (GPU Offload & Sway GUI) |
| :--- | :--- | :--- |
| **Processor (CPU)** | 64-bit x86_64 Dual-Core (Intel / AMD) | 4+ Cores with AVX2 or AVX-512 support |
| **System Memory (RAM)** | 2 GB RAM (for 1B quantized LLM) | 8 GB to 16 GB RAM |
| **Graphics (GPU)** | Basic integrated VGA / VESA / DRM | NVIDIA GTX/RTX (≥ 4 GB VRAM) or AMD ROCm |
| **Storage** | 4 GB free disk space (USB or Virtual Disk) | 32 GB+ SSD / NVMe (for model weight cache) |
| **Network** | Offline (No network required) | Ethernet / Wi-Fi (for cloud fallback & updates) |
| **Firmware Mode** | Legacy BIOS or UEFI with CSM enabled | Hybrid BIOS / MBR |

---

## 2. Obtaining the Bootable ISO Image

### Option 1: Direct Download from GitHub Releases
Download the official pre-compiled hybrid ISO image (`ai-os-3.21-x86_64.iso`) and its SHA-256 checksum from the repository releases page:
- **GitHub Release Asset:** `https://github.com/rajkotpodman/First-AI-OS/releases`

Verify the download integrity:
```bash
# On Linux / WSL:
sha256sum -c SHA256SUMS.txt

# On Windows PowerShell:
Get-FileHash -Algorithm SHA256 .\ai-os-3.21-x86_64.iso
```

### Option 2: Building from Source via WSL or Linux Host
To generate the latest ISO directly from this repository:
```bash
git clone https://github.com/rajkotpodman/First-AI-OS.git
cd First-AI-OS
chmod +x build_base_os.sh
sudo ./build_base_os.sh
```
The resulting `ai-os-3.21-x86_64.iso` will be generated in the root directory.

---

## 3. Creating a Bootable USB Flash Drive (Bare Metal)

### Method A: Ventoy (Multiboot — Recommended)
Ventoy is the easiest way to boot First AI OS alongside other distributions without reformatting:
1. Install [Ventoy](https://www.ventoy.net/) onto your USB flash drive.
2. Drag and drop `ai-os-3.21-x86_64.iso` directly into the Ventoy USB partition in Windows Explorer or Linux file manager.
3. Boot your PC, select the USB drive from the BIOS boot menu (<kbd>F12</kbd>, <kbd>F11</kbd>, or <kbd>Esc</kbd>), and select `ai-os-3.21-x86_64.iso`.

### Method B: Rufus (Windows)
1. Download and run [Rufus](https://rufus.ie/).
2. Insert your USB drive (minimum 4 GB).
3. Under **Device**, select your USB flash drive.
4. Under **Boot selection**, click **SELECT** and choose `ai-os-3.21-x86_64.iso`.
5. Under **Partition scheme**, select **MBR**.
6. Under **Target system**, select **BIOS (or UEFI-CSM)**.
7. Click **START**. If prompted to write in *ISO Image mode* or *DD Image mode*, select **DD Image mode** for exact hybrid ISO sector replication.

### Method C: Linux `dd` Command
On any Linux or macOS terminal:
```bash
# 1. Identify your USB drive device node (e.g. /dev/sdb, /dev/sdc - DO NOT SELECT /dev/sda!)
lsblk

# 2. Unmount any active partitions on the drive
sudo umount /dev/sdX* 2>/dev/null || true

# 3. Flash the hybrid ISO directly to the raw block device
sudo dd if=ai-os-3.21-x86_64.iso of=/dev/sdX bs=4M status=progress conv=fsync
```

### Method D: BalenaEtcher (Cross-Platform)
1. Open [BalenaEtcher](https://etcher.balena.io/) on Windows, macOS, or Linux.
2. Click **Flash from file** and select `ai-os-3.21-x86_64.iso`.
3. Click **Select target** and choose your USB drive.
4. Click **Flash!**.

---

## 4. Virtual Machine Setup: VMware Workstation

To run First AI OS inside VMware Workstation Pro or VMware Workstation Player:

1. Open VMware Workstation and click **Create a New Virtual Machine** (<kbd>Ctrl</kbd> + <kbd>N</kbd>).
2. Choose **Typical (recommended)** -> Click **Next**.
3. Choose **Installer disc image file (iso)**:
   - Click **Browse...** and select `ai-os-3.21-x86_64.iso`.
   - If VMware indicates "Could not detect operating system", click **Next**.
4. Select Guest Operating System:
   - Guest OS: **Linux**
   - Version: **Other Linux 5.x kernel 64-bit** (or *Other Linux 64-bit*).
   - Click **Next**.
5. Name the Virtual Machine:
   - Name: `First-AI-OS` -> Click **Next**.
6. Disk Capacity:
   - Maximum disk size: **16 GB** (or 20 GB).
   - Select **Store virtual disk as a single file** -> Click **Next**.
7. **Hardware Configuration:**
   - Click **Customize Hardware...**:
     - **Memory:** Set to **2048 MB (2 GB)** for basic TTY CLI, or **4096 MB to 8192 MB** for local Ollama execution and GUI mode.
     - **Processors:** Set to **2 cores** or **4 cores**.
     - **Network Adapter:** Set to **NAT** or **Bridged**.
   - Click **Close**, then click **Finish**.
8. Click **Power on this virtual machine**.
9. The boot menu appears. Press <kbd>Enter</kbd> to boot Option 1 (`linux-virt`). Within 3 seconds, you are dropped directly into the AI OS prompt on `tty1`.

---

## 5. Virtual Machine Setup: Oracle VirtualBox

1. Launch VirtualBox and click **New** (<kbd>Ctrl</kbd> + <kbd>N</kbd>).
2. Set VM parameters:
   - **Name:** `First-AI-OS`
   - **Type:** `Linux`
   - **Version:** `Linux 2.6 / 3.x / 4.x / 5.x (64-bit)`
   - **ISO Image:** Select `ai-os-3.21-x86_64.iso`.
   - Check **Skip Unattended Installation** -> Click **Next**.
3. **Hardware Allocation:**
   - Base Memory: **4096 MB (4 GB)**.
   - Processors: **2 CPUs**.
   - Click **Next**.
4. **Virtual Hard Disk:**
   - Create a Virtual Hard Disk Now: **16 GB** -> Click **Next** -> Click **Finish**.
5. Open VM **Settings**:
   - **System -> Motherboard:** Ensure *Enable I/O APIC* is checked.
   - **Display -> Screen:** Set Video Memory to **64 MB**; Graphics Controller: **VMSVGA**.
   - **Network:** Adapter 1 attached to **NAT**.
6. Click **Start** to boot the virtual machine.

---

## 6. Virtual Machine Setup: QEMU / KVM

For Linux power users, developers, and headless cloud instances, QEMU provides near-native execution speed via KVM:

### Standard Graphical Virtual Machine:
```bash
qemu-system-x86_64 \
  -m 4G \
  -smp 4 \
  -enable-kvm \
  -cpu host \
  -cdrom ai-os-3.21-x86_64.iso \
  -boot d \
  -net nic,model=virtio \
  -net user \
  -vga virtio
```

### Headless Console-Only Mode (Terminal Direct Redirection):
To redirect AI OS's serial console directly into your active terminal shell without opening a GUI window:
```bash
qemu-system-x86_64 \
  -m 2G \
  -smp 2 \
  -enable-kvm \
  -cdrom ai-os-3.21-x86_64.iso \
  -boot d \
  -nographic \
  -serial mon:stdio \
  -append "console=ttyS0"
```

---

## 7. Virtual Machine Setup: Proxmox VE

To deploy First AI OS as an autonomous edge VM inside a Proxmox cluster:

1. Upload `ai-os-3.21-x86_64.iso` to your Proxmox ISO storage (`local -> ISO Images -> Upload`).
2. Click **Create VM** in the top right header:
   - **General:** Name = `first-ai-os`, VM ID = e.g., `105`.
   - **OS:** Use CD/DVD disc image file -> Select `ai-os-3.21-x86_64.iso`. Type: **Linux**, Version: **6.x - 2.6 Kernel**.
   - **System:** Graphic card = **Default**, Machine = **q35**, BIOS = **Default (SeaBIOS)**.
   - **Disks:** Bus/Device = **VirtIO Block**, Storage = `local-lvm`, Disk size = **20 GB**.
   - **CPU:** Sockets = `1`, Cores = `4`, Type = `host`.
   - **Memory:** `4096 MB` (4 GB).
   - **Network:** Bridge = `vmbr0`, Model = `VirtIO (paravirtualized)`.
3. Click **Finish**.
4. Go to **Console** and click **Start Now**. The system boots directly into the AI OS shell.

---

## 8. Configuring Permanent Storage Persistence

By default, First AI OS boots as a Live system in RAM with an ephemeral OverlayFS layer. To make your `/workspace/` projects, Git histories, and Ollama model weights persist permanently on your physical hard drive or dedicated virtual disk:

1. Create an `ext4` partition labeled `AIOS_DATA`:
   ```bash
   # From a recovery console (tty2) or setup script:
   mkfs.ext4 -L AIOS_DATA /dev/sdX1
   ```
2. Mount the persistence volume:
   ```bash
   mkdir -p /mnt/aios-storage
   mount -L AIOS_DATA /mnt/aios-storage
   mkdir -p /mnt/aios-storage/workspace /mnt/aios-storage/ollama
   
   # Bind mount into AI OS workspace:
   mount --bind /mnt/aios-storage/workspace /workspace
   mount --bind /mnt/aios-storage/ollama /workspace/.ollama
   ```
3. Add to `/etc/fstab` to persist mounts automatically across future boots.

---

## 9. Post-Installation Verification Checklist

Once First AI OS boots and presents the command prompt on `tty1`, run this quick verification sequence:

```bash
# 1. Verify subsystem health
ai-os
status

# 2. Verify hardware detection & tier allocation
ai-hw

# 3. Test the knowledge graph indexer
ai-index --status

# 4. Check network reachability & active model router
ai-router --status
```
If all four checks output green `[OK]` status indicators, your First AI OS installation is fully operational and ready for autonomous agent workloads!

