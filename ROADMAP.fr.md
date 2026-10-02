# Roadmap communautaire

[🇬🇧 English](ROADMAP.md) · [🇫🇷 Français](ROADMAP.fr.md)

SIM.lab est maintenu par la communauté. Cette roadmap présente des pistes utiles et ne constitue pas une promesse de livraison.

## Premières contributions

- Ajouter de vraies captures d'écran ou un GIF de la simulation au README.
- Améliorer la documentation débutant et le dépannage.
- Ajouter des presets de simulation.
- Améliorer l'accessibilité et le responsive de l'interface.
- Ajouter des tests unitaires ciblés.

## Améliorations plus importantes

- Export/import et sauvegarde du monde.
- Profilage des performances avec de grandes populations.
- Meilleure visualisation du raisonnement et de l'apprentissage des agents.
- Visualisation des groupes sociaux et des évolutions de civilisation.
- Nouveaux événements météo/environnement.
- Configuration optionnelle par variables d'environnement ou fichier.

## Déploiement

Docker Compose et des manifests Kubernetes génériques sont fournis. Un chart Helm optionnel est disponible dans `deploy/helm/simlab`.

## Non-objectifs

- Réintroduire la configuration du homelab privé.
- Imposer un cloud particulier.
- Lancer de la CI automatiquement sur les push ou pull requests. Le seul workflow GitHub Actions est la publication manuelle d'une image.

## Participer

Cherchez les issues `good first issue` ou `help wanted`, ou ouvrez une feature request avant un gros changement.
