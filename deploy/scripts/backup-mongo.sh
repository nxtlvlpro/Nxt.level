#!/usr/bin/env bash
# =====================================================================
# NXT8 — daily Mongo backup with 14-day rotation.
# Runs from cron: see /etc/cron.d/nxt8-mongo-backup
# =====================================================================
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backup}"
DB_NAME="${DB_NAME:-nxt8}"
DAYS_RETENTION="${DAYS_RETENTION:-14}"

STAMP="$(date +%F)"
TARGET="${BACKUP_DIR}/nxt8-${STAMP}"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] mongodump → ${TARGET}"
mongodump --db "${DB_NAME}" --out "${TARGET}" --quiet

# Rotation: drop backups older than N days
find "${BACKUP_DIR}" -maxdepth 1 -name "nxt8-*" -type d -mtime "+${DAYS_RETENTION}" -exec rm -rf {} \; 2>/dev/null || true

# Report current size
TOTAL=$(du -sh "${BACKUP_DIR}" 2>/dev/null | awk '{print $1}')
COUNT=$(find "${BACKUP_DIR}" -maxdepth 1 -name "nxt8-*" -type d | wc -l)
echo "[$(date -Iseconds)] done. ${COUNT} backups, total ${TOTAL}"
