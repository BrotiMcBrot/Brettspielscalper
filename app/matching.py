"""Titel-Matching: gehört ein Kleinanzeigen-Titel wirklich zu diesem Spiel?"""
import re
import unicodedata

STOPWORDS = {"the", "a", "an", "of", "and", "der", "die", "das", "des", "dem", "den", "ein", "eine", "einer",
             "und", "von", "vom", "im", "zu", "fur", "for", "spiel", "game"}
# Anzeigen mit diesen Wörtern sind meist kein Grundspiel (Zubehör, Merch, Bücher, Gesuche …)
REJECT = {
    "erweiterung", "erweiterungen", "expansion", "promo", "promos", "mini",
    "suche", "gesucht", "gesuch", "tausche", "tausch", "mieten", "leihen", "defekt",
    "sleeves", "insert", "inlay", "organizer", "tray", "trays", "zubehor", "upgrade", "3d", "clays",
    "matte", "spielmatte", "playmat", "neopren", "token", "tokens", "kartenhalter", "dashboard", "dashboards",
    "figur", "figuren", "spielfiguren", "miniatur", "miniaturen", "ersatzteil", "ersatzteile", "teile",
    "karton", "leer", "leerer", "booster", "pack", "map", "scenarios", "szenarien", "artbook", "art", "fan",
    "konvolut", "sammlung", "spielesammlung", "junior", "kids", "duo",
    "lego", "playmobil", "puzzle", "puzzel", "dvd", "bluray", "blu", "cd", "lp", "vinyl", "buch", "roman",
    "manga", "hardcover", "taschenbuch", "poster", "shirt", "tshirt", "trikot", "jacke", "weste", "pullover",
    "hoodie", "cap", "pin", "anstecknadel", "sticker", "aufkleber", "cpu", "kuhler",
}
EDITION = re.compile(r"\b(?:(?:second|2nd|third|3rd|fourth|4th|essential|revised|big box)\s+)?edition\b"
                     r"|\b(?:the\s+)?(?:board|card)\s+game\b", re.I)


def normalize(text):
    text = text.lower().replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokens(text):
    return [t for t in normalize(text).split() if t not in STOPWORDS]


def base_name(name):
    """Suchbarer Kurzname: Editions-Zusätze weg, lange Untertitel weg ('Through the Ages: A New Story …')."""
    n = EDITION.sub("", name).strip(" :–-")
    if ":" in n:
        pre, suf = n.split(":", 1)
        if len(tokens(suf)) >= 3 and len(normalize(pre)) >= 5:
            n = pre
    return n.strip(" :–-")


def contains(seq, sub):
    """sub kommt als zusammenhängende Wortfolge in seq vor."""
    return bool(sub) and any(seq[i:i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))


def matches(name, title, exclude=()):
    """Der Spielname muss als zusammenhängende Wortfolge im Titel stehen ('Star Wars Rebellion' passt nicht zu
    'Star Wars Rebels … Rebellion'); Ausschlusswörter (global + pro Spiel) dürfen nicht vorkommen."""
    want, have = tokens(name), tokens(title)
    if not contains(have, want):
        return False
    if (set(have) & REJECT) - set(want):
        return False
    return not any(contains(have, tokens(e)) for e in exclude)
