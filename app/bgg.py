"""BGG-Ranglisten aus beliebigen BGG-Browse-/Suchseiten lesen.

Beispiele für die URL einer Liste:
  https://boardgamegeek.com/browse/boardgame                      (Top-Spiele gesamt)
  https://boardgamegeek.com/search/boardgame?sort=rank&advsearch=1&familyids[0]=... (gefilterte Suche)
Jede Seite enthält 100 Zeilen; mehr Seiten werden bei size > 100 nachgeladen.
"""
import csv
import io
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


RANK_COLUMNS = {
    "rank": "Gesamt (alle Brettspiele)", "strategygames_rank": "Strategiespiele", "familygames_rank": "Familienspiele",
    "thematic_rank": "Thematische Spiele (Thematic)", "wargames_rank": "Kriegsspiele", "partygames_rank": "Partyspiele",
    "cgs_rank": "Sammelkartenspiele/Customizable", "abstracts_rank": "Abstrakte Spiele", "childrensgames_rank": "Kinderspiele",
}


def _pick(row, *names):
    for n in names:
        if row.get(n) not in (None, ""):
            return row[n]
    return None


def parse_csv(text, column="rank", size=100):
    """BGG-CSV -> [(rank, id, name, year)]. Versteht zwei Formate:
    - Ranglisten-Export boardgames_ranks.csv (Spalten id, name, rank, familygames_rank …): sortiert nach der gewählten Rangliste
    - eigene Sammlung/Wunschliste (Collection-Export: objectid, objectname, rank, itemtype …): alle Spiele, sortiert nach BGG-Rang
    Trennzeichen (Komma/Semikolon) wird automatisch erkannt."""
    text = text.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(text[:5000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    fields = {f.strip().lower() for f in (reader.fieldnames or [])}
    if not ({"id", "objectid"} & fields and {"name", "objectname", "originalname"} & fields):
        raise ValueError("Unbekanntes CSV-Format – erwartet wird der BGG-Ranglisten-Export (boardgames_ranks.csv) "
                         f"oder ein BGG-Sammlungs-Export. Gefundene Spalten: {', '.join(sorted(fields))[:300]}")
    collection = "objectid" in fields
    rows, seen = [], set()
    for i, raw in enumerate(reader, 1):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if r.get("is_expansion") == "1" or r.get("itemtype") == "expansion" or r.get("subtype") == "boardgameexpansion":
            continue
        gid = _pick(r, "id", "objectid")
        if not (gid or "").isdigit() or gid in seen:
            continue
        name = _pick(r, "name", "objectname", "originalname")
        year = _pick(r, "yearpublished") or None
        rank_col = column if column in r else "rank"
        rank_txt = r.get(rank_col, "")
        if collection:
            rank = int(rank_txt) if rank_txt.isdigit() and int(rank_txt) > 0 else 100000 + i  # ungerankte ans Ende
        else:
            if column not in r:
                raise ValueError(f"Spalte '{column}' fehlt in der CSV.")
            if not rank_txt.isdigit() or int(rank_txt) == 0:
                continue
            rank = int(rank_txt)
        seen.add(gid)
        rows.append((rank, int(gid), name, year))
    rows.sort()
    if collection:  # Position in der eigenen Liste statt riesiger Rangnummern
        rows = [(n, gid, name, year) for n, (_, gid, name, year) in enumerate(rows, 1)]
    return rows[:size]
