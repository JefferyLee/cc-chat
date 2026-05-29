"""Tests for the MCP server glue.

The tool functions are thin wrappers over the daemon RPC, so we verify they call
the right method/params (with client.request faked — no daemon needed). The
FastMCP build is checked only if the optional `mcp` extra is installed.
"""
import pytest

from toxi import mcp_server


def test_tools_call_expected_rpcs(monkeypatch):
    calls = []

    def fake_request(method, params=None, **kwargs):
        calls.append((method, params))
        return {
            "get_messages": {"messages": [{"alias": "bob", "content": "hi"}]},
            "send_message": {"status": "queued"},
            "list_contacts": {"contacts": []},
            "get_status": {"queue_size": 0},
        }.get(method, {})

    monkeypatch.setattr(mcp_server.client, "request", fake_request)

    assert mcp_server.get_unread() == [{"alias": "bob", "content": "hi"}]
    assert ("get_messages", {"unread_only": True, "limit": 100}) in calls

    assert mcp_server.send_message("bob", "hi")["status"] == "queued"
    assert ("send_message", {"alias": "bob", "body": "hi"}) in calls

    assert mcp_server.list_contacts() == []
    assert mcp_server.get_status() == {"queue_size": 0}
    mcp_server.read_history("bob", 5)
    assert ("get_messages", {"alias": "bob", "limit": 5}) in calls


def test_build_server():
    pytest.importorskip("mcp")
    server = mcp_server.build_server()
    assert server is not None
