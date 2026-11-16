"""Hidden mode: `scritch --gogdl <args>` runs the vendored gogdl (itch_deck/vendor, GPL-3).

Always started as its own process by stores/gog.py (never inside the app's process: gogdl forks
download workers and installs its own signal handlers). Kept free of pygame and of the app's
imports, so it starts quickly."""
import os
import sys

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")


def run(args):
    if VENDOR not in sys.path:
        sys.path.insert(0, VENDOR)
    import multiprocessing
    try:
        multiprocessing.set_start_method("fork")    # Linux: workers fork; no re-exec of our binary
    except (RuntimeError, ValueError):
        pass
    import gogdl.cli
    sys.argv = ["gogdl", *args]
    gogdl.cli.main()
    return 0
