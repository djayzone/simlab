<div align="center">

# SIM.lab

### An emergent simulation of agents, resources, climate and civilizations.

**Watch a world evolve, learn, cooperate, fragment and adapt.**

[🇬🇧 English](README.md) · [🇫🇷 Français](README.fr.md)

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Docker](https://img.shields.io/badge/docker-ready-2496ED)
![Kubernetes](https://img.shields.io/badge/kubernetes-ready-326CE5)
![Status](https://img.shields.io/badge/status-community--maintained-purple)

</div>

---

## About

**SIM.lab** is an experimental emergent simulation. Autonomous agents live in a shared world with resources, needs, social relationships, learning, climate events and civilization mechanics.

The project is no longer developed as an official first-party product, but it remains **open to forks, issues and pull requests**.

> New here? Start with Docker Compose. You do not need any Python knowledge.

## Quick start

| Method | Best for | Main command |
|---|---|---|
| **Docker Compose** | Beginners | `docker compose up --build` |
| **Docker** | Docker users | `docker build -t simlab:local .` |
| **Local Python** | Python developers | `SIM_STATIC_ROOT=. SIM_DB_PATH=./sim.db python3 server.py` |
| **Kubernetes** | Homelabs / clusters | see [docs/KUBERNETES.md](docs/KUBERNETES.md) |

### Recommended: Docker Compose

```bash
git clone https://github.com/djayzone/simlab.git
cd simlab
docker compose up --build
```

Then open **http://localhost:8080**.

The SQLite database is automatically persisted in a Docker volume named `simlab-data`.

## Docker

Step-by-step beginner guide:

**[docs/DOCKER.md](docs/DOCKER.md)**

Short version:

```bash
docker build -t simlab:local .
docker run --rm -p 8080:8080 -v simlab-data:/data simlab:local
```

## Kubernetes

A generic manifest is provided in `deploy/kubernetes/`.

Quick local test with **kind**:

```bash
docker build -t simlab:local .
kind create cluster --name simlab
kind load docker-image simlab:local --name simlab
kubectl apply -f deploy/kubernetes/
kubectl -n simlab port-forward svc/simlab 8080:8080
```

Then open **http://localhost:8080**.

Full Kubernetes guide:

**[docs/KUBERNETES.md](docs/KUBERNETES.md)**

## Local development

### Requirements

- Python 3.11 or newer

### Run

Linux/macOS:

```bash
SIM_STATIC_ROOT=. SIM_DB_PATH=./sim.db python3 server.py
```

PowerShell:

```powershell
$env:SIM_STATIC_ROOT="."
$env:SIM_DB_PATH="./sim.db"
python server.py
```

Then open **http://localhost:8080**.

### Tests

```bash
python3 -m unittest discover -p 'test_*.py'
```

## Persistence

SIM.lab uses SQLite.

| Environment | Location |
|---|---|
| Docker | `/data/sim.db` in the `simlab-data` volume |
| Kubernetes | `/data/sim.db` on a PersistentVolumeClaim |
| Local | configurable with `SIM_DB_PATH` |

Deleting the database starts a fresh world.

## Architecture

The main building blocks are intentionally straightforward:

- `engine.py` — world state and main simulation loop;
- `learning_engine.py` — agent learning;
- `social_engine.py` — relationships and social dynamics;
- `weather_engine.py` — climate;
- `server.py` — HTTP server and web interface;
- `index.html`, `app.js`, `styles.css` — frontend;
- `test_*.py` — automated tests.

## Technical documentation

- [Runtime](RUNTIME.md)
- [Schema](SCHEMA.md)
- [Gameplay & balancing](GAMEPLAY_BALANCE.md)
- [Civilization & social dynamics](SOCIAL_CIVILIZATION.md)
- [Weather](WEATHER.md)
- [Weather control](WEATHER_CONTROL.md)
- [Performance](PERFORMANCE.md)
- [Mechanics](HOT_MECHANICS.md)

## Community roadmap

See **[ROADMAP.md](ROADMAP.md)** for starter tasks, larger ideas and current limitations.

### Helm

Advanced Kubernetes users can also use the optional Helm chart:

```bash
helm install simlab ./deploy/helm/simlab --namespace simlab --create-namespace
```

The plain Kubernetes YAML remains the recommended learning path for beginners.

### Publishing container images without CI

See **[docs/PUBLISHING.md](docs/PUBLISHING.md)** to publish a GHCR image through a manually triggered GitHub workflow (or directly from your own machine).

## Contributing

Gameplay, performance, UX, documentation and architecture improvements are welcome.

See **[CONTRIBUTING.md](CONTRIBUTING.md)**. Bug reports, feature requests and documentation requests have dedicated GitHub issue forms.

Historical Kubernetes manifests from the original private homelab are intentionally not included. The public deployment examples in this repository are generic.

## License

MIT — see [LICENSE](LICENSE).
