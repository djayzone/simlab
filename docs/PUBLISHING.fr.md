# Publication manuelle d'une image conteneur (GHCR)

SIM.lab ne fournit volontairement **aucun workflow GitHub Actions automatique** pour publier les images.

Cela permet de ne consommer aucune minute de CI du dépôt.

## Publier manuellement

Connexion à GitHub Container Registry :

```bash
docker login ghcr.io -u VOTRE_UTILISATEUR_GITHUB
```

Construction et tag :

```bash
docker build -t ghcr.io/djayzone/simlab:latest .
```

Publication :

```bash
docker push ghcr.io/djayzone/simlab:latest
```

Pour une version :

```bash
docker build -t ghcr.io/djayzone/simlab:1.0.0 .
docker push ghcr.io/djayzone/simlab:1.0.0
```

Après le premier push, passez la visibilité du package à **Public** dans GitHub Packages si vous souhaitez autoriser les pulls anonymes.

## Utiliser l'image

```bash
docker run --rm -p 8080:8080 -v simlab-data:/data ghcr.io/djayzone/simlab:latest
```

Pour Kubernetes ou Helm, utilisez `ghcr.io/djayzone/simlab` comme repository d'image.
