#!/usr/bin/env python3
"""Send the current terminal's text to a toxi contact, split into Tox-sized messages.

Capture order: tmux pane (no manual copy) -> clipboard (pbpaste). The text is
chunked on UTF-8 character boundaries to stay under the daemon's per-message
limit, and each part is sent via `toxi send <alias> -`.

Usage: send_terminal.py <alias> [scrollback_lines]
"""
import json
import os
import shutil
import subprocess
import sys

# Per-message budget measured in JSON-ESCAPED bytes (the daemon encodes the body
# with json.dumps, so non-ASCII like Chinese or box-drawing chars cost ~6 bytes
# each, not their 3-byte UTF-8 size). The daemon caps the whole encoded envelope
# at 1372 bytes; ~112 of that is fixed overhead and a few more go to the [i/n]
# prefix, so 1180 of escaped body keeps every message comfortably under the cap.
BUDGET = 1180


def capture(lines):
    if os.environ.get("TMUX") and shutil.which("tmux"):
        cmd = ["tmux", "capture-pane", "-p"]
        if lines:
            cmd += ["-S", f"-{lines}"]
        text = subprocess.run(cmd, capture_output=True, text=True).stdout
    elif shutil.which("pbpaste"):
        text = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    else:
        return ""
    # Drop tmux's trailing line padding and surrounding blank lines.
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _esc_cost(ch):
    # Bytes this char adds to the JSON-encoded body (minus the two outer quotes).
    return len(json.dumps(ch)) - 2


def chunk(text, budget):
    parts, cur, cur_c = [], "", 0
    for ch in text:
        c = _esc_cost(ch)
        if cur and cur_c + c > budget:
            parts.append(cur)
            cur, cur_c = ch, c
        else:
            cur += ch
            cur_c += c
    if cur:
        parts.append(cur)
    return parts


def main():
    if len(sys.argv) < 2:
        print("usage: send_terminal.py <alias> [scrollback_lines]")
        sys.exit(2)
    alias = sys.argv[1]
    lines = sys.argv[2] if len(sys.argv) > 2 else None

    text = capture(lines)
    if not text:
        print("nothing to send — copy some terminal text first (or run inside tmux)")
        return

    parts = chunk(text, BUDGET)
    n = len(parts)
    toxi = shutil.which(os.environ.get("TOXI_BIN", "toxi")) or "toxi"

    for i, part in enumerate(parts, 1):
        body = f"[{i}/{n}] {part}" if n > 1 else part
        r = subprocess.run([toxi, "send", alias, "-"], input=body,
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"part {i}/{n} failed: {(r.stderr or r.stdout).strip()}")
            sys.exit(1)

    print(f"sent {n} message(s) to {alias} ({len(text.encode('utf-8'))} bytes total)")


if __name__ == "__main__":
    main()
