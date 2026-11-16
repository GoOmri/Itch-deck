"""Stand-in for gogdl's C extension gogdl_xdelta3 (xdelta3 patching).

gogdl imports it at the top of its download worker, but only CALLS it to apply a GOG patch file
to an existing install (game updates, GOG step 3). Fresh installs (step 2) never patch. Raising
RuntimeError here is what gogdl already catches as "Patch failed" for that one file.
Step 3 decides: build the real extension in CI, or always update by chunks.
"""


def patch(source, patch_file, target, speed_queue=None):
    raise RuntimeError("xdelta3 patching isn't built into SCRiTCH")
