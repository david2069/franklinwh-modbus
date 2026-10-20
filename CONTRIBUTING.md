# Contributing to franklinwh-modbus

Thank you for your interest in contributing! This project provides Modbus TCP control for FranklinWH battery storage systems and benefits greatly from community contributions.

## Getting Started

### Prerequisites

- Python 3.10+
- A FranklinWH aGate gateway on your LAN (for hardware testing)
- Git

### Development Setup

```bash
git clone git@github.com:david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Unit tests (no hardware required)
python3 -m pytest tests/unit/ -v

# Integration tests (no hardware required)
python3 -m pytest tests/integration/ -v

# Hardware tests (requires aGate on LAN)
python3 -m pytest tests/hardware/ -v --ip YOUR_AGATE_IP
```

## How to Contribute

### Reporting Bugs

- Use the [Bug Report](https://github.com/david2069/franklinwh-modbus/issues/new?template=bug_report.md) template
- Include your aGate firmware version (`--status` output shows this)
- Include the exact command and full error output
- If the bug involves extension register writes (15507–15509), include the read-back result the setter returned

### Suggesting Features

- Use the [Feature Request](https://github.com/david2069/franklinwh-modbus/issues/new?template=feature_request.md) template
- Describe the use case and expected behavior

### Pull Requests

1. Fork the repo and create your branch from `develop`
2. Add or update tests for any new functionality
3. Ensure all tests pass: `python3 -m pytest tests/ -v`
4. Update documentation if you change public APIs
5. **Add a changelog entry** under `[Unreleased]` in [CHANGELOG.md](./CHANGELOG.md)
6. Submit a PR with a clear description of the change

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) prefixes:

| Prefix | Use For |
|--------|---------|
| `feat:` | New feature or capability |
| `fix:` | Bug fix |
| `doc:` | Documentation only |
| `test:` | Adding or updating tests |
| `chore:` | Build, CI, tooling changes |
| `refactor:` | Code restructuring (no behavior change) |

Example: `fix: CRITICAL - WSetPct used wrong denominator (WMaxRtg vs charge rate)`

### Code Style

- Follow PEP 8 for Python code
- Use type hints where practical
- Add docstrings to public methods
- Keep log messages informative but concise

### Hardware Testing

Many features interact with real hardware. If you don't have an aGate:

- Unit tests with mocks cover most logic
- Clearly mark hardware-dependent changes in your PR
- A maintainer with hardware will validate before merging

## Changelog Policy

This project maintains a [CHANGELOG.md](./CHANGELOG.md) following the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

**Every PR must include a changelog entry.** Add your change under the `[Unreleased]` section in the appropriate category:

| Category | Use For |
|----------|---------|
| `Added` | New features, new tools, new docs |
| `Changed` | Changes to existing functionality |
| `Deprecated` | Features that will be removed in future |
| `Removed` | Features removed in this release |
| `Fixed` | Bug fixes |
| `Security` | Vulnerability fixes |

PRs without a changelog entry will be asked to add one before merging.

## Release Process

When cutting a release:

1. Move `[Unreleased]` entries to a new version heading: `## [X.Y.Z] - YYYY-MM-DD`
2. Update version in `setup.py`
3. Add comparison link at bottom of CHANGELOG.md
4. Tag the release: `git tag vX.Y.Z`
5. Push tag: `git push origin vX.Y.Z`

Versioning follows [Semantic Versioning](https://semver.org/):
- **MAJOR** — breaking API changes
- **MINOR** — new features, backward-compatible
- **PATCH** — bug fixes, backward-compatible

## Project Structure

```
src/franklinwh_modbus/     # Core library (the pip package)
tools/                     # CLI tools and utilities
tests/unit/                # Unit tests (mocked, no hardware)
tests/integration/         # Integration tests
tests/hardware/            # Live hardware tests
docs/                      # Documentation
schedules/                 # TOU schedule examples
```

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](./LICENSE).
