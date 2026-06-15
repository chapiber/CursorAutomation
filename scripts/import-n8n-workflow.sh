#!/usr/bin/env bash
# Importe (ou met à jour) le workflow CDM dans n8n via CLI Docker.
# Usage : bash scripts/import-n8n-workflow.sh [--no-activate]
#
# Après import, unpublish → publish réenregistre le cron 7h (n8n 2.x).
# Ne pas stopper le conteneur n8n : un simple restart casse le schedule trigger.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WF_SRC="$ROOT/n8n/workflows/cdm2026-daily.json"
WF_ID="CdM2026DailyWf01"
CONTAINER="${N8N_CONTAINER:-cursor-n8n}"
COMPOSE_FILE="$ROOT/docker-compose.yml"
DOCKER="${DOCKER_BIN:-/usr/local/bin/docker}"
COMPOSE="${DOCKER} compose -f ${COMPOSE_FILE}"
ACTIVATE="${1:---activate}"

if [[ ! -f "$WF_SRC" ]]; then
  echo "Workflow introuvable : $WF_SRC" >&2
  exit 1
fi

if ! $DOCKER ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Conteneur $CONTAINER absent — démarrage..."
  $COMPOSE up -d n8n
  sleep 5
fi

TMP="$(mktemp /tmp/cdm2026-daily-import.XXXXXX.json)"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT

python3 - "$WF_SRC" "$TMP" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    data = json.load(f)
# n8n 2.x : l'activation effective passe par publish:workflow (voir fin du script).
data["active"] = False
with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
PY

echo "Copie vers conteneur $CONTAINER..."
$DOCKER cp "$TMP" "$CONTAINER:/tmp/cdm2026-daily-import.json"

echo "Import n8n..."
$DOCKER exec "$CONTAINER" n8n import:workflow --input=/tmp/cdm2026-daily-import.json

if [[ "$ACTIVATE" != "--no-activate" ]]; then
  echo "Réenregistrement planification (unpublish → publish)..."
  $DOCKER exec "$CONTAINER" n8n unpublish:workflow --id="$WF_ID" 2>/dev/null || true
  $DOCKER exec "$CONTAINER" n8n publish:workflow --id="$WF_ID"
fi

echo "Vérification..."
$DOCKER exec "$CONTAINER" n8n export:workflow --id="$WF_ID" --output=/tmp/wf-check.json
$DOCKER exec "$CONTAINER" node -e "
const w = require('/tmp/wf-check.json');
const x = Array.isArray(w) ? w[0] : w;
console.log('Workflow:', x.name);
console.log('Active:', x.active);
console.log('Nodes:', x.nodes.map(n => n.name).join(', '));
const ifNode = x.nodes.find(n => n.name === 'Encore actif ?');
if (ifNode) {
  const c = ifNode.parameters?.conditions?.conditions?.[0];
  console.log('Condition:', c?.leftValue, c?.operator?.type, c?.operator?.operation);
}
"

echo "Import terminé."
