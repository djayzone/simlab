# Manual container publishing (GHCR)

SIM.lab intentionally does **not** ship an automatic GitHub Actions publishing workflow.

This keeps repository CI usage at zero unless a maintainer explicitly chooses to publish an image from their own machine.

## Publish manually

Authenticate to GitHub Container Registry:

```bash
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Build and tag the image:

```bash
docker build -t ghcr.io/djayzone/simlab:latest .
```

Push it:

```bash
docker push ghcr.io/djayzone/simlab:latest
```

For a versioned release:

```bash
docker build -t ghcr.io/djayzone/simlab:1.0.0 .
docker push ghcr.io/djayzone/simlab:1.0.0
```

After the first push, make sure the package visibility is set to **Public** in GitHub Packages if you want anonymous pulls.

## Use the published image

```bash
docker run --rm -p 8080:8080 -v simlab-data:/data ghcr.io/djayzone/simlab:latest
```

For Kubernetes or Helm, set the image repository to `ghcr.io/djayzone/simlab`.
