# CursorAutomation

Orchestrateur NAS : **n8n** planifie des jobs, **skills-runner** invoque des skills Cursor (SDK cloud) sur des repos GitHub, puis dÃ©ploie vers le web Synology.

## POC : CDM 2026

Workflow quotidien Ã  **7h00 (Europe/Paris)** :
1. Agent cloud exÃ©cute `@cdm2026-update` sur `chapiber/MyDiveClub`
2. Commit + push GitHub
3. `git pull` local + deploy vers `/volume1/web/portailClub`

## DÃ©marrage rapide (NAS)

```bash
cd /volume1/docker/cursor-automation
cp .env.example .env   # renseigner CURSOR_API_KEY, RUNNER_API_KEY, N8N_ENCRYPTION_KEY
./scripts/install-nas.sh
```

Voir [docs/DEPLOY-NAS.md](docs/DEPLOY-NAS.md) et [docs/TEST-POC.md](docs/TEST-POC.md).

## Stack

| Service | RÃ´le |
|---------|------|
| `skills-runner` | API FastAPI + Cursor SDK cloud + deploy |
| `n8n` | Scheduler + workflows (UI : `https://diveapps.serveblog.net/n8n/` en prod) |

## API runner

```bash
curl -X POST http://localhost:8765/api/v1/run \
  -H "X-API-Key: $RUNNER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"job_id":"cdm2026-daily"}'
```

## Ajouter un job

Ã‰diter `config/jobs.json` et `config/prompts/<skill>.txt`, puis crÃ©er un workflow n8n.
