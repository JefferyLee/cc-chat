"""MCP server exposing toxi to MCP clients (e.g. Claude Code).

Run with `toxi mcp serve` (stdio transport). Needs the optional `mcp` extra:

    pipx install 'toxi[mcp]'      # or: pip install '.[mcp]'

The tools talk to the running daemon over its Unix socket, so start it first
with `toxi daemon start`.
"""
from . import client


def get_unread() -> list:
    """List unread incoming messages. Does NOT mark them read."""
    return client.request("get_messages", {"unread_only": True, "limit": 100})["messages"]


def read_history(alias: str, limit: int = 20) -> list:
    """Recent conversation history with a contact. Does NOT mark anything read."""
    return client.request("get_messages", {"alias": alias, "limit": limit})["messages"]


def send_message(alias: str, body: str) -> dict:
    """Send a message to a contact. It is queued if they're currently offline."""
    return client.request("send_message", {"alias": alias, "body": body})


def list_contacts() -> list:
    """List contacts with their online status."""
    return client.request("list_contacts", {})["contacts"]


def get_status() -> dict:
    """Daemon status: connection, contacts, queue size and 24h stats."""
    return client.request("get_status", {})


TOOLS = [get_unread, read_history, send_message, list_contacts, get_status]


def build_server():
    """Build the FastMCP server (imports `mcp` lazily so it stays optional)."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("toxi")
    for fn in TOOLS:
        server.tool()(fn)
    return server


def serve() -> None:
    build_server().run()
