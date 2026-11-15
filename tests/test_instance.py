"""Single instance (v0.7.1 Deck log: two copies ran at once and raced on hltb.json)."""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from itch_deck import library, paths

ROOT = Path(__file__).resolve().parent.parent

LOCK_AND = """
import os, sys, time
sys.path.insert(0, {root!r})
from itch_deck import paths
paths.use_root({tmp!r})
r = paths.lock_instance()
print("LOCKED" if r is None else "BUSY " + r, flush=True)
{after}
"""


def _py(tmp, after="", **kw):
    code = LOCK_AND.format(root=str(ROOT), tmp=str(tmp), after=after)
    return subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, **kw)


def test_second_copy_is_refused_and_lock_frees_on_exit(tmp_path):
    first = _py(tmp_path, "time.sleep(30)")
    assert first.stdout.readline().strip() == "LOCKED"
    second = _py(tmp_path)
    out = second.communicate(timeout=20)[0].strip()
    assert out == f"BUSY {first.pid}"
    first.kill()
    first.wait()
    third = _py(tmp_path)
    assert third.communicate(timeout=20)[0].strip() == "LOCKED"


def test_exec_restart_retakes_the_lock(tmp_path):
    """The updater restarts with os.execve: the new image must get the lock, not see itself."""
    again = LOCK_AND.format(root=str(ROOT), tmp=str(tmp_path), after="")
    p = _py(tmp_path, f"os.execv(sys.executable, [sys.executable, '-c', {again!r}])")
    out = p.communicate(timeout=20)[0].split()
    assert out == ["LOCKED", "LOCKED"]


def test_json_writes_from_many_threads_never_collide(tmp_path):
    target = tmp_path / "hltb.json"
    errors = []

    def write(n):
        try:
            for i in range(50):
                library._write_json(target, {"n": n, "i": i})
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    ts = [threading.Thread(target=write, args=(n,)) for n in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors
    assert json.loads(target.read_text())["i"] == 49
    assert [p.name for p in tmp_path.iterdir()] == ["hltb.json"]   # no temp files left


def test_tmp_names_differ_per_process_and_thread(tmp_path):
    a = paths.tmp_for(tmp_path / "x.json")
    b = []
    t = threading.Thread(target=lambda: b.append(paths.tmp_for(tmp_path / "x.json")))
    t.start()
    t.join()
    assert a != b[0] and str(os.getpid()) in a.name and a.parent == tmp_path
