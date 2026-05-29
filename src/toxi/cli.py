"""The `toxi` CLI (PRD §4.7). Short-lived: each command talks to the daemon over
IPC and exits. Only `init` and `daemon start` touch the filesystem/process
directly; everything else goes through the daemon.
"""
import json
import shutil
import subprocess
import sys
import time

import click

from . import bootstrap, client, paths
from .tox import Tox

_CONNECTION = {0: "offline", 1: "connected (TCP)", 2: "connected (UDP)"}


def _call(method: str, params: dict | None = None):
    try:
        return client.request(method, params)
    except client.DaemonNotRunning as e:
        raise click.ClickException(str(e))
    except client.DaemonError as e:
        raise click.ClickException(e.message)  # human-readable; code is for programs


def _emit(ctx, data) -> bool:
    """In --json mode, print `data` as JSON and return True so the caller stops.
    Otherwise return False and let the caller print the human-readable version."""
    if ctx.obj and ctx.obj.get("json"):
        click.echo(json.dumps(data, ensure_ascii=False))
        return True
    return False


@click.group()
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON.")
@click.pass_context
def cli(ctx, as_json):
    """Decentralized, encrypted, asynchronous chat over the Tox protocol."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json


@cli.command()
def init():
    """Initialize your identity (generates your Tox keypair)."""
    paths.ensure_config_dir()
    sp = paths.tox_state_path()
    if sp.exists():
        t = Tox(savedata=sp.read_bytes())
        click.echo(f"Already initialized.\nYour Tox ID: {t.self_get_address_hex()}")
        t.kill()
        return
    t = Tox()
    address = t.self_get_address_hex()
    sp.write_bytes(t.get_savedata())
    t.kill()
    click.echo(
        f"Initialized toxi.\n"
        f"Your Tox ID: {address}\n\n"
        f"Share this ID with friends so they can add you.\n"
        f"Next: start the daemon with `toxi daemon start`."
    )


@cli.command()
@click.pass_context
def me(ctx):
    """Show your Tox ID and display name."""
    info = _call("get_me")
    if _emit(ctx, info):
        return
    click.echo(f"Your Tox ID: {info['tox_id']}")
    if info["name"]:
        click.echo(f"Display name: {info['name']}")
    click.echo(f"Connection: {_CONNECTION.get(info['connection'], 'unknown')}")


@cli.command(name="set-name")
@click.argument("name")
def set_name(name):
    """Set your display name."""
    _call("set_name", {"name": name})
    click.echo(f"Display name set to: {name}")


def _uptime(seconds: int) -> str:
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    parts = [f"{d}d" if d else "", f"{h}h" if h else "", f"{m}m"]
    return " ".join(p for p in parts if p)


@cli.command()
@click.pass_context
def status(ctx):
    """Show daemon status, DHT connection, contacts, queue and recent stats."""
    st = _call("get_status")
    if _emit(ctx, st):
        return
    dht = _CONNECTION.get(st["connection"], "offline") if st["dht_connected"] else "not connected"
    click.echo(f"Daemon: running (PID {st['pid']})")
    click.echo(f"Uptime: {_uptime(st['uptime_seconds'])}")
    click.echo(f"DHT: {dht}")
    click.echo(f"Tox ID: {st['tox_id']}")
    if st["name"]:
        click.echo(f"Display Name: {st['name']}")

    click.echo(f"\nContacts: {st['contacts_total']} total, {st['contacts_online']} online")
    for c in st["contacts"]:
        mark = "✓" if c["is_online"] else "○"
        state = "online" if c["is_online"] else "offline"
        seen = f" (last seen {_ago(c['last_seen'])})" if c["last_seen"] else ""
        click.echo(f"  {mark} {c['alias']:12} {state}{seen}")

    click.echo(f"\nQueue: {st['queue_size']} messages pending")
    s = st["stats_24h"]
    click.echo(f"Stats (last 24h): sent {s['sent']} / received {s['received']} / failed {s['failed']}")


@cli.command()
@click.argument("alias")
@click.argument("tox_id")
def add(alias, tox_id):
    """Add a friend by their Tox ID: toxi add <alias> <tox_id>."""
    _call("add_contact", {"alias": alias, "tox_id": tox_id})
    click.echo(f"Added {alias}. Friend request sent — waiting for them to accept.")


@cli.command()
@click.pass_context
def requests(ctx):
    """Show pending friend requests."""
    reqs = _call("list_requests")["requests"]
    if _emit(ctx, reqs):
        return
    if not reqs:
        click.echo("No pending friend requests.")
        return
    click.echo(f"[{len(reqs)} pending friend request(s)]")
    for r in reqs:
        click.echo(f"  {r['public_key']}")
        if r["message"]:
            click.echo(f"    \"{r['message']}\"")
    click.echo("\nAccept with: toxi accept <alias> <public-key-prefix>")


@cli.command()
@click.argument("alias")
@click.argument("public_key")
def accept(alias, public_key):
    """Accept a friend request: toxi accept <alias> <public-key-prefix>."""
    _call("accept_request", {"alias": alias, "public_key": public_key})
    click.echo(f"Accepted. Added as '{alias}'.")


@cli.command()
@click.option("--online", "online_only", is_flag=True, help="Only show online contacts.")
@click.pass_context
def contacts(ctx, online_only):
    """List your contacts."""
    cs = _call("list_contacts", {"online_only": online_only})["contacts"]
    if _emit(ctx, cs):
        return
    if not cs:
        click.echo("No contacts yet.")
        return
    for c in cs:
        mark = "✓" if c["is_online"] else "○"
        state = "online" if c["is_online"] else "offline"
        click.echo(f"  {mark} {c['alias']:12} {state}")


def _ago(ts: int) -> str:
    d = max(0, int(time.time()) - ts)
    if d < 60:
        return f"{d}s ago"
    if d < 3600:
        return f"{d // 60}m ago"
    if d < 86400:
        return f"{d // 3600}h ago"
    return f"{d // 86400}d ago"


@cli.command()
@click.argument("alias")
@click.argument("message")
@click.pass_context
def send(ctx, alias, message):
    """Send a message: toxi send <alias> <message> (use - to read from stdin)."""
    if message == "-":
        message = sys.stdin.read().rstrip("\n")
    res = _call("send_message", {"alias": alias, "body": message})
    if _emit(ctx, res):
        return
    if res["status"] == "sent":
        click.echo("✓ sent")
    else:
        click.echo(f"✓ {alias} is offline — queued (will send when they come online)")


@cli.command()
def statusline():
    """One-line summary for Claude Code's statusLine setting (never fails noisily)."""
    try:
        st = client.request("get_status")
        msgs = client.request("get_messages", {"unread_only": True, "limit": 100})["messages"]
    except client.DaemonNotRunning:
        click.echo("toxi: offline")
        return
    except client.DaemonError:
        click.echo("toxi: error")
        return

    online = f"{st['contacts_online']}/{st['contacts_total']} online"
    if msgs:
        senders = []
        for m in msgs:
            if m["alias"] not in senders:
                senders.append(m["alias"])
        click.echo(f"toxi: 📬 {len(msgs)} from {', '.join(senders)} · {online}")
    else:
        click.echo(f"toxi: {online}")


@cli.command()
@click.argument("alias", required=False)
@click.pass_context
def unread(ctx, alias):
    """Show unread messages (optionally just from one contact)."""
    msgs = _call("get_messages", {"alias": alias, "unread_only": True, "limit": 100})["messages"]
    # --json is a programmatic peek (e.g. the Claude Code hook); it must not mark read.
    if _emit(ctx, msgs):
        return
    if not msgs:
        click.echo("No unread messages.")
        return
    click.echo(f"[{len(msgs)} unread]")
    for m in reversed(msgs):  # oldest first
        click.echo(f"  {m['alias']} ({_ago(m['created_at'])}): {m['content']}")
    _call("mark_read", {"msg_uuids": [m["msg_uuid"] for m in msgs]})


@cli.command()
@click.argument("alias")
@click.option("--limit", default=20, help="How many recent messages to show.")
@click.pass_context
def read(ctx, alias, limit):
    """Show conversation history with a contact."""
    msgs = _call("get_messages", {"alias": alias, "limit": limit})["messages"]
    if _emit(ctx, msgs):  # programmatic peek: don't mark read
        return
    if not msgs:
        click.echo("No messages yet.")
        return
    for m in reversed(msgs):  # oldest first
        who = "you" if m["direction"] == "out" else m["alias"]
        click.echo(f"  {who} ({_ago(m['created_at'])}): {m['content']}")
    unread_in = [m["msg_uuid"] for m in msgs if m["direction"] == "in" and m["read_at"] is None]
    if unread_in:
        _call("mark_read", {"msg_uuids": unread_in})


@cli.command()
@click.pass_context
def queue(ctx):
    """Show messages waiting to be delivered."""
    q = _call("list_queue")["queue"]
    if _emit(ctx, q):
        return
    if not q:
        click.echo("Queue is empty.")
        return
    click.echo(f"[{len(q)} queued]")
    for m in q:
        click.echo(f"  {m['alias']}: {m['content']} ({_ago(m['created_at'])})")


@cli.command()
@click.argument("to")
@click.argument("whom")
@click.option("--note", default="", help="A short note about who this is.")
def introduce(to, whom, note):
    """Share a contact's details: toxi introduce <to> <whom>."""
    _call("introduce", {"to_alias": to, "contact_alias": whom, "note": note})
    click.echo(f"✓ Sent {whom}'s contact to {to}.")


@cli.command()
@click.pass_context
def introductions(ctx):
    """Show contacts other people have introduced to you."""
    intros = _call("list_introductions")["introductions"]
    if _emit(ctx, intros):
        return
    if not intros:
        click.echo("No introductions.")
        return
    click.echo(f"[{len(intros)} introduction(s)]")
    for i in intros:
        click.echo(f"  {i['from_alias']} introduced '{i['suggested_alias']}' "
                   f"(Tox ID: {i['introduced_tox_id'][:16]}...)")
        if i["note"]:
            click.echo(f"    note: {i['note']}")
    click.echo("\nAccept with: toxi accept-intro <from> <whom> [--alias=...]")


@cli.command(name="accept-intro")
@click.argument("introducer", metavar="FROM")
@click.argument("whom")
@click.option("--alias", default=None, help="Local alias to give them (default: their suggested name).")
def accept_intro(introducer, whom, alias):
    """Accept an introduction: toxi accept-intro <from> <whom>."""
    res = _call("accept_introduction",
                {"from_alias": introducer, "whom": whom, "alias": alias})
    click.echo(f"Sending a friend request to '{res['alias']}'. They'll need to accept it.")


@cli.group()
def daemon():
    """Manage the background daemon."""


def _spawn_daemon(timeout: float = 10.0) -> int:
    """Spawn the daemon detached and poll until it answers. Returns the PID."""
    paths.ensure_config_dir()
    proc = subprocess.Popen(
        [sys.executable, "-m", "toxi.daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bootstrap.daemon_running():
            return proc.pid
        time.sleep(0.05)
    raise click.ClickException(f"daemon failed to start; check {paths.log_path()}")


@daemon.command("start")
def daemon_start():
    """Start the background daemon."""
    if bootstrap.daemon_running():
        click.echo("daemon already running")
        return
    pid = _spawn_daemon()
    click.echo(f"daemon started (pid {pid})")


@daemon.command("stop")
def daemon_stop():
    """Stop the background daemon."""
    try:
        client.request("shutdown")
        click.echo("daemon stopped")
    except client.DaemonNotRunning:
        click.echo("daemon is not running")


@cli.group()
def mcp():
    """MCP server for Claude Code and other MCP clients."""


@mcp.command("serve")
def mcp_serve():
    """Run the MCP server over stdio (used by Claude Code's .mcp.json)."""
    from . import mcp_server
    try:
        mcp_server.serve()
    except ImportError:
        raise click.ClickException(
            "MCP support needs the extra: pipx install 'toxi[mcp]'"
        )


@cli.command()
def setup():
    """One-shot setup: init identity, start daemon, wire Claude Code statusLine."""
    # 1. Identity
    if bootstrap.identity_initialized():
        click.echo("✓ Identity already initialized.")
    else:
        paths.ensure_config_dir()
        t = Tox()
        addr = t.self_get_address_hex()
        paths.tox_state_path().write_bytes(t.get_savedata())
        t.kill()
        click.echo(f"✓ Generated identity (Tox ID: {addr[:16]}…). Run `toxi me` for the full ID.")

    # 2. Daemon
    if bootstrap.daemon_running():
        click.echo("✓ Daemon already running.")
    else:
        pid = _spawn_daemon()
        click.echo(f"✓ Daemon started (PID {pid}).")

    # 3. statusLine
    sp = bootstrap.claude_settings_path()
    result = bootstrap.ensure_statusline()
    if result == "added":
        click.echo(f"✓ Wired statusLine into {sp}.")
    elif result == "kept":
        click.echo(f"✓ statusLine already wired in {sp}.")
    else:  # left-custom
        click.echo(
            f"⚠ {sp} already has a custom statusLine — not touching it.\n"
            f'  To enable toxi in the status bar, merge in: '
            f'{{"statusLine":{{"type":"command","command":"toxi statusline"}}}}'
        )

    # 4. Plugin install hint (Claude Code's plugin registry isn't safe to write from outside)
    click.echo("\nNext — install the Claude Code plugin (run inside Claude Code):")
    click.echo("  /plugin marketplace add JefferyLee/cc-chat")
    click.echo("  /plugin install toxi")


@cli.command()
@click.option("--purge", is_flag=True,
              help="Also delete your identity and chat history (DESTRUCTIVE).")
def teardown(purge):
    """Reverse of setup: stop daemon, unwire statusLine, optionally wipe identity."""
    # 1. Daemon
    if bootstrap.daemon_running():
        try:
            client.request("shutdown")
            click.echo("✓ Daemon stopped.")
        except client.DaemonNotRunning:
            click.echo("✓ Daemon stopped.")
    else:
        click.echo("✓ Daemon already stopped.")

    # 2. statusLine
    sp = bootstrap.claude_settings_path()
    result = bootstrap.remove_statusline()
    if result == "removed":
        click.echo(f"✓ Removed statusLine entry from {sp}.")
    elif result == "absent":
        click.echo("✓ statusLine entry already absent.")
    else:  # left-custom
        click.echo(f"⚠ statusLine in {sp} isn't ours — leaving it alone.")

    # 3. Optional purge
    if purge:
        cd = paths.config_dir()
        if cd.exists():
            shutil.rmtree(cd)
            click.echo(f"✓ Removed config dir ({cd}). Your identity is gone.")
        else:
            click.echo(f"✓ Config dir already absent ({cd}).")
    else:
        click.echo(f"\n(Identity + history preserved in {paths.config_dir()}. Pass --purge to wipe.)")

    # 4. Next steps
    click.echo("\nFinish removal:")
    click.echo("  In Claude Code:  /plugin uninstall toxi@toxi")
    click.echo("  In terminal:     pipx uninstall toxi")


def _pipx_lifecycle(pipx_args: list[str], label: str) -> None:
    """Shared body for `upgrade` and `reinstall`: stop daemon → run pipx → restart."""
    was_running = bootstrap.daemon_running()
    if was_running:
        try:
            client.request("shutdown")
            click.echo("→ Stopped daemon.")
        except client.DaemonNotRunning:
            pass

    click.echo(f"→ Running `pipx {' '.join(pipx_args)}`...")
    try:
        r = subprocess.run(["pipx", *pipx_args], capture_output=True, text=True)
    except FileNotFoundError:
        raise click.ClickException("pipx not found on PATH.")
    click.echo(r.stdout.rstrip() or "(no output)")
    if r.returncode != 0:
        click.echo(r.stderr.rstrip(), err=True)
        raise click.ClickException(f"pipx {label} failed.")

    if was_running:
        pid = _spawn_daemon()
        click.echo(f"✓ Daemon restarted (PID {pid}).")

    click.echo("\nIf the plugin shipped changes too, in Claude Code:")
    click.echo("  /plugin uninstall toxi@toxi")
    click.echo("  /plugin install toxi")


@cli.command()
def upgrade():
    """Upgrade the engine via pipx — only fires when pyproject.toml version bumped."""
    _pipx_lifecycle(["upgrade", "toxi"], "upgrade")


@cli.command()
def reinstall():
    """Force-reinstall the engine via pipx — ignores version, always re-fetches."""
    _pipx_lifecycle(["reinstall", "toxi"], "reinstall")


if __name__ == "__main__":
    cli()
