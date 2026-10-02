# Contribuer

[🇬🇧 English](CONTRIBUTING.md) · [🇫🇷 Français](CONTRIBUTING.fr.md)

Les contributions sont les bienvenues.

## Avant de commencer

Pour une modification importante, ouvrez d'abord une feature request afin de cadrer le besoin avant l'implémentation.

Repérez notamment les labels :

- `good first issue` pour les premières contributions ;
- `help wanted` pour les sujets ouverts à la communauté ;
- `documentation` pour l'onboarding et les traductions.

## Workflow de contribution

1. Forkez le dépôt.
2. Créez une branche dédiée.
3. Faites votre modification.
4. Lancez les tests concernés localement.
5. Ouvrez une pull request en expliquant le changement et les vérifications réalisées.

## Vérifications locales

Pour SIM.lab :

```bash
python3 -m unittest discover -p 'test_*.py'
```

Si votre changement touche Docker :

```bash
docker build -t simlab:local .
docker run --rm -p 8080:8080 -v simlab-data:/data simlab:local
curl http://localhost:8080/healthz
```

## Politique GitHub Actions

Le dépôt n'exécute volontairement **aucune CI automatique sur les push ou pull requests**.

Le seul workflow GitHub Actions est :

```text
Publish Docker image to GHCR
```

Il est déclenché uniquement manuellement avec `workflow_dispatch` afin de construire et publier une image dans GHCR.

Ce workflow **ne constitue pas une validation automatique des pull requests**.

Lancement :

```text
GitHub → Actions → Publish Docker image to GHCR → Run workflow
```

Voir [docs/PUBLISHING.fr.md](docs/PUBLISHING.fr.md).

## Sécurité

Ne versionnez jamais :

- identifiants ou tokens ;
- endpoints d'infrastructure privés ;
- noms DNS internes ;
- secrets ;
- configuration Kubernetes/GitOps du homelab d'origine.

Les exemples publics doivent rester génériques et portables.

## Pull requests

Gardez les PR ciblées et précisez :

- ce qui change ;
- pourquoi ;
- comment le changement a été testé ;
- les limitations connues.

Les captures sont recommandées pour les modifications d'interface.
