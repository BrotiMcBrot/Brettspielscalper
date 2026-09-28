"""Kleinanzeigen.de-Suche: Angebote zu einem Spielnamen holen und auf echte Treffer filtern."""
import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from . import http
from .matching import matches, normalize, tokens

BASE = "https://www.kleinanzeigen.de"
MIN_PRICE = 3.0  # darunter meist Platzhalter / Zubehör


GAMES_CATEGORY = "23"   # Kleinanzeigen-Kategorie der Brettspiel-Anzeigen (steht in jeder Anzeigen-URL: …/<id>-23-<ort>)


def search_url(query, category=None):
    if category:
        slug = "-".join(normalize(query).split())
        return f"{BASE}/s-{slug}/k0c{category}"
    return f"{BASE}/s-suchanfrage.html?keywords={quote_plus(query)}"


def ad_category(url):
    m = re.search(r"/\d+-(\d+)-\d+/?$", url)
    return m.group(1) if m else None


def parse_price(text):
    """'1.234,50 € VB' -> (1234.5, True); 'Zu verschenken' / 'VB' ohne Zahl -> (None, ...)"""
    text = text or ""
    m = re.search(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?\s*€", text)
    if not m:
        return None, "VB" in text
    value = float(m.group(1).replace(".", "") + "." + (m.group(2) or "0"))
    return value, "VB" in text


SHIPPING = re.compile(r"versand", re.I)


def _slug_title(href):
    m = re.search(r"/s-anzeige/([^/]+)/", href)
    return m.group(1).replace("-", " ") if m else ""


def _price_from_text(text):
    """Erster Euro-Betrag im Anzeigentext, der nicht zum Versand gehört."""
    for m in re.finditer(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?\s*€", text):
        if not SHIPPING.search(text[max(0, m.start() - 15):m.start()]):
            return parse_price(text[m.start():m.end() + 4])
    return None, "VB" in text


def parse_results(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for art in soup.select("article[data-adid]"):
        links = [a for a in art.select("a[href*='/s-anzeige/']") if a.get_text(strip=True)]
        if not art.select_one("a[href*='/s-anzeige/']") and not art.get("data-href"):
            continue
        href = art.get("data-href") or art.select_one("a[href*='/s-anzeige/']")["href"]
        # Titel: h2, sonst längster Linktext (Bildzähler wie "4" sind nur Ziffern), sonst aus der URL
        h2 = art.select_one("h2")
        title = h2.get_text(" ", strip=True) if h2 else ""
        if not title or title.isdigit():
            title = max((a.get_text(" ", strip=True) for a in links), key=len, default="")
        if not title or title.isdigit():
            title = _slug_title(href)
        price_el = art.select_one("[class*='price-shipping--price'], [class*='price']")
        price, vb = parse_price(price_el.get_text(" ", strip=True)) if price_el else (None, False)
        if price is None:
            price, vb2 = _price_from_text(art.get_text(" ", strip=True))
            vb = vb or vb2
        loc = art.select_one("[class*='aditem-main--top--left']")
        out.append({
            "ad_id": art["data-adid"],
            "title": title,
            "price": price,
            "negotiable": vb,
            "location": loc.get_text(" ", strip=True) if loc else "",
            "url": urljoin(BASE, href),
            "category": ad_category(href),
        })
    return out


def _search(query):
    """Erst in der Spiele-Kategorie suchen; liefert die nichts (z.B. anderes URL-Schema), allgemein suchen."""
    resp = http.get(search_url(query, GAMES_CATEGORY))
    raw = parse_results(resp.text) if resp.status_code == 200 else []
    if not raw:
        resp = http.get(search_url(query))
        if resp.status_code != 200:
            raise RuntimeError(f"Kleinanzeigen: HTTP {resp.status_code} für '{query}'")
        raw = parse_results(resp.text)
    return raw


def find_offers(names, exclude=(), need_context=False):
    """names: Suchnamen (z.B. deutscher + englischer Titel). -> (passende Angebote, Anzahl roh gelesener Anzeigen)"""
    found, raw_n = {}, 0
    for name in names:
        raw = _search(name)
        raw_n += len(raw)
        for o in raw:
            if (o["price"] is not None and o["price"] >= MIN_PRICE
                    and o["category"] in (None, GAMES_CATEGORY) and matches(name, o["title"], exclude, need_context)):
                found[o["ad_id"]] = o
    return list(found.values()), raw_n


NEW_WORDS = {"neu", "ovp", "eingeschweisst", "eingeschweist", "sealed", "ungespielt", "originalverpackt", "new"}
USED_WORDS = {"gebraucht", "gespielt", "bespielt"}


def estimate_new_price(offers):
    """Neupreis-Schätzung: Median der Angebote, die sich als neu/OVP/ungespielt ausweisen (mind. 2 nötig)."""
    from statistics import median
    prices = []
    for o in offers:
        t = set(tokens(o["title"]))
        if t & NEW_WORDS and not t & USED_WORDS:
            prices.append(o["price"])
    if len(prices) < 3:
        return None, len(prices)
    # Ausreißer (Sammlungen, Tippfehler) raus: nicht mehr als das 2,5-fache des Medians aller Angebote
    cap = 2.5 * median(o["price"] for o in offers)
    prices = [p for p in prices if p <= cap]
    return (round(median(prices), 2), len(prices)) if len(prices) >= 3 else (None, len(prices))
