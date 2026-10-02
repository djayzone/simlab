# SimLab

SimLab is an experimental simulation of agents, resources, climate, social structures and emergent civilization mechanics.

This repository is now maintained as a public community project. The original maintainer no longer operates it as an actively developed first-party product, but forks, issues and pull requests are welcome.

## Requirements

- Python 3.11+ recommended
- No external Python package is required for the core runtime

## Run locally

```bash
python3 server.py
```

## Tests

```bash
python3 -m unittest discover -p 'test_*.py'
```

## Documentation

- `RUNTIME.md`
- `SCHEMA.md`
- `GAMEPLAY_BALANCE.md`
- `SOCIAL_CIVILIZATION.md`
- `WEATHER.md`
- `WEATHER_CONTROL.md`
- `PERFORMANCE.md`
- `HOT_MECHANICS.md`

Environment-specific Kubernetes/GitOps manifests from the original private homelab were intentionally excluded.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT.
