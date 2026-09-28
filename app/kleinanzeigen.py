"""Kleinanzeigen.de-Suche: Angebote zu einem Spielnamen holen und auf echte Treffer filtern."""
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from . import http
from .matching import matches

BASE = "https://www.kleinanzeigen.de"
MIN_PRICE = 3.0  # darunter meist Platzhalter / Zubehör


def search_url(query):
    return f"{BASE}/s-suchanfrage.html?keywords={quote_plus(query)}"


def parse_price(text):
    """'1.234,50 € VB' -> (1234.5, True); 'Zu verschenken' / 'VB' ohne Zahl -> (None, ...)"""
    text = text or ""
    m = re.search(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?\s*€", text)
    if not m:
        return None, "VB" in text
    value = float(m.group(1).replace(".", "") + "." + (m.group(2) or "0"))
    return value, "VB" in text


def parse_results(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for art in soup.select("article[data-adid]"):
        link = art.select_one("h2 a, a.ellipsis, a[href*='/s-anzeige/']")
        price_el = art.select_one("[class*='price-shipping--price'], p[class*='price']")
        if not link:
            continue
        price, vb = parse_price(price_el.get_text(" ", strip=True) if price_el else "")
        loc = art.select_one("[class*='aditem-main--top--left']")
        href = art.get("data-href") or link.get("href", "")
        out.append({
            "ad_id": art["data-adid"],
            "title": link.get_text(" ", strip=True),
            "price": price,
            "negotiable": vb,
            "location": loc.get_text(" ", strip=True) if loc else "",
            "url": urljoin(BASE, href),
        })
    return out


def find_offers(game_name, search_name=None):
    """-> (passende Angebote, Anzahl roh gelesener Anzeigen). search_name (z.B. deutscher Titel) hat Vorrang."""
    name = search_name or game_name
    resp = http.get(search_url(name))
    if resp.status_code != 200:
        raise RuntimeError(f"Kleinanzeigen: HTTP {resp.status_code} für '{name}'")
    raw = parse_results(resp.text)
    return [o for o in raw if o["price"] is not None and o["price"] >= MIN_PRICE and matches(name, o["title"])], len(raw)
