# Publier une image conteneur sur GHCR

[🇬🇧 English](PUBLISHING.md) · [🇫🇷 Français](PUBLISHING.fr.md)

SIM.lab n'a **aucune CI automatique sur les push ou pull requests**.

La publication d'une image est disponible uniquement via un workflow GitHub Actions **déclenché manuellement**, ou depuis votre propre machine.

## Méthode recommandée : interface GitHub

1. Ouvrez le dépôt sur GitHub.
2. Allez dans **Actions**.
3. Sélectionnez **Publish Docker image to GHCR**.
4. Cliquez sur **Run workflow**.
5. Saisissez le tag, par exemple :
   - `latest`
   - `1.0.0`
   - `2026-10-03`
6. Confirmez avec **Run workflow**.

L'image publiée sera :

```text
ghcr.io/djayzone/simlab:<tag>
```

Le workflow utilise le `GITHUB_TOKEN` du dépôt avec le droit `packages: write`. Aucun token personnel n'est stocké dans le repo.

> Les minutes GitHub Actions ne sont consommées que lorsque ce workflow est lancé manuellement.

## Première publication

La visibilité d'un package GHCR est indépendante de celle du dépôt. Après le premier push, vérifiez les paramètres du package et passez-le en **Public** si vous souhaitez permettre les pulls anonymes.

## Utiliser l'image

```bash
docker pull ghcr.io/djayzone/simlab:latest
docker run --rm -p 8080:8080 -v simlab-data:/data ghcr.io/djayzone/simlab:latest
```

## Publication depuis votre propre machine

```bash
docker login ghcr.io -u VOTRE_UTILISATEUR_GITHUB
docker build -t ghcr.io/djayzone/simlab:latest .
docker push ghcr.io/djayzone/simlab:latest
```
