"""Key and mouse-button names the virtual keyboard can press (Linux input codes). No Linux-only imports, so
dos_controls.py and the tests can use it anywhere. mouse.py registers every code below with uinput."""

BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112

CODES = {
    "esc": 1, "enter": 28, "tab": 15, "backspace": 14, "space": 57,
    "up": 103, "down": 108, "left": 105, "right": 106,
    "ctrl": 29, "alt": 56, "shift": 42,
    "comma": 51, "period": 52,
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21, "u": 22, "i": 23, "o": 24, "p": 25,
    "a": 30, "s": 31, "d": 32, "f": 33, "g": 34, "h": 35, "j": 36, "k": 37, "l": 38,
    "z": 44, "x": 45, "c": 46, "v": 47, "b": 48, "n": 49, "m": 50,
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64, "f7": 65, "f8": 66, "f9": 67, "f10": 68,
    "lmb": BTN_LEFT, "rmb": BTN_RIGHT, "mmb": BTN_MIDDLE,
}

# what the player sees for a key ("ctrl" -> "Ctrl"): plain words, no codes
WORDS = {"esc": "Esc", "enter": "Enter", "tab": "Tab", "backspace": "Backspace", "space": "Space",
         "up": "Up", "down": "Down", "left": "Left", "right": "Right", "ctrl": "Ctrl", "alt": "Alt",
         "shift": "Shift", "comma": ",", "period": ".", "lmb": "Left click", "rmb": "Right click",
         "mmb": "Middle click"}


def word(key):
    return WORDS.get(key) or key.upper()
