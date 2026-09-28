"""Diagnose: testet BGG, Geizhals und Kleinanzeigen mit einem Beispielspiel und legt die Roh-HTML-Seiten ab."""
import os
import re

from . import bgg, geizhals, http, kleinanzeigen

DEBUG_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "debug")
SAMPLE = "Brass Birmingham"
BLOCK_WORDS = re.compile(r"captcha|cloudflare|access denied|zugriff verweigert|robot|consent|zustimmung|verify you", re.I)


def _probe(label, url, parser):
    lines = [f"== {label}: {url}"]
    try:
        r = http.get(url)
    except Exception as e:
        return lines + [f"   FEHLER beim Verbinden: {e}"]
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.abspath(os.path.join(DEBUG_DIR, f"{label}.html"))
    open(path, "w", encoding="utf-8").write(r.text)
    items = parser(r.text) if r.status_code == 200 else []
    title = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
    lines += [f"   HTTP {r.status_code}, {len(r.text)} Zeichen, Titel: {title.group(1).strip()[:80] if title else '-'}",
              f"   gelesene Einträge: {len(items)}"]
    lines += [f"     - {i}" for i in items[:3]]
    if BLOCK_WORDS.search(r.text[:20000]) and not items:
        lines.append("   Hinweis: Seite enthält Captcha-/Consent-/Bot-Schutz-Wörter.")
    lines.append(f"   Roh-HTML gespeichert: {path}")
    return lines


def run():
    out = _probe("bgg", "https://boardgamegeek.com/browse/boardgame", bgg.parse_ranking)
    out += _probe("geizhals", geizhals.search_url(SAMPLE), geizhals.parse_results)
    out += _probe("kleinanzeigen", kleinanzeigen.search_url(SAMPLE), kleinanzeigen.parse_results)
    return "\n".join(out)
