"""mydealz.de über die offiziellen RSS-Feeds (für Feed-Reader gedacht, kein Scraping).

Es werden die aktuellen Deals der Brettspiel-Gruppe geholt und den Spielen der Liste zugeordnet.
Das sind Neuware-Angebote von Händlern; verglichen wird mit dem mittleren Shop-Preis (Median von brettspielpreise.de)."""
import re
import xml.etree.ElementTree as ET

from . import http
from .kleinanzeigen import parse_price
from .matching import matches

FEEDS = ["https://www.mydealz.de/rss/gruppe/brettspiele",
         "https://www.mydealz.de/rss/gruppe/gesellschaftsspiele",
         "https://www.mydealz.de/rss/search?q=brettspiel"]


def parse_feed(xml_text):
    """-> [{ad_id,title,price,negotiable,location,url}] (nur Deals mit erkennbarem Preis)."""
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        price, merchant = None, ""
        for el in item:  # <pepper:merchant name="Amazon" price="29,99€"/> – Namespace egal
            if el.tag.endswith("merchant"):
                merchant = el.get("name", "")
                price = parse_price((el.get("price") or "").replace("€", " €"))[0]
        if price is None:
            m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*€", title)
            price = float(m.group(1).replace(",", ".")) if m else None
        if price and link:
            out.append({"ad_id": "mydealz:" + (item.findtext("guid") or link), "title": title, "price": price,
                        "negotiable": False, "location": merchant, "url": link})
    return out


def fetch_all():
    """Alle Deals aus den Feeds, ohne Duplikate. -> (deals, fehler)"""
    deals, errors = {}, []
    for url in FEEDS:
        try:
            r = http.get(url)
            if r.status_code == 200:
                for d in parse_feed(r.text):
                    deals[d["ad_id"]] = d
            else:
                errors.append(f"mydealz: HTTP {r.status_code} für {url}")
        except http.Blocked as e:
            return list(deals.values()), [f"mydealz: {e}"]
        except Exception as e:  # kaputter Feed → nächsten probieren
            errors.append(f"mydealz: {url}: {e}")
    return list(deals.values()), ([] if deals else errors)


def for_game(deals, names, exclude=(), need_context=False):
    return [d for d in deals if any(matches(n, d["title"], exclude, need_context) for n in names)]
