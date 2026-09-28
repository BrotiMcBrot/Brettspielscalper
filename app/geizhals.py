"""Neupreis von Geizhals.de: günstigster aktueller Preis des passenden Produkts (Suche per Spielname)."""
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from . import http
from .matching import matches

BASE = "https://geizhals.de"
PRODUCT_HREF = re.compile(r"-a\d+\.html")   # Geizhals-Produktseiten enden auf -a<ID>.html
PRICE = re.compile(r"€\s*(\d{1,3}(?:\.\d{3})*,\d{2})|(\d{1,3}(?:\.\d{3})*,\d{2})\s*€")


def search_url(query):
    return f"{BASE}/?fs={quote_plus(query)}&hloc=de"


def _to_float(s):
    return float(s.replace(".", "").replace(",", "."))


def parse_results(html):
    """-> [{name, price, url}] – bewusst layout-tolerant: pro Produktlink den umgebenden Block nach einem Preis absuchen."""
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=PRODUCT_HREF):
        url = urljoin(BASE, a["href"].split("#")[0])
        name = a.get_text(" ", strip=True)
        if url in seen or not name:
            continue
        block = a
        for _ in range(5):  # bis zu 5 Ebenen hoch, bis ein Preis im Block steht
            block = block.parent
            if block is None:
                break
            m = PRICE.search(block.get_text(" ", strip=True))
            if m:
                seen.add(url)
                out.append({"name": name, "price": _to_float(m.group(1) or m.group(2)), "url": url})
                break
    return out


def find_price(game_name, search_name=None):
    """-> (preis, notiz) oder None, wenn kein passendes Produkt gefunden wurde."""
    name = search_name or game_name
    resp = http.get(search_url(name))
    if resp.status_code != 200:
        raise RuntimeError(f"Geizhals: HTTP {resp.status_code} für '{name}'")
    hits = [r for r in parse_results(resp.text) if r["price"] >= 3 and matches(name, r["name"])]
    if not hits:
        return None
    best = min(hits, key=lambda r: r["price"])
    return best["price"], f"Geizhals: {best['name']} – {best['url']}"
