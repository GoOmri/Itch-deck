"""Fake library for mockups and tests (M1). Titles are invented."""

_RAW = [
    # title, author, platforms, size MB, state
    ("Starfall Ferry", "Lantern Moth", "linux windows", 412, "installed"),
    ("Moss & Rivets", "tinyforge", "windows", 1380, "installed"),
    ("Hollow Lighthouse", "Kestrel Bay", "windows", 2210, "downloading"),
    ("Paper Comet", "oddbird", "linux", 96, "queued"),
    ("Grave Gardener", "Nightjar Games", "windows", 780, "failed"),
    ("Quiet Quarry", "Pebblesoft", "linux windows", 240, None),
    ("Ninefold Tower", "M. Okafor", "windows", 1650, None),
    ("Saltwater Saints", "Brine Collective", "linux", 512, None),
    ("Little Lamp Detective", "Foxglove", "html", 0, None),
    ("Bramble Run", "Kite & Key", "linux windows", 130, "installed"),
    ("Orbit Bakery", "sugarcube", "windows", 330, None),
    ("The Long Mile", "Ashgrove", "windows", 4100, None),
    ("Velvet Static", "nullwave", "mac", 600, None),
    ("Cinder Choir", "Ember Hall", "linux windows", 870, None),
    ("Dune Postman", "Waypoint", "windows", 1020, None),
    ("Frog Parliament", "lilypad", "html", 0, None),
    ("Glasshouse Garden", "Verdant", "linux", 210, None),
    ("Harbor Ghosts", "Tidewater", "windows", 640, "installed"),
    ("Iron Picnic", "Rustbelt", "windows", 900, None),
    ("Jelly Kingdom", "wobble", "linux windows", 75, None),
    ("Kettle Knight", "Steamworks Guild", "windows", 1500, None),
    ("Lost Signal OST", "nullwave", "soundtrack", 180, None),
    ("Marble Monastery", "Cloister", "linux windows", 360, None),
    ("Neon Orchard", "Pixel Pomona", "windows", 2800, None),
    ("Owl Post Express", "Featherlight", "html", 0, None),
    ("Pocket Volcano", "magma.exe", "windows", 450, None),
    ("Rainbarrel", "drizzle", "linux", 120, None),
    ("Sundial Thieves", "Gnomon", "windows", 1100, None),
    ("Tin Can Astronaut", "Orbital Jam", "linux windows", 520, None),
    ("Underthaw", "Permafrost", "windows", 3300, None),
]


def library():
    out = []
    for i, (title, author, plats, mb, state) in enumerate(_RAW):
        g = {"id": f"g{i:03d}", "title": title, "author": author,
             "platforms": set(plats.split()), "size_mb": mb, "state": state}
        if state == "downloading":
            g.update(progress=0.42, speed_mbs=11.8, eta_s=111)
        out.append(g)
    return sorted(out, key=lambda g: g["title"].lower())


def uploads():
    """Upload list for the build picker."""
    return [
        ("Linux 64-bit", "tar.gz · 212 MB", "Linux"),
        ("Windows", "zip · 240 MB", "Windows"),
        ("Windows installer", "setup.exe · 238 MB", "Windows"),
    ]  # demos/soundtracks are filtered out before the picker
