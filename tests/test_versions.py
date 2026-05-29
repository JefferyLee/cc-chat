"""Version metadata should move together across engine and bundled plugins."""
import json
import tomllib
from pathlib import Path

import toxi


ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_engine_and_plugin_versions_match_pyproject():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    version = project["version"]

    assert toxi.__version__ == version
    assert _json(ROOT / "claude-code-plugin" / ".claude-plugin" / "plugin.json")["version"] == version
    assert _json(ROOT / "plugins" / "toxi" / ".codex-plugin" / "plugin.json")["version"] == version
