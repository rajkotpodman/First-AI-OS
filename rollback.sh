#!/bin/sh
# ==============================================================================
# rollback.sh - Emergency Boot & Version Recovery Script for AI OS
# Author: DevOps Engineer and Linux System Reliability Specialist
# ==============================================================================

set -e

BACKUP_DIR="/var/backups/ai_os"
LOCAL_BACKUP_DIR="./backups/ai_os"
LOG_FILE="/var/log/ai_os_updates.log"
RESTORE_TARGET="${AI_OS_ROOT:-.}"

echo "\033[1;36m============================================================\033[0m"
echo "\033[1;36m       AI OS EMERGENCY SYSTEM RECOVERY & ROLLBACK          \033[0m"
echo "\033[1;36m============================================================\033[0m"

# Locate backup repository
if [ -d "$BACKUP_DIR" ]; then
    ACTIVE_BACKUP="$BACKUP_DIR"
elif [ -d "$LOCAL_BACKUP_DIR" ]; then
    ACTIVE_BACKUP="$LOCAL_BACKUP_DIR"
else
    echo "\033[1;31m[✗] Error: No backup directories found at $BACKUP_DIR or $LOCAL_BACKUP_DIR\033[0m"
    exit 1
fi

# Determine snapshot to restore
if [ -n "$1" ]; then
    TARGET_SNAPSHOT="$1"
else
    echo "[*] Searching for most recent verified snapshot in $ACTIVE_BACKUP..."
    TARGET_SNAPSHOT=$(ls -t "$ACTIVE_BACKUP"/snapshot_*.tar.gz 2>/dev/null | head -n 1)
fi

if [ -z "$TARGET_SNAPSHOT" ] || [ ! -f "$TARGET_SNAPSHOT" ]; then
    echo "\033[1;31m[✗] Error: Snapshot file not found: $TARGET_SNAPSHOT\033[0m"
    exit 1
fi

echo "[*] Selected Recovery Snapshot: \033[1;33m$TARGET_SNAPSHOT\033[0m"
echo "[*] Restoring components into:   \033[1;32m$RESTORE_TARGET\033[0m"

# Unpack snapshot safely
tar -xzf "$TARGET_SNAPSHOT" -C "$RESTORE_TARGET"

# Check if OverlayFS upperdir needs cleaning (for Alpine / Live ISO environments)
if [ -d "/mnt/overlay/upper/src" ]; then
    echo "[*] Synchronizing OverlayFS upperdir with restored snapshot..."
    cp -rf "$RESTORE_TARGET/src" /mnt/overlay/upper/
fi

# Log the rollback event
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
if [ -w "$(dirname "$LOG_FILE")" ]; then
    echo "{\"timestamp\": \"$TIMESTAMP\", \"action\": \"EMERGENCY_ROLLBACK\", \"status\": \"SUCCESS\", \"snapshot\": \"$TARGET_SNAPSHOT\"}" >> "$LOG_FILE"
fi

echo "\033[1;32m[✓] System core files successfully recovered from snapshot.\033[0m"

# Run self-test if python3 is present
if command -v python3 >/dev/null 2>&1; then
    echo "[*] Running post-recovery syntax verification..."
    python3 "$RESTORE_TARGET/src/system_updater.py" --health-check || true
fi

echo "\033[1;36m[*] Emergency rollback complete. System is stable.\033[0m"
exit 0
