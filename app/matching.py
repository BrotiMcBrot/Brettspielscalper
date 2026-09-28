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
    "erw", "startspielertoken", "startspielermarker", "promokarte", "promokarten", "startspieler", "playerboard", "spielplan", "spielplane", "spielematte",
    "inserts", "inlays", "spieleinsatz", "munzen", "spielmunzen", "halter", "stander", "funko", "plusch",
    "plushtier", "pluschtier", "nerf", "hot", "wheels", "barbie", "beyblade", "modellauto", "book",
}
# Diese Wörter zeigen, dass es um ein Spiel geht – Pflicht bei mehrdeutigen Namen (Eclipse, Nemesis, SETI …)
GAME_CONTEXT = {
    "brettspiel", "brettspiele", "spiel", "spiele", "gesellschaftsspiel", "kartenspiel", "strategiespiel",
    "familienspiel", "kennerspiel", "expertenspiel", "boardgame", "board", "spieler", "grundspiel",
    "kosmos", "feuerland", "pegasus", "lookout", "alea", "ravensburger", "asmodee", "schmidt", "skellig",
    "frosted", "strohmann", "ffg", "cmon", "gmt", "stonemaier", "cranio", "eagle", "gryphon",
}
# "König & Intrigant für El Grande", "Kioske für Ark Nova", "Roll&Write zu Grand Austria Hotel" = Zubehör/Ableger
ACCESSORY_BEFORE = {"fur", "for", "zu", "zum", "passend"}
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


def matches(name, title, exclude=(), need_context=False):
    """Der Spielname muss als zusammenhängende Wortfolge im Titel stehen ('Star Wars Rebellion' passt nicht zu
    'Star Wars Rebels … Rebellion'); Ausschlusswörter (global + pro Spiel) dürfen nicht vorkommen.
    need_context: Titel muss zusätzlich ein Spiel-Wort enthalten (für mehrdeutige Namen)."""
    want, have = tokens(name), tokens(title)
    if not contains(have, want):
        return False
    if (set(have) & REJECT) - set(want):
        return False
    if any(contains(have, tokens(e)) for e in exclude):
        return False
    raw = normalize(title).split()
    first = raw.index(want[0]) if want[0] in raw else 0
    if set(raw[:first]) & ACCESSORY_BEFORE:
        return False
    if title.count(",") >= 2:  # "AZUL, Phase 10, Siedler, …" – Sammelanzeige, Preis nicht vergleichbar
        return False
    return not need_context or bool(set(raw) & GAME_CONTEXT)
