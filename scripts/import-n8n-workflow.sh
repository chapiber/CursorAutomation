#!/usr/bin/env bash
# Importe (ou met à jour) le workflow CDM dans n8n via CLI Docker.
# Usage : bash scripts/import-n8n-workflow.sh [--activate]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WF_SRC="$ROOT/n8n/workflows/cdm2026-daily.json"
WF_ID="CdM2026DailyWf01"
CONTAINER="${N8N_CONTAINER:-cursor-n8n}"
ACTIVATE="${1:-}"

if [[ ! -f "$WF_SRC" ]]; then
  echo "Workflow introuvable : $WF_SRC" >&2
  exit 1
fi

TMP="$(mktemp /tmp/cdm2026-daily-import.XXXXXX.json)"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

python3 - "$WF_SRC" "$TMP" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    data = json.load(f)
data["active"] = True
with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PY

echo "Copie vers conteneur $CONTAINER..."
docker cp "$TMP" "$CONTAINER:/tmp/cdm2026-daily-import.json"

echo "Import n8n..."
docker exec "$CONTAINER" n8n import:workflow --input=/tmp/cdm2026-daily-import.json

DB="${ROOT}/n8n_data/.n8n/database.sqlite"
if [[ -f "$DB" ]] && [[ "$ACTIVATE" == "--activate" || "$ACTIVATE" == "" ]]; then
  echo "Activation workflow $WF_ID..."
  docker compose -f "$ROOT/docker-compose.yml" stop n8n >/dev/null 2>&1 || true
  docker run --rm -v "$ROOT/n8n_data/.n8n:/db" alpine:3.20 sh -c \
    "apk add --no-cache sqlite >/dev/null && sqlite3 /db/database.sqlite \"UPDATE workflow_entity SET active = 1 WHERE id = '$WF_ID'; SELECT id, active FROM workflow_entity WHERE id='$WF_ID';\""
  docker compose -f "$ROOT/docker-compose.yml" start n8n >/dev/null 2>&1 || docker start "$CONTAINER"
fi

echo "Vérification..."
docker exec "$CONTAINER" n8n export:workflow --id="$WF_ID" --output=/tmp/wf-check.json
docker exec "$CONTAINER" node -e "
const w = require('/tmp/wf-check.json');
const x = Array.isArray(w) ? w[0] : w;
console.log('Workflow:', x.name);
console.log('Active:', x.active);
console.log('Nodes:', x.nodes.map(n => n.name).join(', '));
"

echo "Import terminé."
