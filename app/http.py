"""Gemeinsamer, höflicher HTTP-Client (Browser-UA, Pause zwischen Requests)."""
import time

import requests

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
})
_last = {}


class Blocked(RuntimeError):
    """Die Seite verweigert automatische Abfragen (Cloudflare/Bot-Schutz). Wird nicht umgangen."""


def get(url, delay=1.5, **kw):
    host = requests.utils.urlparse(url).netloc
    wait = _last.get(host, 0) + delay - time.time()
    if wait > 0:
        time.sleep(wait)
    try:
        r = _session.get(url, timeout=25, **kw)
    finally:
        _last[host] = time.time()
    # Ohne charset im Header rät requests ISO-8859-1 → "€" wird zu "â\x82¬" und Preise sind unlesbar
    if "charset" not in r.headers.get("Content-Type", "").lower():
        r.encoding = "utf-8"
    if r.status_code in (403, 429, 503):
        raise Blocked(f"{host} blockiert automatische Abfragen (HTTP {r.status_code}, Bot-Schutz).")
    return r
