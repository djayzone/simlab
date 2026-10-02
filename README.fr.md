<div align="center">

# SIM.lab

### Une simulation d'agents, de ressources, de climat et de civilisations émergentes.

**Observez un monde évoluer, apprendre, coopérer, se fragmenter et s'adapter.**

[🇬🇧 English](README.md) · [🇫🇷 Français](README.fr.md)

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Docker](https://img.shields.io/badge/docker-ready-2496ED)
![Kubernetes](https://img.shields.io/badge/kubernetes-ready-326CE5)
![Status](https://img.shields.io/badge/status-community--maintained-purple)

</div>

---

## À propos

**SIM.lab** est un prototype de simulation émergente. Des agents autonomes évoluent dans un monde partagé avec des ressources, des besoins, des relations sociales, des apprentissages, des événements climatiques et des mécanismes de civilisation.

Le projet n'est plus développé comme produit officiel par son créateur, mais il reste **ouvert aux forks, issues et pull requests**.

> Vous débutez ? Le plus simple est de commencer avec Docker Compose. Aucune connaissance Python n'est nécessaire.

## Démarrage rapide

| Méthode | Pour qui ? | Commande principale |
|---|---|---|
| **Docker Compose** | Débutants | `docker compose up --build` |
| **Docker** | Utilisateurs Docker | `docker build -t simlab:local .` |
| **Python local** | Développeurs Python | `SIM_STATIC_ROOT=. SIM_DB_PATH=./sim.db python3 server.py` |
| **Kubernetes** | Homelab / cluster | voir [docs/KUBERNETES.fr.md](docs/KUBERNETES.fr.md) |

### Option recommandée : Docker Compose

```bash
git clone https://github.com/djayzone/simlab.git
cd simlab
docker compose up --build
```

Puis ouvrez **http://localhost:8080**.

La base SQLite est conservée automatiquement dans un volume Docker nommé `simlab-data`.

## Docker

Guide détaillé : **[docs/DOCKER.fr.md](docs/DOCKER.fr.md)**

## Kubernetes

Guide détaillé : **[docs/KUBERNETES.fr.md](docs/KUBERNETES.fr.md)**

## Développement local

### Prérequis

- Python 3.11 ou supérieur

### Lancement

Linux/macOS :

```bash
SIM_STATIC_ROOT=. SIM_DB_PATH=./sim.db python3 server.py
```

PowerShell :

```powershell
$env:SIM_STATIC_ROOT="."
$env:SIM_DB_PATH="./sim.db"
python server.py
```

Puis ouvrez **http://localhost:8080**.

### Tests

```bash
python3 -m unittest discover -p 'test_*.py'
```

## Persistance

SIM.lab utilise SQLite.

| Environnement | Emplacement |
|---|---|
| Docker | `/data/sim.db` dans le volume `simlab-data` |
| Kubernetes | `/data/sim.db` sur un PersistentVolumeClaim |
| Local | configurable avec `SIM_DB_PATH` |

## Architecture

- `engine.py` — état du monde et simulation principale ;
- `learning_engine.py` — apprentissage des agents ;
- `social_engine.py` — relations et dynamiques sociales ;
- `weather_engine.py` — climat ;
- `server.py` — serveur HTTP et interface ;
- `index.html`, `app.js`, `styles.css` — interface web ;
- `test_*.py` — tests automatisés.

## Contribuer

Voir **[CONTRIBUTING.md](CONTRIBUTING.md)**.

## Licence

MIT — voir [LICENSE](LICENSE).
