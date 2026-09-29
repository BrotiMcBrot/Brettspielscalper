"""Diagnose: testet BGG, Geizhals und Kleinanzeigen mit einem Beispielspiel und legt die Roh-HTML-Seiten ab."""
import os
import re

from bs4 import BeautifulSoup

from . import bgg, bgprices, ebay, http, kleinanzeigen, mydealz, shops

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
    try:
        import json as _json
        data = bgprices.raw(224517)
        os.makedirs(DEBUG_DIR, exist_ok=True)
        path = os.path.abspath(os.path.join(DEBUG_DIR, "bgprices.json"))
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=1, ensure_ascii=False)
        item = (data.get("items") or [{}])[0] if isinstance(data, dict) else {}
        first = (item.get("prices") or [{}])[:2]
        out.append("== BoardGamePrices Rohdaten (bitte mitschicken): Felder " + ", ".join(sorted(item)) )
        out += ["     " + _json.dumps(p, ensure_ascii=False)[:400] for p in first]
        out.append(f"     gespeichert: {path}")
    except Exception as e:
        out.append(f"== BoardGamePrices Rohdaten: {e}")
    prices, err = bgprices.fetch([224517])  # Brass: Birmingham
    out.append("== BoardGamePrices-API (experimentell): " + (err or (f"OK: {prices[224517][0]:.2f} € – {prices[224517][1]}"
                                                                     if 224517 in prices else "Antwort ohne Preis")))
    deals, errs = mydealz.fetch_all()
    out.append(f"== mydealz-RSS: {len(deals)} Brettspiel-Deals gelesen" + (f" – {'; '.join(errs)}" if errs else ""))
    out += [f"     - {d['price']:.2f} € {d['title'][:80]}" for d in deals[:3]]
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
    from urllib.parse import quote_plus
    try:  # Suchseite für die Fehlersuche ablegen
        template = shops.search_url(shop)
        if not template:
            return lines + ["   keine funktionierende Such-Adresse gefunden (Muster aus app/shops.py passen nicht)"]
        r = http.get(template.replace("{q}", quote_plus(SAMPLE)))
        os.makedirs(DEBUG_DIR, exist_ok=True)
        path = os.path.abspath(os.path.join(DEBUG_DIR, "shop_" + re.sub(r"\W+", "_", shop["name"]) + ".html"))
        open(path, "w", encoding="utf-8").write(r.text)
        lines.append(f"   Suchseite: HTTP {r.status_code}, landet auf {r.url} – gespeichert: {path}")
        soup = BeautifulSoup(r.text, "html.parser")
        hrefs = [a["href"] for a in soup.find_all("a", href=True)]
        brass = [h for h in hrefs if "brass" in h.lower()]
        types = sorted({t for t in re.findall(r'"@type"\s*:\s*"(\w+)"', r.text)})
        lines.append(f"   {len(hrefs)} Links, davon {len(brass)} mit 'brass': {brass[:3]} · JSON-LD-Typen: {types[:8]}"
                     + (" · Seite nutzt vermutlich JavaScript zum Nachladen" if len(r.text) < 30000 and not brass else ""))
    except http.Blocked as e:
        return lines + [f"   BLOCKIERT: {e}"]
    except Exception as e:
        return lines + [f"   FEHLER: {e}"]
    try:
        found = shops.find_price([SAMPLE], [shop], blocked := {})
    except Exception as e:
        return lines + [f"   FEHLER: {e}"]
    if blocked:
        return lines + [f"   BLOCKIERT: {next(iter(blocked.values()))}"]
    kind = "Gebraucht-Händler" if (shop.get("type") or "new") == "used" else "Neupreis-Shop"
    return lines + [f"   {kind} OK: {found[0]:.2f} € – {found[1]}" if found else
                    "   kein Preis gefunden (Such-URL falsch, keine strukturierten Daten, oder Spiel nicht im Sortiment)"]
