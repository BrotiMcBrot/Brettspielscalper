"""Diagnose: testet BGG, Geizhals und Kleinanzeigen mit einem Beispielspiel und legt die Roh-HTML-Seiten ab."""
import os
import re

from bs4 import BeautifulSoup

from . import bgg, ebay, http, kleinanzeigen, shops

DEBUG_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "debug")
SAMPLE = "Brass Birmingham"
BLOCK_WORDS = re.compile(r"captcha|cloudflare|access denied|zugriff verweigert|robot|consent|zustimmung|verify you", re.I)


def _probe(label, url, parser):
    lines = [f"== {label}: {url}"]
    try:
        r = http.get(url)
    except http.Blocked as e:
        return lines + [f"   BLOCKIERT: {e}"]
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
    if items and "category" in items[0]:
        from collections import Counter
        lines.append(f"   Kategorien der Anzeigen: {dict(Counter(i['category'] for i in items))}")
    if BLOCK_WORDS.search(r.text[:20000]) and not items:
        lines.append("   Hinweis: Seite enthält Captcha-/Consent-/Bot-Schutz-Wörter.")
    if label == "kleinanzeigen":
        art = BeautifulSoup(r.text, "html.parser").select_one("article[data-adid]")
        if art is not None:
            lines.append("   Erste Anzeige (Rohdaten, bitte bei Problemen mitschicken):")
            lines.append("   " + re.sub(r"\s+", " ", str(art))[:1500])
    lines.append(f"   Roh-HTML gespeichert: {path}")
    return lines


def run():
    out = _probe("bgg", "https://boardgamegeek.com/browse/boardgame", bgg.parse_ranking)
    out += _probe("kleinanzeigen", kleinanzeigen.search_url(SAMPLE, kleinanzeigen.GAMES_CATEGORY), kleinanzeigen.parse_results)
    for shop in shops.load():
        out += _probe_shop(shop)
    out.append("== eBay-API: " + ("eingerichtet" if ebay.configured() else "nicht eingerichtet (optional, siehe README)"))
    if ebay.configured():
        try:
            offers, raw = ebay.find_offers([SAMPLE])
            out.append(f"   {raw} Artikel gelesen, {len(offers)} passend")
        except Exception as e:
            out.append(f"   FEHLER: {e}")
    return "\n".join(out)


def _probe_shop(shop):
    lines = [f"== Shop {shop['name']}"]
    try:
        found = shops.find_price([SAMPLE], [shop], blocked := {})
    except Exception as e:
        return lines + [f"   FEHLER: {e}"]
    if blocked:
        return lines + [f"   BLOCKIERT: {next(iter(blocked.values()))}"]
    return lines + [f"   OK: {found[0]:.2f} € – {found[1]}" if found else
                    "   kein Preis gefunden (Such-URL falsch, keine strukturierten Daten, oder Spiel nicht im Sortiment)"]
