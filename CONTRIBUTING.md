# Contributing

[🇬🇧 English](CONTRIBUTING.md) · [🇫🇷 Français](CONTRIBUTING.fr.md)

Contributions are welcome.

## Before you start

For larger changes, open a feature request first so the scope can be discussed before implementation.

Look for:

- `good first issue` for beginner-friendly tasks;
- `help wanted` for community-owned improvements;
- `documentation` for onboarding and translation work.

## Development flow

1. Fork the repository.
2. Create a focused branch.
3. Make your change.
4. Run the relevant tests locally.
5. Open a pull request explaining the change and how it was tested.

## Local checks

For SIM.lab:

```bash
python3 -m unittest discover -p 'test_*.py'
```

If your change affects Docker:

```bash
docker build -t simlab:local .
docker run --rm -p 8080:8080 -v simlab-data:/data simlab:local
```

Then verify:

```bash
curl http://localhost:8080/healthz
```

## GitHub Actions policy

This repository intentionally has **no automatic CI on push or pull requests**.

The only GitHub Actions workflow is:

```text
Publish Docker image to GHCR
```

It is triggered manually with `workflow_dispatch` and is used only to build and publish a container image to GHCR.

It is **not** a pull-request validation pipeline.

Maintainers can launch it from:

```text
GitHub → Actions → Publish Docker image to GHCR → Run workflow
```

See [docs/PUBLISHING.md](docs/PUBLISHING.md).

## Security and repository hygiene

Do not commit:

- credentials or tokens;
- private infrastructure endpoints;
- internal DNS names;
- secrets;
- private Kubernetes/GitOps configuration from the original homelab.

Public deployment examples must remain generic and portable.

## Pull requests

Keep pull requests focused and describe:

- what changed;
- why;
- how you tested it;
- any known limitations.

Screenshots are encouraged for UI changes.
