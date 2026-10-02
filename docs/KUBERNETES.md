# Lancer SIM.lab sur Kubernetes

Ce guide explique une installation simple. Aucun Ingress n'est nécessaire pour commencer.

## Ce qui sera créé

Le dossier `deploy/kubernetes/` crée :

- un namespace `simlab` ;
- un Deployment avec un pod SIM.lab ;
- un Service interne ;
- un PersistentVolumeClaim pour conserver `sim.db`.

## Option A — tester localement avec kind

### 1. Prérequis

Installez :

- Docker ;
- `kubectl` ;
- `kind`.

Vérifiez :

```bash
docker --version
kubectl version --client
kind version
```

### 2. Construire l'image

Depuis la racine du dépôt :

```bash
docker build -t simlab:local .
```

### 3. Créer un cluster local

```bash
kind create cluster --name simlab
```

### 4. Charger l'image Docker dans kind

```bash
kind load docker-image simlab:local --name simlab
```

### 5. Déployer

```bash
kubectl apply -f deploy/kubernetes/
```

### 6. Vérifier

```bash
kubectl -n simlab get pods
kubectl -n simlab get svc
kubectl -n simlab get pvc
```

Le pod doit finir en état `Running`.

### 7. Ouvrir l'application

```bash
kubectl -n simlab port-forward svc/simlab 8080:8080
```

Ouvrez ensuite :

```text
http://localhost:8080
```

## Option B — utiliser un vrai cluster

Construisez l'image et poussez-la dans votre registre :

```bash
docker build -t REGISTRY/UTILISATEUR/simlab:latest .
docker push REGISTRY/UTILISATEUR/simlab:latest
```

Éditez ensuite `deploy/kubernetes/deployment.yaml` et remplacez :

```yaml
image: simlab:local
```

par votre image :

```yaml
image: REGISTRY/UTILISATEUR/simlab:latest
```

Puis :

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

## Supprimer l'application

```bash
kubectl delete -f deploy/kubernetes/
```

Attention : selon votre StorageClass, la suppression du PVC peut supprimer la base SQLite.

## Exposer publiquement

Pour un premier test, utilisez `kubectl port-forward`.

Pour une exposition Internet, ajoutez ensuite un Ingress adapté à votre contrôleur (Traefik, NGINX, etc.) et un certificat TLS. Cet élément dépend du cluster et n'est donc volontairement pas imposé dans le manifeste générique.
