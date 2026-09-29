"""Neupreise aus Online-Shops – generisch, ohne shop-spezifischen Parser.

Ablauf je Shop (Liste in app/shops.csv, beliebig erweiterbar):
 1. Suchseite abrufen ({q} in der URL wird durch den Spielnamen ersetzt)
 2. Produktlinks finden, deren Linktext zum Spielnamen passt
 3. Produktseite abrufen und den Preis aus den strukturierten Produktdaten lesen
    (schema.org JSON-LD "Product/Offer", itemprop="price" oder og/product:price-Metatags) –
    das liefern praktisch alle Shop-Systeme (Shopware, Shopify, WooCommerce, JTL …) für Google.
Blockiert ein Shop (Cloudflare o.ä.), wird er für den Rest des Laufs übersprungen.
"""
import csv
import json
import os
import re
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import http
from .matching import matches

PATH = os.path.join(os.path.dirname(__file__), "shops.csv")
PRICE_RE = re.compile(r"\d+(?:[.,]\d{1,2})?")


CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "shop_patterns.json")
# Übliche Such-Adressen der verbreiteten Shop-Systeme (Shopware 5/6, JTL, WooCommerce, Magento, PrestaShop …)
PATTERNS = ["/search?sSearch={q}", "/search?search={q}", "/search?q={q}", "/suche?q={q}", "/search?query={q}",
            "/navi.php?qs={q}", "/?s={q}&post_type=product", "/catalogsearch/result/?q={q}", "/suche?search={q}",
            "/recherche?search_query={q}", "/search/?text={q}", "/de/search?q={q}"]
PROBE_NAMES = ["Azul", "Carcassonne"]


def load(kind=None):
    """Shops aus app/shops.csv; kind='new' (Neupreise) oder 'used' (Gebraucht-Angebote)."""
    with open(PATH, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader((l for l in f if not l.startswith("#")), delimiter=";")
                if (r.get("active") or "1").strip() == "1"]
    return [r for r in rows if kind is None or (r.get("type") or "new").strip() == kind]


def _cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def search_url(shop):
    """Such-URL mit {q}. Bei 'auto:https://domain' wird das Muster einmal ermittelt und gemerkt (data/shop_patterns.json).
    -> URL oder None, wenn kein Muster funktioniert."""
    url = shop["search_url"].strip()
    if not url.startswith("auto:"):
        return url
    base = url[5:].rstrip("/")
    cache = _cache()
    if base in cache:
        return cache[base]
    found = None
    for pattern in PATTERNS:
        cand = base + pattern
        resp = http.get(cand.replace("{q}", quote_plus(PROBE_NAMES[0])))  # Blocked fliegt hier direkt raus
        if resp.status_code == 200 and (product_links(resp.text, resp.url, PROBE_NAMES[0])
                                        or matches(PROBE_NAMES[0], product_price(resp.text)[1] or "")):
            found = cand
            break
    cache[base] = found
    os.makedirs(os.path.dirname(os.path.abspath(CACHE)), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)
    return found


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("\xa0", "")
    if "," in s and "." in s:  # 1.234,56
        s = s.replace(".", "").replace(",", ".")
    s = s.replace(",", ".")
    m = PRICE_RE.search(s)
    return float(m.group(0)) if m else None


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def product_price(html):
    """-> (preis, name) aus strukturierten Daten einer Produktseite, oder (None, None)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except ValueError:
            continue
        for node in _walk(data):
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if "Product" in types or "ProductGroup" in types:
                prices = []
                for off in _walk(node.get("offers") or []):
                    for key in ("price", "lowPrice"):
                        p = _num(off.get(key))
                        if p:
                            prices.append(p)
                if prices:
                    return min(prices), node.get("name")
    for sel in ('[itemprop="price"]', 'meta[property="product:price:amount"]', 'meta[property="og:price:amount"]'):
        el = soup.select_one(sel)
        if el is not None:
            p = _num(el.get("content") or el.get_text())
            if p:
                title = soup.select_one('meta[property="og:title"]')
                return p, title.get("content") if title else None
    return None, None


def product_links(html, base_url, name):
    """Links auf der Suchseite, deren Text (oder title) zum Spielnamen passt – Duplikate raus, max. 3."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base_url).netloc
    out = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True) or a.get("title") or ""
        url = urljoin(base_url, a["href"].split("#")[0])
        if urlparse(url).netloc != host or url in out or url == base_url:
            continue
        if matches(name, text):
            out.append(url)
        if len(out) >= 3:
            break
    return out


def shop_hit(shop, names, exclude=(), blocked=None):
    """Günstigster passender Artikel eines Shops. -> (preis, produktname, url) oder None.
    Blockiert der Shop / ist er nicht erreichbar, wird er in blocked eingetragen."""
    blocked = blocked if blocked is not None else {}
    try:
        template = search_url(shop)
        if not template:
            blocked[shop["name"]] = f"{shop['name']}: keine funktionierende Such-Adresse gefunden"
            return None
        for name in names:
            resp = http.get(template.replace("{q}", quote_plus(name)))
            if resp.status_code != 200:
                break
            # manche Shops leiten bei eindeutigem Treffer direkt auf die Produktseite
            price, pname = product_price(resp.text)
            hits = [(price, pname, resp.url)] if price and matches(name, pname or "", exclude) else []
            for link in product_links(resp.text, resp.url, name)[:2] if not hits else []:
                p, pn = product_price(http.get(link).text)
                if p and matches(name, pn or name, exclude):
                    hits.append((p, pn or name, link))
            hits = [h for h in hits if h[0] >= 3]
            if hits:
                return min(hits)
    except http.Blocked as e:
        blocked[shop["name"]] = str(e)
    except requests.RequestException as e:  # nicht erreichbar → Shop für diesen Lauf überspringen
        blocked[shop["name"]] = f"{shop['name']} nicht erreichbar ({type(e).__name__})"
    return None


def all_prices(names, shops=None, blocked=None, exclude=()):
    """-> [(preis, shopname, produktname, url)] aller Shops mit Treffer, günstigster zuerst."""
    shops = shops if shops is not None else load("new")
    blocked = blocked if blocked is not None else {}
    out = []
    for shop in shops:
        if shop["name"] in blocked:
            continue
        hit = shop_hit(shop, names, exclude, blocked)
        if hit:
            out.append((hit[0], shop["name"], hit[1], hit[2]))
    return sorted(out)


def find_price(names, shops=None, blocked=None, exclude=()):
    """Günstigster Neupreis über alle Shops. -> (preis, notiz) oder None; Fehlertexte in blocked."""
    hits = all_prices(names, shops, blocked, exclude)
    if not hits:
        return None
    p, shop, pname, url = hits[0]
    return p, f"Shop {shop}: {pname} – {url}"


def used_offers(names, exclude=(), blocked=None, shops=None):
    """Gebraucht-Händler mit Festpreis (medimops, rebuy …) -> Angebote im selben Format wie Kleinanzeigen."""
    out = []
    for shop in shops if shops is not None else load("used"):
        if blocked is not None and shop["name"] in blocked:
            continue
        hit = shop_hit(shop, names, exclude, blocked)
        if hit:
            out.append({"ad_id": f"{shop['name']}:{hit[2]}", "title": f"{hit[1]} ({shop['name']}, gebraucht)",
                        "price": hit[0], "negotiable": False, "location": shop["name"], "url": hit[2],
                        "source": "used"})
    return out
