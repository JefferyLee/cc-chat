#!/usr/bin/env python3
"""Codex Stop hook for toxi.

Emits Codex hook JSON with the same statusline-style summary that Claude Code
shows in its bottom bar. It stays silent when `toxi statusline` cannot run.
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
                    "hookSpecificOutput": {
                        "hookEventName": "Stop",
                        "additionalContext": status,
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
