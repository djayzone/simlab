# Lancer SIM.lab avec Docker

[🇬🇧 English](DOCKER.md) · [🇫🇷 Français](DOCKER.fr.md)

Ce guide ne suppose aucune connaissance de Python.

## 1. Installer Docker

Installez **Docker Desktop** sur Windows/macOS ou Docker Engine sur Linux.

Vérifiez ensuite :

```bash
docker --version
docker compose version
```

## 2. Télécharger le projet

```bash
git clone https://github.com/djayzone/simlab.git
cd simlab
```

## 3. Méthode la plus simple : Docker Compose

```bash
docker compose up --build
```

Ouvrez **http://localhost:8080**.

Pour arrêter :

```bash
docker compose down
```

Votre monde reste dans le volume Docker `simlab-data`.

Pour supprimer également les données :

```bash
docker compose down -v
```

## 4. Docker classique

```bash
docker build -t simlab:local .
docker run --name simlab -p 8080:8080 -v simlab-data:/data simlab:local
```

## Vérifier le service

```bash
curl http://localhost:8080/healthz
```

Réponse attendue :

```json
{"ok":true}
```

## Logs

```bash
docker compose logs -f simlab
```

## Changer le port

```bash
docker run --rm -p 9000:8080 -v simlab-data:/data simlab:local
```

Puis ouvrez **http://localhost:9000**.

## Mettre à jour

```bash
git pull
docker compose up --build -d
```
