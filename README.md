<div align="center">

# SIM.lab

### Une simulation d'agents, de ressources, de climat et de civilisations émergentes.

**Observez un monde évoluer, apprendre, coopérer, se fragmenter et s'adapter.**

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

> Vous débutez ? Le plus simple est de commencer avec Docker. Aucune connaissance Python n'est nécessaire.

## Démarrage rapide

| Méthode | Pour qui ? | Commande principale |
|---|---|---|
| **Docker Compose** | Débutants | `docker compose up --build` |
| **Docker** | Utilisateurs Docker | `docker build -t simlab:local .` |
| **Python local** | Développeurs Python | `SIM_STATIC_ROOT=. SIM_DB_PATH=./sim.db python3 server.py` |
| **Kubernetes** | Homelab / cluster | voir [docs/KUBERNETES.md](docs/KUBERNETES.md) |

### Option recommandée : Docker Compose

```bash
git clone https://github.com/djayzone/simlab.git
cd simlab
docker compose up --build
```

Puis ouvrez :

**http://localhost:8080**

La base SQLite est conservée automatiquement dans un volume Docker nommé `simlab-data`.

## Docker

Guide détaillé, expliqué étape par étape :

**[docs/DOCKER.md](docs/DOCKER.md)**

En version courte :

```bash
docker build -t simlab:local .
docker run --rm -p 8080:8080 -v simlab-data:/data simlab:local
```

## Kubernetes

Un manifeste générique est fourni dans `deploy/kubernetes/`.

Pour tester localement avec **kind** :

```bash
docker build -t simlab:local .
kind create cluster --name simlab
kind load docker-image simlab:local --name simlab
kubectl apply -f deploy/kubernetes/
kubectl -n simlab port-forward svc/simlab 8080:8080
```

Puis ouvrez **http://localhost:8080**.

Le guide complet explique également comment utiliser votre propre registre d'images :

**[docs/KUBERNETES.md](docs/KUBERNETES.md)**

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

Supprimer la base revient à repartir avec un nouveau monde.

## Architecture

Les principales briques sont volontairement lisibles et accessibles :

- `engine.py` — état du monde et simulation principale ;
- `learning_engine.py` — apprentissage des agents ;
- `social_engine.py` — relations et dynamiques sociales ;
- `weather_engine.py` — climat ;
- `server.py` — serveur HTTP et interface ;
- `index.html`, `app.js`, `styles.css` — interface web ;
- `test_*.py` — tests automatisés.

## Documentation technique

- [Runtime](RUNTIME.md)
- [Schéma](SCHEMA.md)
- [Gameplay & équilibrage](GAMEPLAY_BALANCE.md)
- [Civilisation et dynamiques sociales](SOCIAL_CIVILIZATION.md)
- [Météo](WEATHER.md)
- [Contrôle météo](WEATHER_CONTROL.md)
- [Performance](PERFORMANCE.md)
- [Mécaniques](HOT_MECHANICS.md)

## Contribuer

Les améliorations de gameplay, performances, UX, documentation et architecture sont les bienvenues.

Voir **[CONTRIBUTING.md](CONTRIBUTING.md)**.

Les manifests Kubernetes historiques du homelab privé ne font volontairement pas partie de ce dépôt. Les exemples publics fournis ici sont génériques.

## Licence

MIT — voir [LICENSE](LICENSE).
