"""Store interface. The UI only talks to Library, which talks to a Store — so an Epic tab can
plug in later without touching scenes."""


class Store:
    name = "?"

    def check_key(self):
        """Raise net.AuthError if the credentials are bad, net.Offline if unreachable."""
        raise NotImplementedError

    def sync(self, on_page=None):
        """Return the owned games as plain dicts (see stores/itch.py game_from_key)."""
        raise NotImplementedError

    def list_builds(self, game):
        """Uploads as dicts: id, filename, name, size, type, storage, demo, linux, windows."""
        raise NotImplementedError

    def download_url(self, game, build):
        """URL to stream the build from (fetched fresh each time: they expire)."""
        raise NotImplementedError
