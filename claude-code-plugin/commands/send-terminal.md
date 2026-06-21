---
description: Send this terminal's text (tmux pane, else clipboard) to a toxi contact, auto-split into messages
allowed-tools: Bash(python3 *)
argument-hint: <alias> [scrollback_lines]
---

Capture this terminal's text and send it to the named contact, split into
Tox-sized messages. Uses the tmux pane when available (no manual copy), otherwise
the clipboard (`pbpaste` — copy the text first).

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/send_terminal.py" $ARGUMENTS`

Relay the result above to me concisely.
