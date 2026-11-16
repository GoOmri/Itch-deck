# Vendored code

## gogdl (GPL-3, `gogdl/LICENSE`)
Heroic Games Launcher's GOG helper: https://github.com/Heroic-Games-Launcher/heroic-gogdl
Copied unchanged from commit 6c6ef53 (28 Oct 2026, gogdl 1.4.0), package folder only.

Why vendored: gogdl's GitHub releases are hand-published drafts, so the Linux file isn't
reliably there to download (SCRiTCH v0.9.0 failed on the Deck because of that). gogdl is pure
Python + `requests`, so SCRiTCH carries it and runs it as a hidden mode of its own binary:
`scritch --gogdl <gogdl arguments>` (see `itch_deck/gogdl_mode.py`), in its own process.

Not included: the C extension `gogdl_xdelta3` (patch files for game updates). `gogdl_xdelta3.py`
here is a stand-in that refuses to patch; fresh installs never patch. GOG step 3 (updates)
decides what to do about it.

To update: copy the new `gogdl/` folder over this one, keep `LICENSE`, update the commit above,
run `python -m pytest -q tests/test_gog.py`.
