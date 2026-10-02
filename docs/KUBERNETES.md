# Run SIM.lab on Kubernetes

[🇬🇧 English](KUBERNETES.md) · [🇫🇷 Français](KUBERNETES.fr.md)

This guide walks through a simple deployment. No Ingress is required to get started.

## What gets created

The manifest in `deploy/kubernetes/` creates:

- namespace `simlab`;
- one Deployment;
- one internal Service;
- one PersistentVolumeClaim for `sim.db`.

## Option A — local test with kind

### Requirements

Install Docker, `kubectl` and `kind`.

```bash
docker --version
kubectl version --client
kind version
```

### Build the image

```bash
docker build -t simlab:local .
```

### Create a local cluster

```bash
kind create cluster --name simlab
```

### Load the image into kind

```bash
kind load docker-image simlab:local --name simlab
```

### Deploy

```bash
kubectl apply -f deploy/kubernetes/
```

### Check the deployment

```bash
kubectl -n simlab get pods
kubectl -n simlab get svc
kubectl -n simlab get pvc
```

The pod should eventually reach `Running`.

### Open the application

```bash
kubectl -n simlab port-forward svc/simlab 8080:8080
```

Open **http://localhost:8080**.

## Option B — real Kubernetes cluster

Build and push the image to your registry:

```bash
docker build -t REGISTRY/USER/simlab:latest .
docker push REGISTRY/USER/simlab:latest
```

Edit `deploy/kubernetes/deployment.yaml` and replace:

```yaml
image: simlab:local
```

with:

```yaml
image: REGISTRY/USER/simlab:latest
```

Then:

```bash
kubectl apply -f deploy/kubernetes/
```

## Logs

```bash
kubectl -n simlab logs -f deployment/simlab
```

## Restart

```bash
kubectl -n simlab rollout restart deployment/simlab
```

## Remove

```bash
kubectl delete -f deploy/kubernetes/
```

Depending on your StorageClass and reclaim policy, deleting storage resources may also delete the SQLite database.

## Public exposure

Start with port-forwarding. For Internet exposure, add an Ingress compatible with your cluster and enable HTTPS.
