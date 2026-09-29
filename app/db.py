"""SQLite-Speicher: Listen, Spiele, Neupreise und Kleinanzeigen-Angebote."""
import os
import sqlite3
import time

DB_PATH = os.environ.get("BSS_DB", os.path.join(os.path.dirname(__file__), "..", "data", "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    bgg_url TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 100,
    updated_at REAL
);
CREATE TABLE IF NOT EXISTS games (
    bgg_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    year TEXT,
    search_name TEXT,          -- z.B. deutscher Titel, falls abweichend
    new_price REAL,            -- Neupreis in EUR
    price_note TEXT,           -- Quelle / Notiz zum Neupreis
    price_updated REAL
);
CREATE TABLE IF NOT EXISTS list_items (
    list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,
    bgg_id INTEGER NOT NULL REFERENCES games(bgg_id),
    PRIMARY KEY (list_id, bgg_id)
);
CREATE TABLE IF NOT EXISTS offers (
    ad_id TEXT PRIMARY KEY,
    bgg_id INTEGER NOT NULL REFERENCES games(bgg_id),
    title TEXT NOT NULL,
    price REAL NOT NULL,
    negotiable INTEGER NOT NULL DEFAULT 0,
    location TEXT,
    url TEXT NOT NULL,
    seen_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS offers_game ON offers(bgg_id);
"""


def connect():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(games)")}
    if "exclude" not in cols:  # Migration älterer Datenbanken
        con.execute("ALTER TABLE games ADD COLUMN exclude TEXT")
    if "ref_price" not in cols:  # Richtwert (ca. UVP) – Vergleichsbasis für Neuware-Angebote (Shops, mydealz)
        con.execute("ALTER TABLE games ADD COLUMN ref_price REAL")
    ocols = {r[1] for r in con.execute("PRAGMA table_info(offers)")}
    if "source" not in ocols:
        con.execute("ALTER TABLE offers ADD COLUMN source TEXT NOT NULL DEFAULT 'kleinanzeigen'")
    if "auction" not in ocols:
        con.execute("ALTER TABLE offers ADD COLUMN auction INTEGER NOT NULL DEFAULT 0")
    return con


def add_list(con, name, bgg_url, size=100):
    cur = con.execute("INSERT INTO lists(name, bgg_url, size) VALUES (?,?,?)", (name, bgg_url, size))
    con.commit()
    return cur.lastrowid


def save_ranking(con, list_id, items):
    """items: [(rank, bgg_id, name, year)] – ersetzt die Listeneinträge, behält Preise."""
    con.execute("DELETE FROM list_items WHERE list_id=?", (list_id,))
    for rank, bgg_id, name, year in items:
        con.execute(
            "INSERT INTO games(bgg_id, name, year) VALUES (?,?,?) "
            "ON CONFLICT(bgg_id) DO UPDATE SET name=excluded.name, year=excluded.year",
            (bgg_id, name, year),
        )
        con.execute("INSERT OR IGNORE INTO list_items(list_id, rank, bgg_id) VALUES (?,?,?)", (list_id, rank, bgg_id))
    con.execute("UPDATE lists SET updated_at=? WHERE id=?", (time.time(), list_id))
    con.commit()


def set_price(con, bgg_id, price, note=None):
    con.execute(
        "UPDATE games SET new_price=?, price_note=COALESCE(?, price_note), price_updated=? WHERE bgg_id=?",
        (price, note, time.time(), bgg_id),
    )
    con.commit()


def games_of_list(con, list_id):
    return con.execute(
        "SELECT g.*, li.rank FROM list_items li JOIN games g USING(bgg_id) WHERE li.list_id=? ORDER BY li.rank",
        (list_id,),
    ).fetchall()


def replace_offers(con, bgg_id, offers, source="kleinanzeigen"):
    """offers: [dict(ad_id,title,price,negotiable,location,url[,auction])] – ersetzt die Angebote des Spiels aus dieser Quelle."""
    now = time.time()
    con.execute("DELETE FROM offers WHERE bgg_id=? AND source=?", (bgg_id, source))
    for o in offers:
        con.execute(
            "INSERT OR REPLACE INTO offers(ad_id,bgg_id,title,price,negotiable,location,url,seen_at,source,auction) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (o["ad_id"], bgg_id, o["title"], o["price"], int(o["negotiable"]), o["location"], o["url"], now,
             source, int(o.get("auction", False))),
        )
    con.commit()


# Neuware (Shop-Preise, mydealz) mit dem Richtwert (ca. UVP) vergleichen – sonst wäre der Shop-Preis
# gleichzeitig Neupreis und Angebot. Manuelle Neupreise gelten immer.
NEW_GOODS = "('shop', 'mydealz')"
BASE_PRICE = (f"CASE WHEN o.source IN {NEW_GOODS} AND g.price_note NOT IN ('manuell', 'Import') "
              "THEN COALESCE(g.ref_price, g.new_price) ELSE g.new_price END")


def deals(con, list_id, max_ratio, min_ratio=0.0, sources=None):
    """Angebote mit min_ratio * Neupreis <= Preis <= max_ratio * Neupreis (nur Spiele mit bekanntem Neupreis)."""
    return con.execute(
        f"""SELECT * FROM (
             SELECT o.*, g.name AS game, li.rank, {BASE_PRICE} AS new_price, o.price / ({BASE_PRICE}) AS ratio
             FROM offers o JOIN games g USING(bgg_id) JOIN list_items li USING(bgg_id) WHERE li.list_id=?)
           WHERE new_price > 0 AND price <= ? * new_price AND price >= ? * new_price
           ORDER BY ratio""",
        (list_id, max_ratio, min_ratio),
    ).fetchall() if not sources else [r for r in deals(con, list_id, max_ratio, min_ratio) if r["source"] in sources]


def add_manual_games(con, list_id, names):
    """Spiele ohne BGG-Abruf anlegen (negative IDs), z.B. wenn BGG den Zugriff blockiert."""
    rank = (con.execute("SELECT COALESCE(MAX(rank),0) FROM list_items WHERE list_id=?", (list_id,)).fetchone()[0])
    for name in (n.strip() for n in names):
        if not name:
            continue
        rank += 1
        gid = min(0, con.execute("SELECT COALESCE(MIN(bgg_id),0) FROM games").fetchone()[0]) - 1
        con.execute("INSERT INTO games(bgg_id, name) VALUES (?,?)", (gid, name))
        con.execute("INSERT INTO list_items(list_id, rank, bgg_id) VALUES (?,?,?)", (list_id, rank, gid))
    con.commit()


def rename_list(con, list_id, name):
    con.execute("UPDATE lists SET name=? WHERE id=?", (name, list_id))
    con.commit()


def delete_list(con, list_id):
    """Liste löschen. Spiele, die in keiner anderen Liste mehr stehen, samt Angeboten und Preisen mit entfernen."""
    con.execute("DELETE FROM list_items WHERE list_id=?", (list_id,))
    con.execute("DELETE FROM lists WHERE id=?", (list_id,))
    orphans = "SELECT bgg_id FROM games WHERE bgg_id NOT IN (SELECT bgg_id FROM list_items)"
    con.execute(f"DELETE FROM offers WHERE bgg_id IN ({orphans})")
    con.execute(f"DELETE FROM games WHERE bgg_id IN ({orphans})")
    con.commit()
