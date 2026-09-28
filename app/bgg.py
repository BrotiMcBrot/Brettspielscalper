"""BGG-Ranglisten aus beliebigen BGG-Browse-/Suchseiten lesen.

Beispiele für die URL einer Liste:
  https://boardgamegeek.com/browse/boardgame                      (Top-Spiele gesamt)
  https://boardgamegeek.com/search/boardgame?sort=rank&advsearch=1&familyids[0]=... (gefilterte Suche)
Jede Seite enthält 100 Zeilen; mehr Seiten werden bei size > 100 nachgeladen.
"""
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from . import http

GAME_HREF = re.compile(r"/boardgame(?:expansion)?/(\d+)")


def page_url(url, page):
    if page == 1:
        return url
    u = urlparse(url)
    if u.path.startswith("/browse/"):
        path = u.path.rstrip("/") + f"/page/{page}"
        return urlunparse(u._replace(path=path))
    q = dict(parse_qsl(u.query, keep_blank_values=True))
    q["page"] = str(page)
    return urlunparse(u._replace(query=urlencode(q)))


def parse_ranking(html):
    """-> [(rank, bgg_id, name, year)]"""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for i, row in enumerate(soup.select("tr[id^=row_]"), 1):
        link = row.select_one("td.collection_objectname a.primary") or row.select_one("a.primary")
        if not link:
            continue
        m = GAME_HREF.search(link.get("href", ""))
        if not m:
            continue
        rank_td = row.select_one("td.collection_rank")
        rank_txt = re.sub(r"\D", "", rank_td.get_text()) if rank_td else ""
        year = row.select_one("span.smallerfont")
        year_m = re.search(r"\d{4}", year.get_text()) if year else None
        items.append((int(rank_txt) if rank_txt else i, int(m.group(1)), link.get_text(strip=True),
                      year_m.group(0) if year_m else None))
    return items


def fetch_ranking(url, size=100):
    items, page = [], 1
    while len(items) < size:
        resp = http.get(page_url(url, page))
        if resp.status_code != 200:
            raise RuntimeError(f"BGG antwortete mit HTTP {resp.status_code} für {resp.url}")
        found = parse_ranking(resp.text)
        if not found:
            if page == 1:
                raise RuntimeError("Keine Spiele auf der BGG-Seite gefunden (Layout geändert oder Bot-Schutz?).")
            break
        items += found
        page += 1
    return items[:size]
