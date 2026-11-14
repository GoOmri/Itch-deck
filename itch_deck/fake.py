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
    ("Pocket Volcano", "magma.exe", "windows", 450, "missing"),
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
        g["short_text"] = _TAGLINES.get(title, "")
        g["screens"] = 0 if "html" in g["platforms"] else 3 + i % 4
        g["description"] = _description(title, g["short_text"])
        g["comments"] = _COMMENTS if i % 3 else []
        g["comment_count"] = 24 if i % 3 else 0
        g["added"] = f"2026-{1 + i % 11:02d}-{1 + (i * 7) % 27:02d}"
        if i % 4 == 1 or state == "installed":
            g["played"] = f"2026-11-{1 + (i * 5) % 14:02d}T20:00:00"
        if state == "downloading":
            g.update(progress=0.42, speed_mbs=11.8, eta_s=111)
        if state == "missing":
            g["missing"] = "card"
        out.append(g)
    return sorted(out, key=lambda g: g["title"].lower())


_TAGLINES = {
    "Quiet Quarry": "Dig, sort and stack stones in a sleepy mountain quarry. A cosy puzzle game.",
    "Hollow Lighthouse": "Keep the light burning through one long winter on a haunted island.",
    "Moss & Rivets": "Repair a rusted robot garden, one bolt and one sprout at a time.",
    "Grave Gardener": "Tend the flowers of a cemetery that doesn't stay quiet at night.",
    "Starfall Ferry": "Ferry fallen stars across a river in this short narrative game.",
}


def uploads():
    """Upload list for the build picker: (name the developer gave it, details, recommended).
    Demos, soundtracks and other-OS files are filtered out before the picker."""
    return [
        ("quietquarry-linux64.tar.gz", "Linux · 212 MB · updated 3 Oct", True),
        ("QuietQuarry_Windows.zip", "Windows · 240 MB · updated 3 Oct", False),
        ("QuietQuarry_Setup_v1.2.exe", "Windows installer · 238 MB · updated 1 Aug", False),
    ]


def _description(title, tagline):
    """Stand-in for the full description read from the game's itch page (HTML -> paragraphs)."""
    return [
        f"{title} started as a game jam entry and grew into a small, finished indie game.",
        f"Explore hand-drawn places, meet odd characters and find your own pace. {title} takes "
        "about two to three hours to finish, with a few secrets for anyone who looks closely.",
        "Features: full controller support · autosave · three save slots · original soundtrack.",
        "Controls: left stick to move, A to interact, B to cancel, Start for the menu.",
    ]


_COMMENTS = [
    {"author": "mossy_toad", "when": "2 days ago", "replies": 1,
     "text": "Runs great on the Steam Deck with Proton. The controls feel a bit floaty at first "
             "but you get used to them after the first area.",
     "reply_list": [{"author": "Pebblesoft", "when": "2 days ago", "dev": True,
                     "text": "Glad it works! A sensitivity slider is coming in the next update."}]},
    {"author": "Pebblesoft", "when": "3 days ago", "dev": True,
     "text": "Thanks everyone for playing! Update 1.2 fixes the save bug in chapter 2 and adds "
             "full controller support in the menus."},
    {"author": "nightowl_plays", "when": "1 week ago",
     "text": "Lovely little game, took me about two and a half hours. The ending made me smile. "
             "Would love a longer sequel some day, maybe with more puzzles in the caves, and more "
             "of the music from the second area because it was honestly the best part of the game."},
    {"author": "kestrel", "when": "2 weeks ago", "replies": 3,
     "text": "Is there a way to remap the jump button? Couldn't find it in the options.",
     "reply_list": [
         {"author": "nightowl_plays", "when": "2 weeks ago",
          "text": "Not in the game itself, but Steam Input can remap it per game."},
         {"author": "Pebblesoft", "when": "12 days ago", "dev": True,
          "text": "Remapping is on the list for 1.3, sorry about that!"}]},
]
