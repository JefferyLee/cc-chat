#!/usr/bin/env python3
"""Claude Code Stop hook for cc-chat.

Peeks at unread messages after each Claude response. If any exist, prints a
one-line notification. Silent when there is nothing new.

Set CHAT_BIN if `cc-chat` isn't on PATH, and CLAUDE_CHAT_HOME for a
non-default config dir.
"""
import json
import os
import subprocess
import sys


def main() -> None:
    chat = os.environ.get("CHAT_BIN", "cc-chat")
    try:
        out = subprocess.run(
            [chat, "--json", "unread"], capture_output=True, text=True, timeout=8
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
    for m in msgs:
        counts[m["alias"]] = counts.get(m["alias"], 0) + 1
    summary = ", ".join(f"{alias}({n})" for alias, n in counts.items())
    print(f"[cc-chat] {len(msgs)} unread from {summary} — /cc-chat:unread to read")


if __name__ == "__main__":
    main()
    sys.exit(0)
