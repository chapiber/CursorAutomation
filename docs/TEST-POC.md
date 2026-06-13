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

## Test 2 — Run manuel (sans attendre 7h)

```bash
source .env
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
4. Vérifier : node « Appeler skills-runner » vert → branche « Résultat OK »

## Test 4 — Planification 7h

- Workflow **activé** (toggle ON)
- Timezone workflow : `Europe/Paris`
- Cron : `0 7 * * *`

**Validation rapide :** modifier temporairement le cron à `*/5 * * * *`, attendre 5 min, vérifier l'historique **Executions** dans n8n, puis remettre `0 7 * * *`.

## Test 5 — Cas d'erreur

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
| Action requise | Renseigner `CURSOR_API_KEY` réelle dans `.env` puis `docker compose restart skills-runner` |
| n8n | Importer workflow `n8n/workflows/cdm2026-daily.json` après 1ère connexion UI |
| RUNNER_API_KEY | Généré sur NAS (voir `.env` sur le NAS, non reproduit ici) |

## Commandes utiles

```bash
# Dernier log deploy
ls -lt workspaces/MyDiveClub/deploy_logs/ | head -3

# meta.updatedAt
python3 -c "import json; d=json.load(open('workspaces/MyDiveClub/site/apps/cdm2026/data/cdm2026.json')); print(d['meta']['updatedAt'])"

# Relancer uniquement le runner
docker compose restart skills-runner
```
