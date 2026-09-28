"""eBay.de über die offizielle Browse-API (kostenloser Entwickler-Zugang nötig, siehe README).

Zugangsdaten als Umgebungsvariablen EBAY_CLIENT_ID / EBAY_CLIENT_SECRET
oder in data/ebay.json: {"client_id": "...", "client_secret": "..."}.
"""
import base64
import json
import os
import time

import requests

from .matching import matches

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
CONFIG = os.path.join(os.path.dirname(__file__), "..", "data", "ebay.json")
_token = {"value": None, "exp": 0}


def credentials():
    cid, secret = os.environ.get("EBAY_CLIENT_ID"), os.environ.get("EBAY_CLIENT_SECRET")
    if not (cid and secret) and os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        cid, secret = cfg.get("client_id"), cfg.get("client_secret")
    return (cid, secret) if cid and secret else None


def configured():
    return credentials() is not None


def _get_token():
    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    cid, secret = credentials()
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    r = requests.post(TOKEN_URL, timeout=25, headers={"Authorization": f"Basic {auth}",
                      "Content-Type": "application/x-www-form-urlencoded"},
                      data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"})
    if r.status_code != 200:
        raise RuntimeError(f"eBay-Anmeldung fehlgeschlagen (HTTP {r.status_code}) – Client-ID/Secret prüfen.")
    data = r.json()
    _token.update(value=data["access_token"], exp=time.time() + data.get("expires_in", 7200))
    return _token["value"]


def parse_items(data):
    out = []
    for it in data.get("itemSummaries", []):
        price = (it.get("currentBidPrice") if "AUCTION" in it.get("buyingOptions", []) and "FIXED_PRICE" not in it.get("buyingOptions", [])
                 else it.get("price")) or it.get("price") or {}
        if price.get("currency") != "EUR" or not price.get("value"):
            continue
        loc = it.get("itemLocation") or {}
        out.append({
            "ad_id": "ebay:" + it["itemId"],
            "title": it.get("title", ""),
            "price": float(price["value"]),
            "negotiable": "BEST_OFFER" in it.get("buyingOptions", []),
            "auction": "AUCTION" in it.get("buyingOptions", []) and "FIXED_PRICE" not in it.get("buyingOptions", []),
            "location": " ".join(x for x in (loc.get("postalCode"), loc.get("city")) if x),
            "url": it.get("itemWebUrl", ""),
            "condition": it.get("condition", ""),
        })
    return out


def find_offers(names, exclude=(), need_context=False):
    """Gebrauchte/neue Angebote auf eBay.de (Artikelstandort Deutschland). -> (passende Angebote, Anzahl gelesen)"""
    headers = {"Authorization": f"Bearer {_get_token()}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_DE",
               "Accept-Language": "de-DE"}
    found, raw_n = {}, 0
    for name in names:
        r = requests.get(SEARCH_URL, headers=headers, timeout=25, params={
            "q": name, "limit": 50, "filter": "itemLocationCountry:DE,priceCurrency:EUR"})
        if r.status_code == 429:
            raise RuntimeError("eBay: Tageslimit der API erreicht.")
        if r.status_code != 200:
            raise RuntimeError(f"eBay: HTTP {r.status_code} für '{name}'")
        items = parse_items(r.json())
        raw_n += len(items)
        for o in items:
            if o["price"] >= 3 and matches(name, o["title"], exclude, need_context):
                found[o["ad_id"]] = o
        time.sleep(0.3)
    return list(found.values()), raw_n
