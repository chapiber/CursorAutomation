#!/usr/bin/env bash
# Déploiement CDM 2026 vers NAS (apps/cdm2026 + api/cdm2026).
set -euo pipefail

ROOT="${SOURCE_DIR:?SOURCE_DIR requis}"
PUBLIC="${ROOT}/public"
API="${ROOT}/api"
DEST_BASE="${DEPLOY_DEST_PORTAIL_CLUB:-/deploy/portailClub}"
DEST_APP="${DEST_BASE}/apps/cdm2026"
DEST_API="${DEST_BASE}/api/cdm2026"
LOG_DIR="${LOG_DIR:-/workspaces/cdm2026/deploy_logs}"
LOG_TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/deploy_cdm2026_${LOG_TS}.log"

mkdir -p "$LOG_DIR" "$DEST_APP" "$DEST_API"

{
  echo "============================================"
  echo "Deploiement CDM 2026 vers $DEST_BASE"
  echo "Journal : $LOG_FILE"
  echo "============================================"

  if [[ ! -f "$PUBLIC/index.html" ]]; then
    echo "[ERREUR] Source introuvable : $PUBLIC"
    exit 1
  fi

  echo "[INFO] Deploy front apps/cdm2026..."
  rsync -a --delete \
    --exclude '.git' \
    --exclude 'deploy_logs' \
    --exclude 'config.local.php' \
    "$PUBLIC/" "$DEST_APP/"

  echo "[INFO] Deploy API api/cdm2026..."
  rsync -a --delete \
    --exclude '.git' \
    "$API/" "$DEST_API/"

  echo "[INFO] Cache-bust __BUILD_VERSION__ = $LOG_TS..."
  if [[ -f "$DEST_APP/index.html" ]]; then
    sed -i "s/__BUILD_VERSION__/${LOG_TS}/g" "$DEST_APP/index.html"
  fi

  echo "[OK] Deploiement termine — https://diveapps.serveblog.net/portailClub/apps/cdm2026/"
} 2>&1 | tee "$LOG_FILE"
