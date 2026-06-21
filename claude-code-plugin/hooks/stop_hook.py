#!/usr/bin/env python3
"""Claude Code Stop hook for toxi.

Peeks at unread messages after each Claude response. If any exist, prints a
one-line notification. Silent when there is nothing new.

Set TOXI_BIN if `toxi` isn't on PATH, and TOXI_HOME for a non-default config dir.
"""
import json
import os
import subprocess
import sys


def main() -> None:
    toxi = os.environ.get("TOXI_BIN", "toxi")
    try:
        out = subprocess.run(
            [toxi, "--json", "unread"], capture_output=True, text=True, timeout=8
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return
    if out.returncode != 0:
        return
    try:
        msgs = json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return
    if not msgs:
        return

    counts: dict[str, int] = {}
    media: dict[str, int] = {}
    emoji = {"image": "📷", "voice": "🎤", "video": "🎬", "file": "📎"}
    for m in msgs:
        counts[m["alias"]] = counts.get(m["alias"], 0) + 1
        t = m.get("msg_type", "text")
        if t in emoji:
            media[t] = media.get(t, 0) + 1
    summary = ", ".join(f"{alias}({n})" for alias, n in counts.items())
    line = f"[toxi] {len(msgs)} unread from {summary}"
    if media:
        line += " (" + " ".join(f"{emoji[t]}{n}" for t, n in media.items()) + ")"
    print(line + " — /toxi:read to read (keeps your main session clean)")


if __name__ == "__main__":
    main()
    sys.exit(0)
