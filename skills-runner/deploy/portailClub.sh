#!/usr/bin/env bash
# Équivalent Linux de MyDiveClub/deployer.bat — déploiement portailClub vers NAS.
set -euo pipefail

SOURCE="${SOURCE_DIR:?SOURCE_DIR requis}"
DEST="${DEPLOY_DEST_PORTAIL_CLUB:-/deploy/portailClub}"
LOG_DIR="${LOG_DIR:-/workspaces/MyDiveClub/deploy_logs}"
LOG_TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/deploy_portailClub_${LOG_TS}.log"

mkdir -p "$LOG_DIR" "$DEST"

{
  echo "============================================"
  echo "Deploiement Portail Club vers $DEST"
  echo "Journal : $LOG_FILE"
  echo "============================================"

  if [[ ! -f "$SOURCE/index.html" ]]; then
    echo "[ERREUR] Source introuvable : $SOURCE"
    exit 1
  fi

  rsync -a --delete \
    --exclude '.git' \
    --exclude 'deploy_logs' \
    --exclude 'config.local.php' \
    --exclude 'apps/cdm2026' \
    --exclude 'api/cdm2026' \
    --exclude 'lib/cdm2026.inc.php' \
    "$SOURCE/" "$DEST/"

  echo "[INFO] Generation version.json ($LOG_TS)..."
  python3 - "$DEST" "$LOG_TS" <<'PY'
import json, sys
from datetime import datetime, timezone
dest, ts = sys.argv[1], sys.argv[2]
payload = {
    "version": ts,
    "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
    "label": datetime.now().strftime("%d/%m/%Y %H:%M"),
}
with open(f"{dest}/version.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)
PY

  echo "[INFO] Cache-bust __BUILD_VERSION__ = $LOG_TS..."
  CACHE_FILES=(
    "$DEST/index.html"
    "$DEST/install.html"
    "$DEST/apps/formations/index.html"
    "$DEST/apps/materiel/index.html"
  )
  for f in "${CACHE_FILES[@]}"; do
    if [[ -f "$f" ]]; then
      sed -i "s/__BUILD_VERSION__/${LOG_TS}/g" "$f"
    fi
  done

  echo "[OK] Deploiement termine — https://diveapps.serveblog.net/portailClub/"
} 2>&1 | tee "$LOG_FILE"
