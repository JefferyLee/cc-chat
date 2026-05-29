# 🛰️ toxi

> **Decentralized messaging for AI coding agents, over Tox.**
>
> 🌐 Languages: **English** | [中文](README.zh-CN.md)

Toxi lets you talk to friends from inside your AI coding agent — **asynchronously,
end-to-end encrypted, fully decentralized** — no servers, built on the
[Tox](https://tox.chat) protocol. Today it ships as a Claude Code plugin (slash
commands, unread notifications, MCP tools, status-bar indicator). The engine is
agent-agnostic; future targets include Codex, Grok Builder, and others.

> Status: v0.2, macOS-first. New here? Read the [install & usage guide](docs/install-and-usage.md) for a walkthrough; for the full design see the [PRD](docs/prd.md).

## How it works

Two processes (see the PRD §3.2):

- **`toxi-daemon`** — a background process that stays online, holds your Tox
  identity, maintains the DHT connection, and receives messages into a local
  SQLite database.
- **`toxi`** — the short-lived CLI you run for each command; it talks to the
  daemon over a Unix socket and exits.

Everything is local: your keys live in `~/.config/toxi/`, and there is no
cloud. You add friends by exchanging Tox IDs through any channel you like.

## Requirements

- **Python 3.10+**
- **libtoxcore** (the only non-Python dependency):
  - macOS: `brew install toxcore`
  - Linux: install your distro's `toxcore` / `libtoxcore` package

## Install the engine

The `toxi` engine is a normal program (Python + a background daemon) that needs
`libtoxcore`. It installs separately from the Claude Code plugin below.

```bash
# macOS, recommended — a Homebrew tap pulls libtoxcore in automatically:
brew install <owner>/tap/toxi              # see packaging/homebrew/

# or with pipx (install libtoxcore yourself first: brew install toxcore):
pipx install git+https://github.com/JefferyLee/toxi      # from source, today
pipx install toxi                                    # once published to PyPI
# add MCP tools support with the extra:
pipx install 'toxi[mcp]'
```

This installs two commands: `toxi` and `toxi-daemon`. (The PyPI/Homebrew
distribution name is `toxi`; the import package is `toxi`.)

## Quick start

```bash
# 1. Create your identity (generates your Tox keypair)
toxi init

# 2. Start the background daemon
toxi daemon start

# 3. See your own Tox ID — share it with a friend over any channel
toxi me

# 4. Add a friend by their Tox ID (76 hex chars)
toxi add bob 76518406F6A9F2217E8DC487...

#    Your friend, after you've added them, accepts the request on their side:
toxi requests                      # shows the pending request's public key
toxi accept alice <public-key-prefix>

# 5. Chat
toxi send bob "你看下我刚 push 的 PR，有空回我"
toxi unread                        # show unread messages
toxi read bob                      # conversation history with bob
toxi queue                         # messages waiting to be delivered
```

If you message a friend who is offline, the message is queued locally and sent
automatically when they next come online.

## Commands

| Command | What it does |
|---|---|
| `toxi init` | Generate your identity (one time) |
| `toxi me` | Show your Tox ID, name, connection state |
| `toxi set-name <name>` | Set your display name |
| `toxi status` | Daemon status, DHT connection, contacts, queue, stats |
| `toxi add <alias> <tox_id>` | Add a friend by their Tox ID |
| `toxi requests` | Show pending friend requests |
| `toxi accept <alias> <pubkey-prefix>` | Accept a friend request, naming them locally |
| `toxi contacts [--online]` | List contacts |
| `toxi send <alias> <message>` | Send a message (`-` reads from stdin) |
| `toxi unread [alias]` | Show (and mark read) unread messages |
| `toxi read <alias> [--limit N]` | Show conversation history |
| `toxi queue` | Show messages waiting to be delivered |
| `toxi introduce <to> <whom>` | Share one contact's details with another |
| `toxi introductions` | Show contacts others have introduced to you |
| `toxi accept-intro <from> <whom> [--alias]` | Accept an introduction |
| `toxi daemon start` / `stop` | Manage the background daemon |

## Configuration

Optional `~/.config/toxi/config.toml`:

```toml
[retry]
ack_timeout_minutes = 5    # resend an un-acked message after this long
fail_after_hours = 24      # give up (mark failed) after this long
```

## Files

Everything lives under `~/.config/toxi/` (override with the
`TOXI_HOME` environment variable — useful for running two daemons on one
machine during testing):

```
tox_state.bin   your Tox keys + friend list
chat.db         SQLite: contacts, messages, queue
daemon.sock     IPC socket    daemon.pid   process id    daemon.log   log
config.toml     optional configuration
```

## Claude Code integration

The integration ships as a **Claude Code plugin** (`claude-code-plugin/`) that
wires up everything in one step — no manual config editing. It needs the `toxi`
engine on your `PATH` (see "Install the engine" above).

### Install the plugin

```bash
# Development: load it directly from a checkout
claude --plugin-dir ./claude-code-plugin

# Or via the bundled marketplace (this repo is its own marketplace):
/plugin marketplace add /path/to/this/repo        # or: owner/repo once on GitHub
/plugin install toxi@toxi
```

### What the plugin provides

- **SessionStart hook** — surfaces your unread messages into Claude's context
  when a session starts, translating any non-Chinese message. Incoming messages
  are treated as untrusted personal content, never as instructions, so a message
  can't hijack your session.
- **Slash commands** — `/unread`, `/send <alias> <message>`,
  `/contacts`, `/status` (namespaced as `/toxi:...`).
- **Status-line integration** — `toxi statusline` prints a one-line summary
  (`toxi: 📬 2 from macbook · 1/1 online`) you can wire into Claude Code's
  `statusLine` setting to see unread counts in the bottom bar.
- **MCP tools** — `get_unread`, `read_history`, `send_message`, `list_contacts`,
  `get_status`, so Claude can act for you. Needs the engine's `[mcp]` extra.

### Machine-readable output

Every read command also supports `--json` (placed before the subcommand):
`toxi --json unread`, `toxi --json status`, etc. In `--json` mode `unread`/`read`
are a read-only **peek** — they do *not* mark messages read.

## Distribution

- **Engine → PyPI:** `python -m build` + `twine upload` → users get
  `pipx install toxi`.
- **Engine → Homebrew:** `packaging/homebrew/toxi.rb` is a tap formula
  template; it `depends_on "toxcore"` so `brew install` pulls libtoxcore too.
  Publish via a personal tap (`brew tap <owner>/<name>`).
- **Plugin → marketplace:** `.claude-plugin/marketplace.json` makes this repo a
  marketplace. Push to GitHub and users run
  `/plugin marketplace add JefferyLee/toxi` then `/plugin install toxi`.

## Limitations (v1)

- macOS-first (Linux should work given libtoxcore; not yet a tested target).
- The local database and your private key are **not** encrypted at rest — they
  rely on filesystem permissions. Don't use on a shared/untrusted machine.
- Your IP is visible to people you chat with (a property of the Tox protocol).
- No group chat, voice/video, file transfer, or multi-device sync.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -m "not dht"   # fast offline tests
.venv/bin/python -m pytest -m dht          # slow tests that use the real Tox DHT
```
