# Publish a container image to GHCR

[🇬🇧 English](PUBLISHING.md) · [🇫🇷 Français](PUBLISHING.fr.md)

SIM.lab has **no automatic CI on push or pull requests**.

Container publishing is available only through a **manually triggered GitHub Actions workflow** or from your own machine.

## Recommended: GitHub UI

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Select **Publish Docker image to GHCR**.
4. Click **Run workflow**.
5. Enter the image tag, for example:
   - `latest`
   - `1.0.0`
   - `2026-10-03`
6. Confirm **Run workflow**.

The workflow runs only when explicitly started and publishes:

```text
ghcr.io/djayzone/simlab:<tag>
```

It uses the repository `GITHUB_TOKEN` with `packages: write`; no personal access token is stored in the repository.

> GitHub-hosted runner minutes are consumed only when this workflow is manually launched.

## First package publication

GHCR package visibility is separate from repository visibility. After the first push, check the package settings and set it to **Public** if anonymous pulls are desired.

## Pull the image

```bash
docker pull ghcr.io/djayzone/simlab:latest
```

Run it:

```bash
docker run --rm -p 8080:8080 -v simlab-data:/data ghcr.io/djayzone/simlab:latest
```

## Manual publishing from your own machine

You can still bypass GitHub Actions entirely:

```bash
docker login ghcr.io -u YOUR_GITHUB_USERNAME
docker build -t ghcr.io/djayzone/simlab:latest .
docker push ghcr.io/djayzone/simlab:latest
```
