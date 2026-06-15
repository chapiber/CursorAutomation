# Test POC — CDM 2026 quotidien

## Prérequis test

- Stack démarrée (`docker compose ps` → `healthy` / `running`)
- `.env` renseigné avec `CURSOR_API_KEY` et `RUNNER_API_KEY` valides
- GitHub `chapiber/MyDiveClub` connecté à Cursor

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

**Phases attendues :** `queued` → `agent_running` → `agent_done` → `git_pull` → `deploy` → `done`

**Champ `report_text` :** présent dès le polling ; en fin de run, vérifier les métriques (durée, matchs, tokens, fichiers commités).

```bash
curl -s http://localhost:8765/api/v1/runs/RUN_ID \
  -H "X-API-Key: $RUNNER_API_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('report_text',''))"
```

## Test 2b — Run sync legacy

```bash
curl -s -X POST http://localhost:8765/api/v1/run \
  -H "X-API-Key: $RUNNER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"job_id":"cdm2026-daily"}' | python3 -m json.tool
```

**Critères de succès :**

| Critère | Vérification |
|---------|--------------|
| Réponse API | `"status": "ok"` |
| Commit GitHub | `gh api repos/chapiber/MyDiveClub/commits/main --jq .sha` ou page GitHub |
| JSON CDM | `workspaces/MyDiveClub/site/apps/cdm2026/data/cdm2026.json` → `meta.updatedAt` récent |
| Site prod | https://diveapps.serveblog.net/portailClub/apps/cdm2026/ — scores / horaires à jour |
| Deploy log | `workspaces/MyDiveClub/deploy_logs/deploy_portailClub_*.log` dernier fichier OK |

**Durée typique :** 5–20 minutes (agent cloud + web scan).

## Test 3 — Workflow n8n manuel

1. Ouvrir `http://<IP-NAS>:5678`
2. Workflow **CDM 2026 — MAJ quotidienne**
3. **Execute workflow** (bouton play)
4. Pendant l'exécution : boucle **Attendre 30s → Lire statut → Journaliser phase** (visible dans Executions → Logs)
5. Fin : branche **Résultat OK** / **Résultat erreur** / **Expiré**, puis **Envoyer CR par mail** (credential n8n **CDM Gmail SMTP**)

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

```bash
# Dans .env, mettre une fausse clé, redémarrer :
docker compose up -d skills-runner
curl -X POST ... # doit retourner 502 avec agent_status startup_error ou error
```

Remettre la vraie clé après le test.

### Aucun changement de données

Si l'agent ne modifie rien : pas de nouveau commit, mais `git pull` + deploy doivent quand même réussir (`status: ok`).

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

## Commandes utiles

```bash
# Dernier log deploy
ls -lt workspaces/MyDiveClub/deploy_logs/ | head -3

# meta.updatedAt
python3 -c "import json; d=json.load(open('workspaces/MyDiveClub/site/apps/cdm2026/data/cdm2026.json')); print(d['meta']['updatedAt'])"

# Relancer uniquement le runner
docker compose restart skills-runner
```
