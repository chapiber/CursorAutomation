# Test POC — CDM 2026 quotidien

## Prérequis test

- Stack démarrée (`docker compose ps` → `healthy` / `running`)
- `.env` renseigné avec `RUNNER_API_KEY` valide
- Deploy key **read/write** sur `chapiber/MyDiveClub` montée dans `secrets/id_ed25519` (push CDM)
- `CURSOR_API_KEY` **non requis** pour `cdm2026-daily` (MAJ programmatique)

## Test 1 — Santé de la stack

```bash
cd /volume1/docker/cursor-automation

docker compose ps
curl -s http://localhost:8765/health
docker compose logs skills-runner --tail 30
```

**Attendu :** `{"status":"ok","service":"skills-runner"}`

## Test 2 — Run async avec suivi (recommandé)

```bash
source .env
# Démarrer
curl -s -X POST http://localhost:8765/api/v1/runs \
  -H "X-API-Key: $RUNNER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"job_id":"cdm2026-daily"}' | python3 -m json.tool

# Polling (remplacer RUN_ID)
curl -s http://localhost:8765/api/v1/runs/RUN_ID \
  -H "X-API-Key: $RUNNER_API_KEY" | python3 -m json.tool

# Dernier run du job
curl -s "http://localhost:8765/api/v1/runs/latest?job_id=cdm2026-daily" \
  -H "X-API-Key: $RUNNER_API_KEY" | python3 -m json.tool

# Journal fichier
ls -lt logs/runs/
cat logs/runs/RUN_ID.json
```

**Phases attendues :** `queued` → `git_pull` → `fetch` → `merge` → `standings` → `git_push` → `deploy` → `done`

**Champ `report_text` :** présent dès le polling ; en fin de run, vérifier durée MAJ, matchs mis à jour, fichiers commités (pas de tokens).

```bash
curl -s http://localhost:8765/api/v1/runs/RUN_ID \
  -H "X-API-Key: $RUNNER_API_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('report_text',''))"
```

## Test 2b — Run sync legacy

> `cdm2026-daily` est **async uniquement** (`handler: cdm_update`). L'endpoint sync retourne une erreur — utiliser Test 2.

```bash
curl -s -X POST http://localhost:8765/api/v1/run \
  -H "X-API-Key: $RUNNER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"job_id":"cdm2026-daily"}' | python3 -m json.tool
# Attendu : HTTP 502 ou NotImplementedError
```

**Critères de succès :**

| Critère | Vérification |
|---------|--------------|
| Réponse API | `"status": "ok"` |
| Commit GitHub | `gh api repos/chapiber/MyDiveClub/commits/main --jq .sha` ou page GitHub |
| JSON CDM | `workspaces/cdm2026/site/public/data/cdm2026.json` → `meta.updatedAt` récent |
| Site prod | https://diveapps.serveblog.net/portailClub/apps/cdm2026/ — scores / horaires à jour |
| Deploy log | `workspaces/MyDiveClub/deploy_logs/deploy_portailClub_*.log` dernier fichier OK |

**Durée typique :** 30 s – 2 min (fetch web + merge + push + deploy).

## Test 3 — Workflow n8n manuel

1. Ouvrir `http://<IP-NAS>:5678`
2. Workflow **CDM 2026 — MAJ quotidienne**
3. **Execute workflow** (bouton play)
4. Pendant l'exécution : boucle **Attendre 30s → Lire statut → Journaliser phase** (visible dans Executions → Logs)
5. Fin : branche **Résultat OK** / **Résultat erreur** / **Expiré**, puis **Envoyer CR par mail** (credential n8n **CDM Gmail OAuth**)

## Test 4 — Expiration workflow (après 14/07/2026)

Simuler côté API (sans attendre la date) :

```bash
# Modifier temporairement stop_after à une date passée dans config/jobs.json, rebuild :
docker compose up -d --build skills-runner
curl -s -X POST http://localhost:8765/api/v1/runs \
  -H "X-API-Key: $RUNNER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"job_id":"cdm2026-daily"}' -w "\nHTTP %{http_code}\n"
# Attendu : HTTP 410, detail.job_expired=true
```

Dans n8n : exécuter le workflow manuellement avec date > 14/07 → branche **Expiré** et CR :

```text
CDM 2026 — workflow expiré (dernière exécution : 14/07/2026)
```

Remettre `stop_after: "2026-07-14"` après le test.

## Test 5 — Planification 7h

- Workflow **publié** (`n8n publish:workflow --id=CdM2026DailyWf01` ou import script)
- Timezone workflow : `Europe/Paris`
- Cron : `0 7 * * *`

**Validation rapide :** modifier temporairement le cron à `*/5 * * * *`, attendre 5 min, vérifier l'historique **Executions** dans n8n, puis remettre `0 7 * * *`.

**Après import ou redémarrage n8n :** relancer `bash scripts/import-n8n-workflow.sh` (unpublish → publish) — un simple toggle UI ou restart ne suffit pas toujours.

## Test 6 — Cas d'erreur

### Clé Cursor invalide

Ne s'applique plus au job CDM (`cdm_update`). Pour d'éventuels futurs jobs `handler: agent` :

```bash
# Dans .env, mettre une fausse clé, redémarrer :
docker compose up -d skills-runner
```

### Aucun changement de données

Si les sources web ne rapportent rien de nouveau : pas de nouveau commit (`git_push.committed: false`), mais pull + deploy doivent réussir (`status: ok`, `matches_updated: 0`).

## Journal du premier run POC

| Champ | Valeur |
|-------|--------|
| Date | 2026-06-13 |
| NAS | NasChapron — `/volume1/docker/cursor-automation` |
| Stack | `cursor-skills-runner` healthy, ports 8765 + 5678 |
| Health | `GET /health` → `{"status":"ok"}` |
| Run agent | **Bloqué** — `CURSOR_API_KEY` placeholder (`Invalid User API Key`) |
| Action requise | Renseigner `CURSOR_API_KEY` réelle dans `.env` puis `sudo /usr/local/bin/docker compose restart skills-runner` |
| n8n UI | http://192.168.1.28:5678 — **HTTP 200 OK** après bind mount `./n8n_data:/data` |
| Workflow | Importer `n8n/workflows/cdm2026-daily.json` puis activer |

## Test 7 — Tests unitaires (local / CI)

```bash
cd skills-runner
pip install -r requirements.txt
pytest tests/ -q
```

## Commandes utiles

```bash
# Dernier log deploy
ls -lt workspaces/MyDiveClub/deploy_logs/ | head -3

# meta.updatedAt
python3 -c "import json; d=json.load(open('workspaces/cdm2026/site/public/data/cdm2026.json')); print(d['meta']['updatedAt'])"

# Relancer uniquement le runner
docker compose restart skills-runner
```
