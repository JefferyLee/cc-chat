#!/usr/bin/env python3
"""Codex Stop hook for toxi.

Emits Codex Stop hook JSON with the current `toxi statusline` summary.
"""
import json
import os
import subprocess


def main() -> None:
    toxi = os.environ.get("TOXI_BIN", "toxi")
    try:
        out = subprocess.run(
            [toxi, "statusline"], capture_output=True, text=True, timeout=8
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return
    if out.returncode != 0:
        return
    status = out.stdout.strip()
    if status:
        print(
            json.dumps(
                {
                    "continue": True,
                    "suppressOutput": True,
                    "systemMessage": status,
                }
            )
        )


if __name__ == "__main__":
    main()
