#!/usr/bin/env bash
# ==============================================================================
# Script: build_base_os.sh
# Description: Automated Alpine Linux v3.21 Hybrid ISO Generation for AI OS
# Role: Senior Linux Distribution Engineer & ISO Build System Specialist
# Target Image: ai-os-3.21-x86_64.iso (Hybrid BIOS/MBR Bootable ISO)
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Global Configurations & Path Definitions
# ------------------------------------------------------------------------------
ALPINE_VERSION="3.21"
ALPINE_PATCH="0"
ARCH="x86_64"
OUTPUT_ISO="ai-os-${ALPINE_VERSION}-${ARCH}.iso"

# Source directory containing the AI OS project codebase
SCRIPT_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FINAL_ISO_PATH="${SCRIPT_SRC_DIR}/${OUTPUT_ISO}"

# Minirootfs source URL
MINIROOTFS_TARBALL="alpine-minirootfs-${ALPINE_VERSION}.${ALPINE_PATCH}-${ARCH}.tar.gz"
MINIROOTFS_URL="https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/releases/${ARCH}/${MINIROOTFS_TARBALL}"

# Isolated temporary workspace under /tmp/ai_os_build/
BUILD_DIR="/tmp/ai_os_build"
ROOTFS_DIR="${BUILD_DIR}/rootfs"
ISO_ROOT_DIR="${BUILD_DIR}/iso_root"
SQUASHFS_DIR="${BUILD_DIR}/squashfs"

# Terminal ANSI styling
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo -e "${CYAN}================================================================${NC}"
echo -e "${BOLD}       AI OPERATING SYSTEM - AUTOMATED ISO BUILD SYSTEM         ${NC}"
echo -e "${CYAN}================================================================${NC}"
log_info "Target Output     : ${FINAL_ISO_PATH}"
log_info "Base Distribution : Alpine Linux v${ALPINE_VERSION}.${ALPINE_PATCH} (${ARCH})"
log_info "Workspace Root    : ${SCRIPT_SRC_DIR}"
echo ""

# ------------------------------------------------------------------------------
# 2. Privilege Check & Teardown Cleanup Traps
# ------------------------------------------------------------------------------
if [[ "${EUID}" -ne 0 ]]; then
    log_error "This script requires administrative privileges. Please re-run with: sudo $0"
fi

cleanup() {
    local exit_code=$?
    log_info "Executing teardown handler..."

    # Ensure virtual filesystems are cleanly detached
    if [ -d "${ROOTFS_DIR}" ]; then
        umount -l "${ROOTFS_DIR}/dev/pts" 2>/dev/null || true
        umount -l "${ROOTFS_DIR}/dev"     2>/dev/null || true
        umount -l "${ROOTFS_DIR}/proc"    2>/dev/null || true
        umount -l "${ROOTFS_DIR}/sys"     2>/dev/null || true
    fi

    # Remove temporary directories only if build succeeded, preserving for inspection on failure
    if [ "${exit_code}" -eq 0 ]; then
        log_info "Cleaning up temporary build workspace: ${BUILD_DIR}..."
        rm -rf "${BUILD_DIR}"
        log_success "Workspace cleanup completed."
    else
        log_warn "Build terminated with status code ${exit_code}."
        log_warn "Preserving ${BUILD_DIR} for debugging and diagnostic inspection."
    fi
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------------------------
# 3. Host Dependency Check & Automatic Installation
# ------------------------------------------------------------------------------
log_info "Auditing host build dependencies..."

HOST_TOOLS=(xorriso syslinux isolinux mksquashfs mcopy curl tar mkfs.vfat)
MISSING_TOOLS=()

for tool in "${HOST_TOOLS[@]}"; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        MISSING_TOOLS+=("${tool}")
    fi
done

if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    log_warn "Missing required host utilities: ${MISSING_TOOLS[*]}"
    if command -v apt-get >/dev/null 2>&1; then
        log_info "Debian/Ubuntu/WSL host detected. Installing build packages via apt-get..."
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y
        apt-get install -y --no-install-recommends \
            xorriso \
            syslinux \
            isolinux \
            syslinux-utils \
            syslinux-common \
            squashfs-tools \
            mtools \
            curl \
            tar \
            dosfstools
    elif command -v apk >/dev/null 2>&1; then
        log_info "Alpine Linux host detected. Installing build packages via apk..."
        apk add --no-cache \
            xorriso \
            syslinux \
            squashfs-tools \
            mtools \
            curl \
            tar \
            dosfstools
    elif command -v pacman >/dev/null 2>&1; then
        log_info "Arch Linux host detected. Installing build packages via pacman..."
        pacman -Sy --noconfirm xorriso syslinux squashfs-tools mtools curl tar dosfstools
    else
        log_error "Unable to detect package manager. Please install: xorriso, syslinux, isolinux, squashfs-tools, mtools, curl, tar, dosfstools."
    fi
    log_success "Host dependencies verified and ready."
else
    log_success "All required host build dependencies are available."
fi

# ------------------------------------------------------------------------------
# 4. Workspace Directory Preparation & Minirootfs Download
# ------------------------------------------------------------------------------
log_info "Preparing temporary build directories under ${BUILD_DIR}..."
rm -rf "${BUILD_DIR}"
mkdir -p "${ROOTFS_DIR}" "${ISO_ROOT_DIR}" "${SQUASHFS_DIR}"
mkdir -p "${ISO_ROOT_DIR}/boot/isolinux"
mkdir -p "${ISO_ROOT_DIR}/live"

MINIROOTFS_PATH="${BUILD_DIR}/${MINIROOTFS_TARBALL}"
log_info "Downloading Alpine Linux v${ALPINE_VERSION}.${ALPINE_PATCH} minirootfs..."
curl -fsSL "${MINIROOTFS_URL}" -o "${MINIROOTFS_PATH}"
log_success "Minirootfs tarball downloaded (${MINIROOTFS_PATH})."

log_info "Extracting minirootfs into target filesystem directory..."
tar -xzf "${MINIROOTFS_PATH}" -C "${ROOTFS_DIR}"
log_success "Rootfs extracted."

# ------------------------------------------------------------------------------
# 5. Virtual Filesystems, Repositories & Chroot Package Setup
# ------------------------------------------------------------------------------
log_info "Mounting host virtual filesystems for chroot operations..."
cp /etc/resolv.conf "${ROOTFS_DIR}/etc/resolv.conf"
mount --bind /dev       "${ROOTFS_DIR}/dev"
mount -t devpts devpts "${ROOTFS_DIR}/dev/pts"
mount -t proc   proc   "${ROOTFS_DIR}/proc"
mount -t sysfs  sysfs  "${ROOTFS_DIR}/sys"

log_info "Configuring Alpine package repositories (main & community)..."
cat << REPOS_EOF > "${ROOTFS_DIR}/etc/apk/repositories"
https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/main
https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION}/community
REPOS_EOF

log_info "Configuring mkinitfs with live ISO & OverlayFS modules..."
mkdir -p "${ROOTFS_DIR}/etc/mkinitfs"
cat << 'MKINITFS_EOF' > "${ROOTFS_DIR}/etc/mkinitfs/mkinitfs.conf"
features="ata base ide scsi usb virtio ext4 squashfs overlay loop"
MKINITFS_EOF

log_info "Executing package installation & kernel bootstrapping inside chroot..."
chroot "${ROOTFS_DIR}" /bin/sh << 'CHROOT_INSTALL'
set -euo pipefail

# Refresh APK index and install system packages
apk update
apk add --no-cache \
    alpine-base \
    openrc \
    busybox \
    busybox-extras \
    util-linux \
    bash \
    python3 \
    py3-pip \
    docker \
    git \
    curl \
    sudo \
    ca-certificates \
    e2fsprogs \
    syslinux \
    linux-virt \
    linux-lts \
    linux-firmware-none \
    mkinitfs

# Regenerate initramfs for all installed kernel versions
for kdir in /lib/modules/*; do
    if [ -d "${kdir}" ]; then
        kver=$(basename "${kdir}")
        flavor=$(echo "${kver}" | sed -E 's/^[0-9.]+-([a-zA-Z0-9]+).*/\1/')
        echo "[*] Generating initramfs for kernel: ${kver} (flavor: ${flavor})..."
        mkinitfs -c /etc/mkinitfs/mkinitfs.conf -b / -o "/boot/initramfs-${flavor}" "${kver}" || true
    fi
done

# Passwordless root for frictionless TTY developer boot
passwd -d root
echo "%wheel ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Create workspace and data mount points
mkdir -p /workspace /mnt/aios-storage /var/lib/docker /home /opt/ai-os /var/log /run

# Set system hostname
echo "ai-os" > /etc/hostname

# Register core system services into OpenRC runlevels
rc-update add devfs sysinit
rc-update add dmesg sysinit
rc-update add mdev sysinit
rc-update add bootmisc boot
rc-update add syslog boot
rc-update add networking default
rc-update add localmount default
rc-update add docker default 2>/dev/null || true

# Prune documentation and caches to keep image compact
rm -rf /var/cache/apk/* /tmp/* /var/tmp/* /usr/share/man /usr/share/doc
CHROOT_INSTALL
log_success "Chroot package installation and kernel configuration complete."

# ------------------------------------------------------------------------------
# 6. AI OS Code Injection & Application Layer Setup
# ------------------------------------------------------------------------------
log_info "Injecting AI OS codebase into /opt/ai-os/..."

mkdir -p "${ROOTFS_DIR}/opt/ai-os"

# Copy source directories
cp -r "${SCRIPT_SRC_DIR}/src" "${ROOTFS_DIR}/opt/ai-os/src"

if [ -d "${SCRIPT_SRC_DIR}/configs" ]; then
    cp -r "${SCRIPT_SRC_DIR}/configs" "${ROOTFS_DIR}/opt/ai-os/configs"
    ln -sf configs "${ROOTFS_DIR}/opt/ai-os/config"
elif [ -d "${SCRIPT_SRC_DIR}/config" ]; then
    cp -r "${SCRIPT_SRC_DIR}/config" "${ROOTFS_DIR}/opt/ai-os/config"
    ln -sf config "${ROOTFS_DIR}/opt/ai-os/configs"
fi

if [ -d "${SCRIPT_SRC_DIR}/plugins" ]; then
    cp -r "${SCRIPT_SRC_DIR}/plugins" "${ROOTFS_DIR}/opt/ai-os/plugins"
fi

if [ -d "${SCRIPT_SRC_DIR}/tests" ]; then
    cp -r "${SCRIPT_SRC_DIR}/tests" "${ROOTFS_DIR}/opt/ai-os/tests"
fi

if [ -d "${SCRIPT_SRC_DIR}/examples" ]; then
    cp -r "${SCRIPT_SRC_DIR}/examples" "${ROOTFS_DIR}/opt/ai-os/examples"
fi

# Copy supplementary root utilities and docs if present
for root_file in toggle_gui.sh personal_memory.py multimodal_gateway.py security_daemon.py system_updater.py README.md; do
    if [ -f "${SCRIPT_SRC_DIR}/${root_file}" ]; then
        cp "${SCRIPT_SRC_DIR}/${root_file}" "${ROOTFS_DIR}/opt/ai-os/${root_file}"
    fi
done

# Ensure executable permissions across all scripts
chmod -R 755 "${ROOTFS_DIR}/opt/ai-os"
chmod +x "${ROOTFS_DIR}/opt/ai-os/src/main_orchestrator.py"

# Create /usr/bin/ai-os wrapper symlink pointing to main_orchestrator.py
mkdir -p "${ROOTFS_DIR}/usr/bin" "${ROOTFS_DIR}/usr/local/bin"
ln -sf /opt/ai-os/src/main_orchestrator.py "${ROOTFS_DIR}/usr/bin/ai-os"
ln -sf /opt/ai-os/src/main_orchestrator.py "${ROOTFS_DIR}/usr/local/bin/ai-os"

# Symlink individual AI OS CLI tools into global PATH
ln -sf /opt/ai-os/src/system_indexer.py   "${ROOTFS_DIR}/usr/local/bin/ai-index"
ln -sf /opt/ai-os/src/hardware_manager.py "${ROOTFS_DIR}/usr/local/bin/ai-hw"
ln -sf /opt/ai-os/src/model_router.py     "${ROOTFS_DIR}/usr/local/bin/ai-router"
ln -sf /opt/ai-os/src/ai_shell_agent.py   "${ROOTFS_DIR}/usr/local/bin/ai-os-shell"
ln -sf /opt/ai-os/src/ai_doc.py           "${ROOTFS_DIR}/usr/local/bin/ai-doc" 2>/dev/null || true
ln -sf /opt/ai-os/src/ai_plugin.py        "${ROOTFS_DIR}/usr/local/bin/ai-plugin" 2>/dev/null || true
ln -sf /opt/ai-os/src/ai_schedule.py      "${ROOTFS_DIR}/usr/local/bin/ai-schedule" 2>/dev/null || true
if [ -f "${ROOTFS_DIR}/opt/ai-os/toggle_gui.sh" ]; then
    ln -sf /opt/ai-os/toggle_gui.sh "${ROOTFS_DIR}/usr/local/bin/gui"
fi

# Set global python environment variables in profile.d
cat << 'PROFILE_EOF' > "${ROOTFS_DIR}/etc/profile.d/ai-os.sh"
#!/bin/sh
export PATH="/opt/ai-os/src:/usr/local/bin:$PATH"
export PYTHONPATH="/opt/ai-os/src:${PYTHONPATH:-}"
export AI_OS_ROOT="/opt/ai-os"
PROFILE_EOF
chmod +x "${ROOTFS_DIR}/etc/profile.d/ai-os.sh"

log_success "AI OS codebase injected into /opt/ai-os/ and /usr/bin/ai-os linked."

# ------------------------------------------------------------------------------
# 7. Auto-Boot TTY & OpenRC Service Configuration
# ------------------------------------------------------------------------------
log_info "Configuring /etc/inittab for automatic TTY1 login to ai-os..."
if [ -f "${SCRIPT_SRC_DIR}/configs/inittab" ]; then
    cp "${SCRIPT_SRC_DIR}/configs/inittab" "${ROOTFS_DIR}/etc/inittab"
else
    cat << 'INITTAB_EOF' > "${ROOTFS_DIR}/etc/inittab"
# /etc/inittab: System initialization configuration for AI OS
::sysinit:/sbin/openrc sysinit
::sysinit:/sbin/openrc boot
::wait:/sbin/openrc default

# Auto-login on TTY1 and execute ai-os directly
tty1::respawn:/sbin/getty -n -l /usr/bin/ai-os 38400 tty1 linux

# Fallback debug / administrative consoles on TTY2 & TTY3
tty2::respawn:/sbin/getty 38400 tty2
tty3::respawn:/sbin/getty 38400 tty3
tty4::respawn:/sbin/getty 38400 tty4

# Serial console fallback (ideal for QEMU -nographic)
ttyS0::respawn:/sbin/getty -n -l /usr/bin/ai-os 115200 ttyS0 vt100

::ctrlaltdel:/sbin/reboot
::shutdown:/sbin/openrc shutdown
INITTAB_EOF
fi

log_info "Configuring OpenRC /etc/init.d/ai-os service..."
if [ -f "${SCRIPT_SRC_DIR}/configs/ai-os.initd" ]; then
    cp "${SCRIPT_SRC_DIR}/configs/ai-os.initd" "${ROOTFS_DIR}/etc/init.d/ai-os"
else
    cat << 'AI_OS_INIT_EOF' > "${ROOTFS_DIR}/etc/init.d/ai-os"
#!/sbin/openrc-run
name="AI OS Background Services"
description="Starts AI Operating System background daemons, cron scheduler, and security runtime"

command="/usr/bin/python3"
command_args="/opt/ai-os/src/ai_cron_daemon.py"
command_background="yes"
pidfile="/run/ai-os.pid"
output_log="/var/log/ai-os.log"
error_log="/var/log/ai-os.err"

depend() {
    need localmount
    after bootmisc networking docker
}

start_pre() {
    mkdir -p /var/log /run /workspace /etc/ai_os /opt/ai-os/logs
    checkpath -d -m 0755 -o root:root /run
    if [ -d /opt/ai-os/configs ] && [ ! -f /etc/ai_os/config.yaml ]; then
        cp -rn /opt/ai-os/configs/* /etc/ai_os/ 2>/dev/null || true
    fi
}

start_post() {
    einfo "AI OS background daemons initialized successfully."
}

stop() {
    ebegin "Stopping AI OS Background Services"
    start-stop-daemon --stop --pidfile "${pidfile}" --quiet
    eend $?
}
AI_OS_INIT_EOF
fi
chmod +x "${ROOTFS_DIR}/etc/init.d/ai-os"

# Install other optional OpenRC daemon services if available
if [ -f "${SCRIPT_SRC_DIR}/configs/ai-agent.initd" ]; then
    cp "${SCRIPT_SRC_DIR}/configs/ai-agent.initd" "${ROOTFS_DIR}/etc/init.d/ai-agent"
    chmod +x "${ROOTFS_DIR}/etc/init.d/ai-agent"
fi
if [ -f "${SCRIPT_SRC_DIR}/configs/ai-overlayfs.initd" ]; then
    cp "${SCRIPT_SRC_DIR}/configs/ai-overlayfs.initd" "${ROOTFS_DIR}/etc/init.d/ai-overlayfs"
    chmod +x "${ROOTFS_DIR}/etc/init.d/ai-overlayfs"
    chroot "${ROOTFS_DIR}" rc-update add ai-overlayfs boot 2>/dev/null || true
fi

# Enable ai-os service in default runlevel
chroot "${ROOTFS_DIR}" rc-update add ai-os default
log_success "OpenRC auto-boot service and inittab configured."

# ------------------------------------------------------------------------------
# 8. Unmount Virtual Filesystems & Kernel Extraction
# ------------------------------------------------------------------------------
log_info "Unmounting chroot virtual filesystems prior to squashfs compression..."
umount -l "${ROOTFS_DIR}/dev/pts" 2>/dev/null || true
umount -l "${ROOTFS_DIR}/dev"     2>/dev/null || true
umount -l "${ROOTFS_DIR}/proc"    2>/dev/null || true
umount -l "${ROOTFS_DIR}/sys"     2>/dev/null || true

# Extract kernel and initramfs to ISO boot directory
log_info "Copying kernel and initramfs images to ISO boot structure..."
mkdir -p "${ISO_ROOT_DIR}/boot"

cp -f "${ROOTFS_DIR}/boot/vmlinuz-"*   "${ISO_ROOT_DIR}/boot/" 2>/dev/null || true
cp -f "${ROOTFS_DIR}/boot/initramfs-"* "${ISO_ROOT_DIR}/boot/" 2>/dev/null || true

# Harmonize kernel naming for virt and lts boot targets
if [ -f "${ISO_ROOT_DIR}/boot/vmlinuz-lts" ] && [ ! -f "${ISO_ROOT_DIR}/boot/vmlinuz-virt" ]; then
    cp "${ISO_ROOT_DIR}/boot/vmlinuz-lts" "${ISO_ROOT_DIR}/boot/vmlinuz-virt"
    cp "${ISO_ROOT_DIR}/boot/initramfs-lts" "${ISO_ROOT_DIR}/boot/initramfs-virt"
elif [ -f "${ISO_ROOT_DIR}/boot/vmlinuz-virt" ] && [ ! -f "${ISO_ROOT_DIR}/boot/vmlinuz-lts" ]; then
    cp "${ISO_ROOT_DIR}/boot/vmlinuz-virt" "${ISO_ROOT_DIR}/boot/vmlinuz-lts"
    cp "${ISO_ROOT_DIR}/boot/initramfs-virt" "${ISO_ROOT_DIR}/boot/initramfs-lts"
fi
log_success "Boot kernel and initramfs prepared."

# ------------------------------------------------------------------------------
# 9. SquashFS Compression (rootfs -> iso_root/live/rootfs.squashfs)
# ------------------------------------------------------------------------------
log_info "Compressing rootfs into /tmp/ai_os_build/iso_root/live/rootfs.squashfs..."
mkdir -p "${ISO_ROOT_DIR}/live"
rm -f "${ISO_ROOT_DIR}/live/rootfs.squashfs"

mksquashfs "${ROOTFS_DIR}" "${ISO_ROOT_DIR}/live/rootfs.squashfs" \
    -comp xz \
    -noappend \
    -wildcards \
    -e "boot" "tmp/*" "var/tmp/*" "proc/*" "sys/*" "dev/*"

# Compatibility symlink for standard LiveCD loaders
ln -sf rootfs.squashfs "${ISO_ROOT_DIR}/live/filesystem.squashfs"

SQUASHFS_SIZE_MB=$(du -sm "${ISO_ROOT_DIR}/live/rootfs.squashfs" | cut -f1)
log_success "SquashFS image generated (${SQUASHFS_SIZE_MB} MB)."

# ------------------------------------------------------------------------------
# 10. Bootloader Setup (ISOLINUX / Syslinux)
# ------------------------------------------------------------------------------
log_info "Setting up ISOLINUX/Syslinux bootloader in iso_root/boot/isolinux/..."
mkdir -p "${ISO_ROOT_DIR}/boot/isolinux"

# Helper function to discover syslinux/isolinux binary files on host or rootfs
find_boot_file() {
    local fname="$1"
    local found=""

    # 1. Search host known directories
    found=$(find /usr/lib/ISOLINUX /usr/lib/syslinux /usr/share/syslinux -name "${fname}" 2>/dev/null | head -n 1 || true)

    # 2. Search rootfs if not found on host
    if [ -z "${found}" ]; then
        found=$(find "${ROOTFS_DIR}/usr/share/syslinux" -name "${fname}" 2>/dev/null | head -n 1 || true)
    fi

    # 3. Fallback search anywhere in /usr
    if [ -z "${found}" ]; then
        found=$(find /usr -name "${fname}" 2>/dev/null | head -n 1 || true)
    fi

    echo "${found}"
}

# Locate and install isolinux.bin
ISOLINUX_BIN=$(find_boot_file "isolinux.bin")
if [ -n "${ISOLINUX_BIN}" ] && [ -f "${ISOLINUX_BIN}" ]; then
    cp -f "${ISOLINUX_BIN}" "${ISO_ROOT_DIR}/boot/isolinux/isolinux.bin"
    log_info "Found isolinux.bin: ${ISOLINUX_BIN}"
else
    log_error "Critical: isolinux.bin could not be found. Please install isolinux / syslinux."
fi

# Locate and copy required COM32 modules (ldlinux.c32, menu.c32, libutil.c32, libcom32.c32)
for c32 in ldlinux.c32 menu.c32 libutil.c32 libcom32.c32; do
    C32_PATH=$(find_boot_file "${c32}")
    if [ -n "${C32_PATH}" ] && [ -f "${C32_PATH}" ]; then
        cp -f "${C32_PATH}" "${ISO_ROOT_DIR}/boot/isolinux/${c32}"
        log_info "Found ${c32}: ${C32_PATH}"
    else
        log_warn "Optional COM32 module ${c32} not found; boot menu may use text fallback."
    fi
done

# Deploy isolinux.cfg with 3-second timeout and clean boot menu
if [ -f "${SCRIPT_SRC_DIR}/configs/isolinux.cfg" ]; then
    cp "${SCRIPT_SRC_DIR}/configs/isolinux.cfg" "${ISO_ROOT_DIR}/boot/isolinux/isolinux.cfg"
else
    cat << 'ISOLINUX_EOF' > "${ISO_ROOT_DIR}/boot/isolinux/isolinux.cfg"
DEFAULT aios
TIMEOUT 30
PROMPT 0

UI menu.c32
MENU TITLE AI Operating System (Alpine 3.21 x86_64)
MENU COLOR border       30;44   #40ffffff #a0000000 std
MENU COLOR title        1;36;44 #ffffffff #a0000000 std
MENU COLOR sel          7;37;40 #e0000000 #20ffffff all
MENU COLOR unsel        37;44   #50ffffff #a0000000 std

LABEL aios
  MENU LABEL Boot AI OS (Default Virtual Kernel)
  MENU DEFAULT
  LINUX /boot/vmlinuz-virt
  INITRD /boot/initramfs-virt
  APPEND console=tty1 quiet initrd=/boot/initramfs-virt modules=loop,squashfs,overlay alpine_dev=cdrom:iso9660

LABEL aios_lts
  MENU LABEL Boot AI OS (LTS Hardware Kernel)
  LINUX /boot/vmlinuz-lts
  INITRD /boot/initramfs-lts
  APPEND console=tty1 quiet initrd=/boot/initramfs-lts modules=loop,squashfs,overlay alpine_dev=cdrom:iso9660
ISOLINUX_EOF
fi

# Mirror bootloader configuration into /boot/syslinux for dual-spec loaders
mkdir -p "${ISO_ROOT_DIR}/boot/syslinux"
cp -rn "${ISO_ROOT_DIR}/boot/isolinux/"* "${ISO_ROOT_DIR}/boot/syslinux/" 2>/dev/null || true

# Stamp Alpine release identity on ISO root
echo "${ALPINE_VERSION}.${ALPINE_PATCH}" > "${ISO_ROOT_DIR}/.alpine-release"
log_success "Bootloader configuration and syslinux modules staged."

# ------------------------------------------------------------------------------
# 11. Hybrid ISO Master Generation (xorriso & isohybrid)
# ------------------------------------------------------------------------------
log_info "Synthesizing hybrid bootable ISO image via xorriso..."

ISOHDPFX=$(find_boot_file "isohdpfx.bin")
XORRISO_FLAGS=(
    -as mkisofs
    -r -V "AI_OS"
    -J -joliet-long
    -l
    -b boot/isolinux/isolinux.bin
    -c boot/isolinux/boot.cat
    -no-emul-boot
    -boot-load-size 4
    -boot-info-table
)

if [ -n "${ISOHDPFX}" ] && [ -f "${ISOHDPFX}" ]; then
    log_info "Enabling hybrid MBR boot record with ${ISOHDPFX}..."
    XORRISO_FLAGS+=(-isohybrid-mbr "${ISOHDPFX}")
else
    log_warn "isohdpfx.bin not located; building standard El Torito ISO..."
fi

# Remove previous ISO if present
rm -f "${FINAL_ISO_PATH}"

# Execute xorriso build
xorriso "${XORRISO_FLAGS[@]}" -o "${FINAL_ISO_PATH}" "${ISO_ROOT_DIR}"

# Post-processing: Apply isohybrid if binary is present on host
if command -v isohybrid >/dev/null 2>&1; then
    isohybrid "${FINAL_ISO_PATH}" 2>/dev/null || true
fi

# ------------------------------------------------------------------------------
# 12. Verification & Summary Report
# ------------------------------------------------------------------------------
if [ ! -f "${FINAL_ISO_PATH}" ]; then
    log_error "Verification failure: ISO file was not generated at ${FINAL_ISO_PATH}"
fi

ISO_SIZE_BYTES=$(stat -c%s "${FINAL_ISO_PATH}" 2>/dev/null || stat -f%z "${FINAL_ISO_PATH}" 2>/dev/null || wc -c < "${FINAL_ISO_PATH}")
ISO_SIZE_MB=$(( ISO_SIZE_BYTES / 1024 / 1024 ))

if [ "${ISO_SIZE_BYTES}" -lt 1000000 ]; then
    log_error "Verification failure: Generated ISO is abnormally small (${ISO_SIZE_BYTES} bytes)."
fi

echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}       AI OS PRODUCTION HYBRID ISO BUILD SUCCESSFUL             ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e " ISO File      : ${FINAL_ISO_PATH}"
echo -e " File Size     : ${ISO_SIZE_MB} MB (${ISO_SIZE_BYTES} bytes)"
echo -e " Target Arch   : ${ARCH} (x86_64)"
echo -e " Base OS       : Alpine Linux v${ALPINE_VERSION}.${ALPINE_PATCH}"
echo -e " Boot Entry    : /usr/bin/ai-os -> /opt/ai-os/src/main_orchestrator.py"
echo -e " Bootloader    : ISOLINUX / Hybrid MBR"
echo -e " TTY Auto-Boot : TTY1 autologin enabled"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo "Test the ISO in QEMU Virtual Machine:"
echo "  qemu-system-x86_64 -m 2G -smp 2 -cdrom \"${OUTPUT_ISO}\" -boot d -net nic -net user"
echo ""
echo "Flash the ISO to a USB flash drive (CAUTION: replace /dev/sdX with your actual USB device):"
echo "  sudo dd if=\"${OUTPUT_ISO}\" of=/dev/sdX bs=4M status=progress conv=fsync"
echo -e "${GREEN}================================================================${NC}"
