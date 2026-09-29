"""BoardGamePrices (boardgameprices.co.uk) – Preisvergleich speziell für Brettspiele mit öffentlicher API.

Abfrage per BGG-ID, Lieferziel Deutschland, Preise in EUR. Die Daten stammen direkt von den Shops (Preisvergleich brettspielpreise.de)."""
from . import http

API = "https://boardgameprices.co.uk/api/info"


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse(data):
    """-> {bgg_id: {"min": preis, "median": preis, "count": n, "link": url}}
    Preis = Gesamtpreis inkl. Versand nach DE ("price"), nur lieferbare Angebote. Mehrere Einträge
    (Editionen/Sprachversionen) zur selben BGG-ID werden zusammengefasst."""
    from statistics import median
    collected = {}
    items = data.get("items", []) if isinstance(data, dict) else []
    for item in items:
        gid = item.get("external_id") or item.get("bggid") or item.get("id")
        try:
            gid = int(gid)
        except (TypeError, ValueError):
            continue
        for p in _walk(item.get("prices", [])):
            price = _num(p.get("price")) or _num(p.get("product"))
            if not price or price < 3 or str(p.get("stock", "Y")).upper() in ("N", "NO", "FALSE", "0"):
                continue
            collected.setdefault(gid, []).append((price, p.get("link") or p.get("url") or ""))
    out = {}
    for gid, offers in collected.items():
        offers.sort()
        out[gid] = {"min": offers[0][0], "median": round(median(o[0] for o in offers), 2),
                    "count": len(offers), "link": offers[0][1]}
    return out


def note(entry):
    return (f"brettspielpreise.de: günstigster von {entry['count']} Shop-Preisen inkl. Versand "
            f"(Median {entry['median']:.2f} €) – {entry['link']}")


def raw(bgg_id):
    """Rohantwort für die Diagnose."""
    r = http.get(API, params={"eid": str(bgg_id), "sitename": "brettspielscalper", "currency": "EUR",
                              "destination": "DE", "sort": "CHEAP"})
    return r.json()


def fetch(bgg_ids):
    """-> ({bgg_id: eintrag wie parse()}, fehlertext|None). Fragt in Blöcken zu 20 IDs."""
    ids = [i for i in bgg_ids if i > 0]
    out = {}
    for start in range(0, len(ids), 20):
        chunk = ids[start:start + 20]
        try:
            r = http.get(API, params={"eid": ",".join(map(str, chunk)), "sitename": "brettspielscalper",
                                      "currency": "EUR", "destination": "DE", "sort": "CHEAP"})
            if r.status_code != 200:
                return out, f"BoardGamePrices: HTTP {r.status_code}"
            out.update(parse(r.json()))
        except http.Blocked as e:
            return out, f"BoardGamePrices: {e}"
        except ValueError:
            return out, "BoardGamePrices: Antwort ist kein JSON (API geändert?)"
        except Exception as e:
            return out, f"BoardGamePrices: {e}"
    return out, None
