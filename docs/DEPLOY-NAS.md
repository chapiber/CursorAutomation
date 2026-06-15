# Déploiement CursorAutomation sur NAS Synology

## Prérequis

| Élément | Détail |
|---------|--------|
| Docker | Container Manager actif sur `NasChapron` |
| Git | `git` disponible en SSH sur le NAS |
| Repo GitHub | `chapiber/CursorAutomation` clonable |
| Cursor API | Clé sur [Dashboard → Integrations](https://cursor.com/dashboard/integrations) |
| GitHub ↔ Cursor | Repo `chapiber/MyDiveClub` connecté au compte Cursor (cloud agents) |
| Accès web | `/volume1/web/portailClub` accessible en écriture |

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

**Si `git` est installé (paquet Synology Git Server) :**

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

- `CURSOR_API_KEY` — clé API Cursor
- `RUNNER_API_KEY` — générer : `openssl rand -hex 32`
- `N8N_ENCRYPTION_KEY` — générer : `openssl rand -hex 32`

### 3. Clé SSH GitHub (optionnel, repo privé)

Pour `git pull` après push de l'agent cloud :

```bash
mkdir -p secrets
ssh-keygen -t ed25519 -f secrets/id_ed25519 -N ""
# Ajouter secrets/id_ed25519.pub comme deploy key (read-only) sur chapiber/MyDiveClub
chmod 600 secrets/id_ed25519
```

Repo public : le clone/pull HTTPS fonctionne sans clé.

### 4. Démarrer la stack

```bash
docker compose build
docker compose up -d
docker compose ps
```

### 5. Importer le workflow n8n

**Automatique (recommandé) :**

```bash
bash scripts/import-n8n-workflow.sh
```

Le script copie `n8n/workflows/cdm2026-daily.json` dans le conteneur, l'importe via `n8n import:workflow`, puis **unpublish → publish** (`CdM2026DailyWf01`) pour réenregistrer le cron 7h sans redémarrer n8n.

> **Important** : ne pas stopper/redémarrer n8n manuellement après import — cela désynchronise le schedule trigger. En cas de doute, relancer `bash scripts/import-n8n-workflow.sh`.

**Manuel (UI) :**

1. Ouvrir `http://<IP-NAS>:5678`
2. Créer un compte admin n8n (première visite)
3. **Workflows** → **Import from File** → `n8n/workflows/cdm2026-daily.json`
4. Vérifier que la variable d'environnement `RUNNER_API_KEY` est bien passée au conteneur n8n (déjà dans `docker-compose.yml`)
5. **Activer** le workflow (toggle en haut à droite)

**Après mise à jour du workflow** (date de fin, CR texte) : réimporter `n8n/workflows/cdm2026-daily.json` (remplace l'existant) ou recréer les nœuds manuellement.

### Date de fin du job CDM

- Dernière exécution planifiée : **14/07/2026 à 7h** (Europe/Paris)
- À partir du **15/07/2026** : le nœud n8n **Encore actif ?** route vers **Expiré** (CR texte sans appel agent)
- Garde-fou API : `stop_after: "2026-07-14"` dans `config/jobs.json` → `POST /api/v1/runs` retourne **410** si date dépassée

### Compte-rendu e-mail (credential SMTP n8n)

Chaque exécution envoie un e-mail à **chapron.loic@gmail.com** via le nœud **Envoyer CR par mail** (SMTP n8n). Le mot de passe **n'est pas** stocké dans `.env` : il est chiffré dans la base n8n (`N8N_ENCRYPTION_KEY`).

**Créer le credential (une fois) :**

1. Ouvrir `http://<IP-NAS>:5678`
2. **Credentials** → **Add credential** → **SMTP**
3. Renseigner :

| Champ | Valeur |
|-------|--------|
| **Credential name** | `CDM Gmail SMTP` (nom exact) |
| **User** | `chapron.loic@gmail.com` |
| **Password** | mot de passe d'application Gmail |
| **Host** | `smtp.gmail.com` |
| **Port** | `587` |
| **SSL/TLS** | STARTTLS |

4. Ouvrir le workflow **CDM 2026 — MAJ quotidienne** → nœud **Envoyer CR par mail** → vérifier que le credential **CDM Gmail SMTP** est sélectionné (après import, parfois à relier manuellement).
5. **Test** : exécuter le workflow manuellement sur la branche **Expiré** (rapide) ou attendre une fin de run complète.

> Sauvegarder `N8N_ENCRYPTION_KEY` : sans elle, les credentials n8n ne sont plus déchiffrables après restauration.

Consultation du CR sans relancer :

```bash
curl -s "http://localhost:8765/api/v1/runs/latest?job_id=cdm2026-daily" \
  -H "X-API-Key: $RUNNER_API_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin)['report_text'])"
```

Format minimaliste :

```text
CDM 2026 — compte-rendu
Durée agent : 312 s
Matchs mis à jour : 8
Tokens : 45200 (in 38000 / out 7200)
Fichiers commités : 1
Commit : abc1234
```

### 6. Vérifier la santé

```bash
curl -s http://localhost:8765/health
# {"status":"ok","service":"skills-runner"}
```

## Volumes importants

| Volume hôte | Montage conteneur | Rôle |
|-------------|-------------------|------|
| `./config` | `/config` | jobs.json + prompts |
| `./workspaces` | `/workspaces` | clone MyDiveClub |
| `/volume1/web/portailClub` | `/deploy/portailClub` | site déployé |
| `./n8n_data` | persistance n8n | workflows, historique |
| `./logs` | logs runner | diagnostics |

## Mise à jour

```bash
cd /volume1/docker/cursor-automation
git pull
docker compose build skills-runner
docker compose up -d
bash scripts/import-n8n-workflow.sh
```

## Dépannage

| Symptôme | Action |
|----------|--------|
| `access to env vars denied` | Ajouter `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` au conteneur n8n puis recréer |
| `401 X-API-Key invalide` | Aligner `RUNNER_API_KEY` dans `.env` et header n8n |
| Agent cloud échoue | Vérifier `CURSOR_API_KEY` et connexion GitHub Cursor |
| `git pull` échoue | Deploy key ou repo public |
| Deploy échoue | Vérifier permissions `/volume1/web/portailClub` |
| n8n EACCES sur volume | Utiliser bind mount `./n8n_data:/data` + `chmod 777 n8n_data` + `N8N_USER_FOLDER=/data` |
| `500 Internal Server Error` | Souvent `git clone` échoué (dossier `/workspaces/MyDiveClub` sans `.git`) — corrigé par réinit workspace ; vérifier `docker logs cursor-skills-runner` |
| `git clone` exit 128 | Dossier cible déjà présent — le runner supprime et reclone automatiquement (v0.2+) |
| Suivi run en cours | `GET /api/v1/runs/{run_id}` ou `logs/runs/{run_id}.json` sur NAS |
| Timeout n8n | Boucle polling 30s × ~40 = 20 min max ; agent cloud 5–20 min |
| Pas de run 7h après import / restart | `staticData` schedule vide — relancer `bash scripts/import-n8n-workflow.sh` (unpublish → publish) |
| Manuel → branche **Expiré** avant le 14/07 | Expression date du nœud **Encore actif ?** non évaluée — réimporter le workflow corrigé |
| `410 job expiré` | Normal après le 14/07/2026 — vérifier `stop_after` dans jobs.json |
| `report_text` vide / n/d | Agent n'a pas émis `[CDM_STATS]` ou tokens non exposés par le SDK |
| E-mail non reçu | Credential **CDM Gmail SMTP** créé dans n8n ? Nœud **Envoyer CR par mail** relié ? Mot de passe d'application Gmail valide ? |

Logs :

```bash
docker compose logs skills-runner -f
docker compose logs n8n -f
```
