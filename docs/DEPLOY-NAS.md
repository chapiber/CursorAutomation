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

1. Ouvrir `http://<IP-NAS>:5678`
2. Créer un compte admin n8n (première visite)
3. **Workflows** → **Import from File** → `n8n/workflows/cdm2026-daily.json`
4. Vérifier que la variable d'environnement `RUNNER_API_KEY` est bien passée au conteneur n8n (déjà dans `docker-compose.yml`)
5. **Activer** le workflow (toggle en haut à droite)

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
```

## Dépannage

| Symptôme | Action |
|----------|--------|
| `401 X-API-Key invalide` | Aligner `RUNNER_API_KEY` dans `.env` et header n8n |
| Agent cloud échoue | Vérifier `CURSOR_API_KEY` et connexion GitHub Cursor |
| `git pull` échoue | Deploy key ou repo public |
| Deploy échoue | Vérifier permissions `/volume1/web/portailClub` |
| Timeout n8n | Le run agent peut durer 10–20 min ; timeout HTTP = 1200s |

Logs :

```bash
docker compose logs skills-runner -f
docker compose logs n8n -f
```
