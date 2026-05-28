"""The `cc-chat` CLI (PRD §4.7). Short-lived: each command talks to the daemon over
IPC and exits. Only `init` and `daemon start` touch the filesystem/process
directly; everything else goes through the daemon.
"""
import json
import subprocess
import sys
import time

import click

from . import client, paths
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
        f"Initialized cc-chat.\n"
        f"Your Tox ID: {address}\n\n"
        f"Share this ID with friends so they can add you.\n"
        f"Next: start the daemon with `cc-chat daemon start`."
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
    """Add a friend by their Tox ID: cc-chat add <alias> <tox_id>."""
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
    click.echo("\nAccept with: cc-chat accept <alias> <public-key-prefix>")


@cli.command()
@click.argument("alias")
@click.argument("public_key")
def accept(alias, public_key):
    """Accept a friend request: cc-chat accept <alias> <public-key-prefix>."""
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
    """Send a message: cc-chat send <alias> <message> (use - to read from stdin)."""
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
    """Share a contact's details: cc-chat introduce <to> <whom>."""
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
    click.echo("\nAccept with: cc-chat accept-intro <from> <whom> [--alias=...]")


@cli.command(name="accept-intro")
@click.argument("introducer", metavar="FROM")
@click.argument("whom")
@click.option("--alias", default=None, help="Local alias to give them (default: their suggested name).")
def accept_intro(introducer, whom, alias):
    """Accept an introduction: cc-chat accept-intro <from> <whom>."""
    res = _call("accept_introduction",
                {"from_alias": introducer, "whom": whom, "alias": alias})
    click.echo(f"Sending a friend request to '{res['alias']}'. They'll need to accept it.")


@cli.group()
def daemon():
    """Manage the background daemon."""


@daemon.command("start")
def daemon_start():
    """Start the background daemon."""
    try:
        client.request("get_status")
        click.echo("daemon already running")
        return
    except client.DaemonNotRunning:
        pass
    paths.ensure_config_dir()
    proc = subprocess.Popen(
        [sys.executable, "-m", "claude_chat.daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            client.request("get_status")
            click.echo(f"daemon started (pid {proc.pid})")
            return
        except client.DaemonNotRunning:
            time.sleep(0.05)
    raise click.ClickException(f"daemon failed to start; check {paths.log_path()}")


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
            "MCP support needs the extra: pipx install 'cc-chat[mcp]'"
        )


if __name__ == "__main__":
    cli()
