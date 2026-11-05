"""README badges point at things that exist (workflows, LICENSE, the PyPI name)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / 'readme.md').read_text()


def test_each_build_badge_points_at_an_existing_workflow():
    workflows = re.findall(r'actions/workflows/([\w.-]+\.yml)/badge\.svg', README)
    assert workflows
    for wf in workflows:
        assert (ROOT / '.github' / 'workflows' / wf).is_file(), wf


def test_every_workflow_has_a_badge():
    shown = set(re.findall(r'actions/workflows/([\w.-]+\.yml)/badge\.svg', README))
    assert {p.name for p in (ROOT / '.github' / 'workflows').glob('*.yml')} <= shown


def test_pypi_badge_matches_the_package_name():
    name = re.search(r'^name = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(), re.M).group(1)
    assert f'img.shields.io/pypi/v/{name})' in README


def test_license_badge_links_to_the_license_file():
    assert '](LICENSE)' in README and (ROOT / 'LICENSE').is_file()
