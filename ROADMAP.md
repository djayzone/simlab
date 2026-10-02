# Community roadmap

[🇬🇧 English](ROADMAP.md) · [🇫🇷 Français](ROADMAP.fr.md)

SIM.lab is community-maintained. This roadmap is intentionally a list of useful directions rather than a delivery promise.

## Good first contributions

- Add real screenshots or a short GIF of the running simulation to the README.
- Improve beginner documentation and troubleshooting.
- Add simulation presets that demonstrate different starting conditions.
- Improve accessibility and responsive behavior of the web interface.
- Add more focused unit tests around isolated mechanics.

## Larger improvements

- Better world export/import and backup workflows.
- Performance profiling for larger populations.
- More observable agent reasoning and learning history.
- Better visualization of social groups and civilization changes.
- Additional weather and environment events.
- Optional configuration through environment variables or a config file.

## Deployment

Docker Compose and generic Kubernetes manifests are provided.

A Helm chart is available under `deploy/helm/simlab`. It is intentionally optional so Kubernetes beginners can continue to use the plain YAML manifest.

## Non-goals

- Reintroducing private homelab infrastructure configuration.
- Requiring a specific cloud provider.
- Running CI automatically on pushes or pull requests. The only GitHub Actions workflow is an explicit manual container-image publication.

## How to help

Look for issues labeled `good first issue` or `help wanted`, or open a feature request before starting a large change.
