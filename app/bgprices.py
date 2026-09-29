"""BoardGamePrices (boardgameprices.co.uk) – Preisvergleich speziell für Brettspiele mit öffentlicher API.

Abfrage per BGG-ID, Lieferziel Deutschland, Preise in EUR. EXPERIMENTELL: Aufbau der Antwort wurde nicht
live geprüft; der Parser sucht daher tolerant nach Preis-Einträgen. „Diagnose“ zeigt, ob es funktioniert."""
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
    """-> {bgg_id: (preis, notiz)} – günstigster lieferbarer Preis je Spiel."""
    out = {}
    items = data.get("items", []) if isinstance(data, dict) else []
    for item in items:
        gid = item.get("external_id") or item.get("bggid") or item.get("id")
        try:
            gid = int(gid)
        except (TypeError, ValueError):
            continue
        best = None
        for p in _walk(item.get("prices", [])):
            # "product" = reiner Artikelpreis, "price" evtl. inkl. Versand – den Artikelpreis bevorzugen
            price = _num(p.get("product")) or _num(p.get("price"))
            if not price or str(p.get("stock", "Y")).upper() in ("N", "NO", "FALSE", "0"):
                continue
            if best is None or price < best[0]:
                store = (p.get("store") or p.get("shop") or p.get("storename") or p.get("store_name")
                         or p.get("storeName") or p.get("merchant") or "")
                store = store.get("name", "") if isinstance(store, dict) else store
                best = (price, f"BoardGamePrices: {store} – {p.get('link') or p.get('url') or ''}".strip(" –"))
        if best:
            out[gid] = best
    return out


def raw(bgg_id):
    """Rohantwort für die Diagnose."""
    r = http.get(API, params={"eid": str(bgg_id), "sitename": "brettspielscalper", "currency": "EUR",
                              "destination": "DE", "sort": "CHEAP"})
    return r.json()


def fetch(bgg_ids):
    """-> ({bgg_id: (preis, notiz)}, fehlertext|None). Fragt in Blöcken zu 20 IDs."""
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
