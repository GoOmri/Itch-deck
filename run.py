import multiprocessing
import sys

# Frozen build: helper processes started by multiprocessing (gogdl's resource tracker) re-run
# this binary with their own arguments; freeze_support() runs them instead of the app (v0.9.7).
multiprocessing.freeze_support()

if sys.argv[1:2] == ["--gogdl"]:          # hidden mode: the vendored GOG helper (stores/gog.py)
    from itch_deck.gogdl_mode import run
    sys.exit(run(sys.argv[2:]))

from itch_deck.app import main  # noqa: E402

sys.exit(main())
