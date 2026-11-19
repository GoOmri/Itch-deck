"""Game page store label: plain store names, one helper."""
from itch_deck.ui import widgets as W
from itch_deck.ui.scenes import library


def test_store_label_each_store():
    assert W.store_label({"store": "itch"}) == "itch.io"
    assert W.store_label({"store": "epic"}) == "Epic"
    assert W.store_label({"store": "gog"}) == "GOG"
    assert W.store_label({"store": "dos"}) == "DOS"


def test_store_label_missing_key_is_itch():
    assert W.store_label({}) == "itch.io"
    assert W.store_label({"store": None}) == "itch.io"


def test_gog_dos_game_still_says_gog():
    assert W.store_label({"store": "gog", "dos": True}) == "GOG"


def test_tab_names_unchanged():
    assert library.STORE_NAMES == {"itch": "itch", "epic": "Epic", "gog": "GOG"}
