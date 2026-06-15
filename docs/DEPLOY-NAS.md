# DÃ©ploiement CursorAutomation sur NAS Synology

## PrÃ©requis

| Ã‰lÃ©ment | DÃ©tail |
|---------|--------|
| Docker | Container Manager actif sur `NasChapron` |
| Git | `git` disponible en SSH sur le NAS |
| Repo GitHub | `chapiber/CursorAutomation` clonable |
| Cursor API | ClÃ© sur [Dashboard â†’ Integrations](https://cursor.com/dashboard/integrations) â€” **optionnelle pour CDM** (jobs `handler: agent` uniquement) |
| GitHub â†” Cursor | Repo `chapiber/MyDiveClub` connectÃ© au compte Cursor â€” **plus requis pour CDM** (MAJ programmatique) |
| AccÃ¨s web | `/volume1/web/portailClub` accessible en Ã©criture |

## Emplacement

```text
/volume1/docker/cursor-automation/
```

## Installation

### 1. Cloner le projet

```bash
ssh chapron@NasChapron
sudo mkdir -p /volume1/docker/cursor-automation
cd /volume1/docker/cursor-automation
```

**Si `git` est installÃ© (paquet Synology Git Server) :**

```bash
git clone https://github.com/chapiber/CursorAutomation.git .
```

**Sinon (sans git sur le NAS) :**

```bash
curl -sL https://github.com/chapiber/CursorAutomation/archive/refs/heads/master.tar.gz -o /tmp/cursor-automation.tar.gz
tar -xzf /tmp/cursor-automation.tar.gz --strip-components=1
```

Ou utiliser le script :

```bash
bash scripts/install-nas.sh
```

**Docker sur Synology :** les commandes passent souvent par `sudo /usr/local/bin/docker compose`.

### 2. Configurer les secrets

```bash
cp .env.example .env
nano .env
```

Renseigner obligatoirement :

- `CURSOR_API_KEY` â€” clÃ© API Cursor (**optionnel** si seul le job `cdm2026-daily` est utilisÃ©)
- `RUNNER_API_KEY` â€” gÃ©nÃ©rer : `openssl rand -hex 32`
- `N8N_ENCRYPTION_KEY` â€” gÃ©nÃ©rer : `openssl rand -hex 32`

### 3. ClÃ© SSH GitHub (recommandÃ© â€” pull + push CDM)

Le job `cdm2026-daily` utilise `handler: cdm_update` : le runner fait **git pull**, met Ã  jour `cdm2026.json`, puis **commit + push** sur `chapiber/MyDiveClub`.

```bash
mkdir -p secrets
ssh-keygen -t ed25519 -f secrets/id_ed25519 -N ""
# Ajouter secrets/id_ed25519.pub comme deploy key **read/write** sur chapiber/MyDiveClub uniquement
chmod 600 secrets/id_ed25519
```

> **Important** : une clÃ© **read-only** suffit pour l'ancien flux agent ; la MAJ programmatique exige **write** sur ce dÃ©pÃ´t. Utiliser une deploy key dÃ©diÃ©e (pas votre clÃ© personnelle).

Repo public : le clone HTTPS fonctionne ; le **push** nÃ©cessite tout de mÃªme une authentification SSH ou un token.

### 4. DÃ©marrer la stack

```bash
docker compose build
docker compose up -d
docker compose ps
```

### 5. Importer le workflow n8n

**Automatique (recommandÃ©) :**

```bash
bash scripts/import-n8n-workflow.sh
```

Le script copie `n8n/workflows/cdm2026-daily.json` dans le conteneur, l'importe via `n8n import:workflow`, puis **unpublish â†’ publish** (`CdM2026DailyWf01`) pour rÃ©enregistrer le cron 7h sans redÃ©marrer n8n.

> **Important** : ne pas stopper/redÃ©marrer n8n manuellement aprÃ¨s import â€” cela dÃ©synchronise le schedule trigger. En cas de doute, relancer `bash scripts/import-n8n-workflow.sh`.

**Manuel (UI) :**

1. Ouvrir `http://<IP-NAS>:5678`
2. CrÃ©er un compte admin n8n (premiÃ¨re visite)
3. **Workflows** â†’ **Import from File** â†’ `n8n/workflows/cdm2026-daily.json`
4. VÃ©rifier que la variable d'environnement `RUNNER_API_KEY` est bien passÃ©e au conteneur n8n (dÃ©jÃ  dans `docker-compose.yml`)
5. **Activer** le workflow (toggle en haut Ã  droite)

**AprÃ¨s mise Ã  jour du workflow** (date de fin, CR texte) : rÃ©importer `n8n/workflows/cdm2026-daily.json` (remplace l'existant) ou recrÃ©er les nÅ“uds manuellement.

### Date de fin du job CDM

- DerniÃ¨re exÃ©cution planifiÃ©e : **14/07/2026 Ã  7h** (Europe/Paris)
- Ã€ partir du **15/07/2026** : le nÅ“ud n8n **Encore actif ?** route vers **ExpirÃ©** (CR texte sans appel agent)
- Garde-fou API : `stop_after: "2026-07-14"` dans `config/jobs.json` â†’ `POST /api/v1/runs` retourne **410** si date dÃ©passÃ©e

### Compte-rendu e-mail (Gmail OAuth n8n)

Chaque exÃ©cution envoie un e-mail Ã  **chapron.loic@gmail.com** via le nÅ“ud **Gmail** (OAuth2). **Ne pas utiliser SMTP + mot de passe d'application** : sur n8n 2.21+ (NAS en 2.23), la validation SMTP Gmail Ã©choue souvent (`Connection closed unexpectedly`) mÃªme avec un App Password valide.

#### 1. Google Cloud (une fois)

1. [Google Cloud Console](https://console.cloud.google.com/) â†’ projet (ou en crÃ©er un)
2. **APIs & Services** â†’ **Library** â†’ activer **Gmail API**
3. **OAuth consent screen** â†’ type **External** â†’ ajouter ton e-mail en testeur
4. **Credentials** â†’ **Create credentials** â†’ **OAuth client ID** â†’ type **Web application**
5. **Authorized redirect URIs** (doit correspondre **exactement** Ã  lâ€™URL affichÃ©e dans n8n) :

```text
http://localhost:5678/rest/oauth2-credential/callback
```

> Google **refuse** `192.168.x.x` et `0.0.0.0`. Si n8n affiche `http://0.0.0.0:5678/...`, ajouter `N8N_EDITOR_BASE_URL=http://localhost:5678` dans `.env` puis `docker compose up -d n8n`.

#### 2b. Tunnel SSH (obligatoire avec localhost)

Sur ton PC :

```powershell
ssh -p 1982 -L 5678:127.0.0.1:5678 chapron@192.168.1.28
```

Ouvre **http://localhost:5678** (pas lâ€™IP du NAS) pour crÃ©er le credential.

#### 2c. Credential n8n

1. `http://localhost:5678` â†’ **Credentials** â†’ **Gmail OAuth2**
2. Nom : **`CDM Gmail OAuth`** (exact)
3. VÃ©rifier que **OAuth Redirect URL** = `http://localhost:5678/rest/oauth2-credential/callback`
4. Coller Client ID + Client Secret
5. **Sign in with Google** â†’ autoriser `chapron.loic@gmail.com`
6. Workflow **CDM 2026 â€” MAJ quotidienne** â†’ nÅ“ud **Envoyer CR par mail** â†’ **CDM Gmail OAuth**

> **Audience** Google Cloud : ajouter `chapron.loic@gmail.com` en **utilisateur test** tant que lâ€™app est en mode Â« Test Â».

#### 3. Test

ExÃ©cuter le workflow manuellement (branche **ExpirÃ©** = rapide) â†’ vÃ©rifier la rÃ©ception du mail.

> Sauvegarder `N8N_ENCRYPTION_KEY` : sans elle, les tokens OAuth n8n ne sont plus dÃ©chiffrables aprÃ¨s restauration.

Consultation du CR sans relancer :

```bash
curl -s "http://localhost:8765/api/v1/runs/latest?job_id=cdm2026-daily" \
  -H "X-API-Key: $RUNNER_API_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin)['report_text'])"
```

Format minimaliste (MAJ programmatique `cdm_update`) :

```text
CDM 2026 â€” compte-rendu
DurÃ©e MAJ : 45 s
Matchs mis Ã  jour : 2
Fichiers commitÃ©s : 1
Commit : abc1234
DurÃ©e totale (pull + deploy) : 72 s
```

> Ancien flux agent (si `handler: agent`) : lignes Â« DurÃ©e agent Â» et Â« Tokens Â» Ã  la place de Â« DurÃ©e MAJ Â».

### Flux CDM programmatique (sans IA)

Le job `cdm2026-daily` (`config/jobs.json`) utilise `handler: cdm_update` :

1. `git pull` MyDiveClub
2. Fetch scores (matchcalendar.football, franceinfo, fifa.com)
3. Merge + recalcul standings
4. `git commit` + `push` si diff
5. Deploy `portailClub.sh`

**DurÃ©e typique :** 30 s â€“ 2 min. **Pas de `CURSOR_API_KEY`** requis.

Phases polling n8n : `git_pull` â†’ `fetch` â†’ `merge` â†’ `standings` â†’ `git_push` â†’ `deploy` â†’ `done`

Logs `[CDM_PROGRESS]` dans `GET /api/v1/runs/{id}` ; `[CDM_STATS]` dans `agent_summary` pour compatibilitÃ© parsing.

### 6. VÃ©rifier la santÃ©

```bash
curl -s http://localhost:8765/health
# {"status":"ok","service":"skills-runner"}
```

## AccÃ¨s externe HTTPS (`diveapps.serveblog.net/n8n`)

URL publique cible :

```text
https://diveapps.serveblog.net/n8n/
```

### PrÃ©requis

1. Compte **owner** n8n dÃ©jÃ  crÃ©Ã© en local (`http://192.168.1.28:5678` ou tunnel SSH) â€” **avant** dâ€™ouvrir lâ€™accÃ¨s Internet
2. Reverse proxy DSM configurÃ© (voir ci-dessous)
3. Variables `.env` alignÃ©es sur lâ€™URL publique (voir `.env.example`)

### 1. Reverse proxy nginx (`/n8n` sur `diveapps.serveblog.net`)

Le reverse proxy DSM route dÃ©jÃ  `diveapps.serveblog.net:443` â†’ Web Station (`localhost:80`). Lâ€™UI DSM **ne gÃ¨re pas** les sous-chemins sur un hÃ´te existant â€” le chemin `/n8n` est ajoutÃ© via nginx :

```bash
cd /volume1/docker/cursor-automation
bash scripts/setup-n8n-reverse-proxy.sh
```

Ce script insÃ¨re `location /n8n/` â†’ `http://127.0.0.1:5678` (WebSocket inclus) dans la config reverse proxy existante. Ã€ relancer si DSM rÃ©gÃ©nÃ¨re `server.ReverseProxy.conf`.

Les ports Docker n8n et runner sont liÃ©s Ã  `127.0.0.1` uniquement â€” pas dâ€™accÃ¨s direct via `<IP-NAS>:5678`.

### 2. Variables `.env` + auth nginx

```bash
bash scripts/apply-n8n-public-env.sh   # .env HTTPS + secrets/n8n.htpasswd
bash scripts/setup-n8n-reverse-proxy.sh   # sudo â€” route /n8n + popup login nginx
docker compose up -d n8n
```

**Authentification (double verrou) :**
1. **Popup nginx** â€” identifiants dans `secrets/n8n-gateway.env` (gÃ©nÃ©rÃ©s par `apply-n8n-public-env.sh`)
2. **Login owner n8n** â€” e-mail + mot de passe crÃ©Ã©s Ã  lâ€™installation

> n8n 2.23 ignore `N8N_BASIC_AUTH_*` ; lâ€™auth Â« porte dâ€™entrÃ©e Â» est faite par **nginx** (`auth_basic`).

Ou manuellement dans `.env` :

```env
N8N_EDITOR_BASE_URL=https://diveapps.serveblog.net/n8n
N8N_PROTOCOL=https
N8N_SECURE_COOKIE=true
WEBHOOK_URL=https://diveapps.serveblog.net/n8n/
```

### 3. Authentification obligatoire

Ã€ lâ€™arrivÃ©e sur `https://diveapps.serveblog.net/n8n/` :

1. **Popup nginx** â€” `secrets/n8n-gateway.env` (`N8N_GATEWAY_USER` / `N8N_GATEWAY_PASSWORD`)
2. **Login owner n8n** â€” e-mail + mot de passe crÃ©Ã©s Ã  lâ€™installation

Sans identifiants â†’ **401**, lâ€™UI n8n nâ€™est pas accessible.

Les webhooks restent sur des URLs dÃ©diÃ©es (sans Basic Auth) :

```text
https://diveapps.serveblog.net/n8n/webhook/<uuid>
```

### 4. OAuth Gmail (URL publique)

Ajouter dans Google Cloud Console :

```text
https://diveapps.serveblog.net/n8n/rest/oauth2-credential/callback
```

Reconnecter le credential **CDM Gmail OAuth** dans n8n aprÃ¨s bascule HTTPS.

### 5. Tests sÃ©curitÃ© (depuis 4G ou hors LAN)

```bash
# Doit retourner 401 sans identifiants
curl -sI https://diveapps.serveblog.net/n8n/

# Avec Basic Auth : 200 ou redirection login n8n
curl -sI -u "user:pass" https://diveapps.serveblog.net/n8n/
```

### 6. Retour en mode local (maintenance OAuth)

Dans `.env` :

```env
N8N_EDITOR_BASE_URL=http://localhost:5678
N8N_PATH=
N8N_PROTOCOL=http
N8N_SECURE_COOKIE=false
WEBHOOK_URL=
N8N_BASIC_AUTH_ACTIVE=false
```

Tunnel SSH puis `docker compose up -d n8n`.

## Volumes importants

| Volume hÃ´te | Montage conteneur | RÃ´le |
|-------------|-------------------|------|
| `./config` | `/config` | jobs.json + prompts |
| `./workspaces` | `/workspaces` | clone MyDiveClub |
| `/volume1/web/portailClub` | `/deploy/portailClub` | site dÃ©ployÃ© |
| `./n8n_data` | persistance n8n | workflows, historique |
| `./logs` | logs runner | diagnostics |

## Mise Ã  jour

```bash
cd /volume1/docker/cursor-automation
git pull
docker compose build skills-runner
docker compose up -d
bash scripts/import-n8n-workflow.sh
```

## DÃ©pannage

| SymptÃ´me | Action |
|----------|--------|
| `access to env vars denied` | Ajouter `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` au conteneur n8n puis recrÃ©er |
| `401 X-API-Key invalide` | Aligner `RUNNER_API_KEY` dans `.env` et header n8n |
| Agent cloud Ã©choue | Jobs `handler: agent` uniquement â€” vÃ©rifier `CURSOR_API_KEY` |
| `git push` Ã©chouÃ© (CDM) | Deploy key **read/write** sur MyDiveClub ; voir section secrets |
| Fetch web sans MAJ | Sources indisponibles ou HTML changÃ© â€” run OK, `matches_updated: 0` |
| `git pull` Ã©choue | Deploy key ou repo public |
| Deploy Ã©choue | VÃ©rifier permissions `/volume1/web/portailClub` |
| n8n EACCES sur volume | Utiliser bind mount `./n8n_data:/data` + `chmod 777 n8n_data` + `N8N_USER_FOLDER=/data` |
| `500 Internal Server Error` | Souvent `git clone` Ã©chouÃ© (dossier `/workspaces/MyDiveClub` sans `.git`) â€” corrigÃ© par rÃ©init workspace ; vÃ©rifier `docker logs cursor-skills-runner` |
| `git clone` exit 128 | Dossier cible dÃ©jÃ  prÃ©sent â€” le runner supprime et reclone automatiquement (v0.2+) |
| Suivi run en cours | `GET /api/v1/runs/{run_id}` ou `logs/runs/{run_id}.json` sur NAS |
| Timeout n8n | Boucle polling 30s Ã— ~40 = 20 min max ; MAJ programmatique ~1â€“2 min |
| Pas de run 7h aprÃ¨s import / restart | `staticData` schedule vide â€” relancer `bash scripts/import-n8n-workflow.sh` (unpublish â†’ publish) |
| Manuel â†’ branche **ExpirÃ©** avant le 14/07 | Expression date du nÅ“ud **Encore actif ?** non Ã©valuÃ©e â€” rÃ©importer le workflow corrigÃ© |
| `410 job expirÃ©` | Normal aprÃ¨s le 14/07/2026 â€” vÃ©rifier `stop_after` dans jobs.json |
| `report_text` vide / n/d | VÃ©rifier `result.cdm.stats` ou `agent.stats.matches_updated` dans le JSON run |
| E-mail non reÃ§u | Credential **CDM Gmail OAuth** connectÃ© ? Redirect URI HTTPS ou `localhost` selon mode |
| UI n8n cassÃ©e derriÃ¨re proxy | WebSocket DSM activÃ© ? `N8N_EDITOR_BASE_URL` = URL publique exacte (port inclus) |

Logs :

```bash
docker compose logs skills-runner -f
docker compose logs n8n -f
```
