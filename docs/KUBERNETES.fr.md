# Lancer SIM.lab sur Kubernetes

[🇬🇧 English](KUBERNETES.md) · [🇫🇷 Français](KUBERNETES.fr.md)

Ce guide explique une installation simple. Aucun Ingress n'est nécessaire pour commencer.

## Ce qui sera créé

Le dossier `deploy/kubernetes/` crée :

- un namespace `simlab` ;
- un Deployment ;
- un Service interne ;
- un PersistentVolumeClaim pour conserver `sim.db`.

## Option A — tester localement avec kind

Installez Docker, `kubectl` et `kind`.

```bash
docker build -t simlab:local .
kind create cluster --name simlab
kind load docker-image simlab:local --name simlab
kubectl apply -f deploy/kubernetes/
kubectl -n simlab get pods
kubectl -n simlab port-forward svc/simlab 8080:8080
```

Puis ouvrez **http://localhost:8080**.

## Option B — vrai cluster Kubernetes

```bash
docker build -t REGISTRY/UTILISATEUR/simlab:latest .
docker push REGISTRY/UTILISATEUR/simlab:latest
```

Remplacez ensuite `image: simlab:local` dans `deploy/kubernetes/deployment.yaml` par votre image, puis :

```bash
kubectl apply -f deploy/kubernetes/
```

## Logs

```bash
kubectl -n simlab logs -f deployment/simlab
```

## Redémarrer

```bash
kubectl -n simlab rollout restart deployment/simlab
```

## Supprimer

```bash
kubectl delete -f deploy/kubernetes/
```

Pour une exposition Internet, ajoutez un Ingress adapté à votre cluster avec HTTPS.
