"""Tests never touch the network: every download fails as "offline" unless a test stubs it itself."""
import pytest

from itch_deck import net


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*a, **k):
        raise net.Offline("tests never use the network")
    monkeypatch.setattr(net, "get", refuse)
    monkeypatch.setattr(net, "get_json", refuse)
