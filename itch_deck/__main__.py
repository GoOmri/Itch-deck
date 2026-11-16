import sys

if sys.argv[1:2] == ["--gogdl"]:          # hidden mode: the vendored GOG helper (stores/gog.py)
    from itch_deck.gogdl_mode import run
    sys.exit(run(sys.argv[2:]))

from itch_deck.app import main  # noqa: E402

sys.exit(main())
