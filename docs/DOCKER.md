# Run SIM.lab with Docker

[🇬🇧 English](DOCKER.md) · [🇫🇷 Français](DOCKER.fr.md)

This guide assumes no Python knowledge.

## 1. Install Docker

Install **Docker Desktop** on Windows/macOS or Docker Engine on Linux.

Check your installation:

```bash
docker --version
docker compose version
```

## 2. Download the project

```bash
git clone https://github.com/djayzone/simlab.git
cd simlab
```

## 3. Easiest method: Docker Compose

```bash
docker compose up --build
```

Open:

```text
http://localhost:8080
```

Stop the application:

```bash
docker compose down
```

Your world is preserved in the `simlab-data` Docker volume.

To remove the application **and all saved data**:

```bash
docker compose down -v
```

## 4. Plain Docker

Build:

```bash
docker build -t simlab:local .
```

Run:

```bash
docker run --name simlab -p 8080:8080 -v simlab-data:/data simlab:local
```

Open **http://localhost:8080**.

Stop:

```bash
docker stop simlab
```

Start again:

```bash
docker start simlab
```

## Health check

```bash
curl http://localhost:8080/healthz
```

Expected response:

```json
{"ok":true}
```

## Logs

Compose:

```bash
docker compose logs -f simlab
```

Docker:

```bash
docker logs -f simlab
```

## Use another host port

Example with port 9000:

```bash
docker run --rm -p 9000:8080 -v simlab-data:/data simlab:local
```

Then open **http://localhost:9000**.

## Update

```bash
git pull
docker compose up --build -d
```
