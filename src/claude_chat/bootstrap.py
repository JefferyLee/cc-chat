"""Helpers for `cc-chat setup` / `teardown` / `upgrade`.

Pure helpers — no Click, no side effects on import. Filesystem touchers return
small status strings so the CLI can phrase its own output.
"""
import json
import os
import shutil
from pathlib import Path

from . import client, paths

STATUSLINE_CMD = "cc-chat statusline"


def claude_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _read_settings(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def _write_settings(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        shutil.copy2(p, p.with_suffix(".json.bak"))
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, p)


def ensure_statusline() -> str:
    """Wire cc-chat into ~/.claude/settings.json.

    Returns: "added" | "kept" | "left-custom".
    """
    p = claude_settings_path()
    data = _read_settings(p)
    sl = data.get("statusLine")
    if isinstance(sl, dict) and sl.get("command") == STATUSLINE_CMD:
        return "kept"
    if sl is not None:
        return "left-custom"
    data["statusLine"] = {"type": "command", "command": STATUSLINE_CMD}
    _write_settings(p, data)
    return "added"


def remove_statusline() -> str:
    """Reverse of ensure_statusline.

    Returns: "removed" | "absent" | "left-custom".
    """
    p = claude_settings_path()
    data = _read_settings(p)
    sl = data.get("statusLine")
    if sl is None:
        return "absent"
    if not (isinstance(sl, dict) and sl.get("command") == STATUSLINE_CMD):
        return "left-custom"
    del data["statusLine"]
    _write_settings(p, data)
    return "removed"


def identity_initialized() -> bool:
    return paths.tox_state_path().exists()


def daemon_running() -> bool:
    try:
        client.request("get_status")
        return True
    except client.DaemonNotRunning:
        return False
