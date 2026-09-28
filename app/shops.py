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


def load():
    with open(PATH, encoding="utf-8") as f:
        return [r for r in csv.DictReader((l for l in f if not l.startswith("#")), delimiter=";")
                if (r.get("active") or "1").strip() == "1"]


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


def find_price(names, shops=None, blocked=None, exclude=()):
    """Günstigster Neupreis über alle Shops. names = Suchnamen. -> (preis, notiz) oder None; Fehlertexte in blocked."""
    shops = shops if shops is not None else load()
    blocked = blocked if blocked is not None else {}
    best = None
    for shop in shops:
        if shop["name"] in blocked:
            continue
        for name in names:
            url = shop["search_url"].replace("{q}", quote_plus(name))
            try:
                resp = http.get(url)
                if resp.status_code != 200:
                    break
                # manche Shops leiten bei eindeutigem Treffer direkt auf die Produktseite
                price, pname = product_price(resp.text)
                candidates = [(resp.url, price, pname)] if price and matches(name, pname or "", exclude) else []
                for link in product_links(resp.text, resp.url, name)[:2] if not candidates else []:
                    p, pn = product_price(http.get(link).text)
                    if p and matches(name, pn or name, exclude):
                        candidates.append((link, p, pn))
            except http.Blocked as e:
                blocked[shop["name"]] = str(e)
                break
            except requests.RequestException as e:  # nicht erreichbar → Shop für diesen Lauf überspringen
                blocked[shop["name"]] = f"{shop['name']} nicht erreichbar ({type(e).__name__})"
                break
            for link, p, pn in candidates:
                if p >= 5 and (best is None or p < best[0]):
                    best = (p, f"Shop {shop['name']}: {pn or name} – {link}")
            if candidates:
                break  # erster Suchname mit Treffer reicht für diesen Shop
    return best
