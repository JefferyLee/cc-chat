"""CLI tests. `init` needs no daemon; the rest drive the real `chat daemon
start`/`stop` commands (spawning an actual daemon subprocess) and exercise the
full CLI -> IPC -> daemon path.
"""
import shutil
import tempfile

import pytest
from click.testing import CliRunner

from toxi import paths
from toxi.cli import cli


@pytest.fixture
def home(monkeypatch):
    d = tempfile.mkdtemp(prefix="cc-", dir="/tmp")  # short path for AF_UNIX
    monkeypatch.setenv("TOXI_HOME", d)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_init_creates_identity(home):
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "Your Tox ID:" in result.output
    assert paths.tox_state_path().exists()

    again = runner.invoke(cli, ["init"])
    assert "Already initialized" in again.output


def test_me_requires_daemon(home):
    result = CliRunner().invoke(cli, ["me"])
    assert result.exit_code != 0
    assert "daemon is not running" in result.output


def test_full_cli_lifecycle(home):
    runner = CliRunner()
    try:
        assert "daemon started" in runner.invoke(cli, ["daemon", "start"]).output

        me = runner.invoke(cli, ["me"])
        assert me.exit_code == 0
        # 38-byte Tox address printed as 76 hex chars
        line = next(l for l in me.output.splitlines() if l.startswith("Your Tox ID:"))
        assert len(line.split(": ", 1)[1]) == 76

        assert "set to: alice" in runner.invoke(cli, ["set-name", "alice"]).output
        assert "Display name: alice" in runner.invoke(cli, ["me"]).output

        st = runner.invoke(cli, ["status"])
        assert "DHT:" in st.output and "Queue: 0 messages pending" in st.output
    finally:
        runner.invoke(cli, ["daemon", "stop"])


def test_daemon_stop_when_not_running(home):
    assert "not running" in CliRunner().invoke(cli, ["daemon", "stop"]).output


def test_error_message_is_clean(home):
    """CLI errors show the human message, not the internal error code."""
    runner = CliRunner()
    try:
        runner.invoke(cli, ["daemon", "start"])
        res = runner.invoke(cli, ["send", "ghost", "hi"])
        assert res.exit_code != 0
        assert "no contact named" in res.output
        assert "CONTACT_NOT_FOUND" not in res.output
    finally:
        runner.invoke(cli, ["daemon", "stop"])
