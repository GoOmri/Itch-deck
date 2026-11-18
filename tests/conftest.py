"""Tests never touch the network: every download fails as "offline" unless a test stubs it itself."""
import sys
import types
from pathlib import Path

import pytest

if sys.platform == "win32":                # mouse.py imports fcntl (Linux only): a stand-in lets the tests load
    try:
        import fcntl  # noqa: F401
    except ImportError:
        sys.modules["fcntl"] = types.ModuleType("fcntl")

from itch_deck import net


def pytest_collection_modifyitems(config, items):
    """On Windows, skip the tests listed in windows_known_failures.txt (they need Linux; CI runs them)."""
    if sys.platform != "win32":
        return
    try:
        lines = Path(__file__).with_name("windows_known_failures.txt").read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    known = {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}
    skip = pytest.mark.skip(reason="known to fail on Windows (needs Linux); CI runs it")
    for item in items:
        if item.nodeid in known:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*a, **k):
        raise net.Offline("tests never use the network")
    monkeypatch.setattr(net, "get", refuse)
    monkeypatch.setattr(net, "get_json", refuse)


@pytest.fixture(autouse=True)
def _steam_up():
    from itch_deck import dosart
    dosart.STEAM_STATE["down"] = False
    yield
    dosart.STEAM_STATE["down"] = False
