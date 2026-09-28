"""Titel-Matching: gehört ein Kleinanzeigen-Titel wirklich zu diesem Spiel?"""
import re
import unicodedata

STOPWORDS = {"the", "a", "an", "der", "die", "das", "und", "and", "of", "von", "fur", "for", "spiel", "game"}
# Anzeigen mit diesen Wörtern sind meist keine Grundspiele / keine Verkaufsangebote
REJECT = {"erweiterung", "expansion", "suche", "gesucht", "gesuch", "sleeves", "insert", "organizer",
          "ersatzteile", "ersatzteil", "promo", "tausche", "tausch", "mieten", "leihen", "defekt", "puzzle"}


def normalize(text):
    text = text.lower().replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def tokens(text):
    return [t for t in normalize(text).split() if t not in STOPWORDS]


def matches(game_name, title):
    """Alle Namens-Tokens müssen im Titel vorkommen; Ausschlusswörter dürfen nicht im Titel stehen,
    außer sie sind Teil des Spielnamens."""
    want = tokens(game_name)
    if not want:
        return False
    have = set(tokens(title))
    if not all(t in have for t in want):
        return False
    return not ((have & REJECT) - set(want))
