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
        con.execute("INSERT INTO list_items(list_id, rank, bgg_id) VALUES (?,?,?)", (list_id, rank, bgg_id))
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


def replace_offers(con, bgg_id, offers):
    """offers: [dict(ad_id,title,price,negotiable,location,url)] – ersetzt alle Angebote des Spiels."""
    now = time.time()
    con.execute("DELETE FROM offers WHERE bgg_id=?", (bgg_id,))
    for o in offers:
        con.execute(
            "INSERT OR REPLACE INTO offers(ad_id,bgg_id,title,price,negotiable,location,url,seen_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (o["ad_id"], bgg_id, o["title"], o["price"], int(o["negotiable"]), o["location"], o["url"], now),
        )
    con.commit()


def deals(con, list_id, max_ratio):
    """Angebote mit Preis <= max_ratio * Neupreis (nur Spiele mit bekanntem Neupreis)."""
    return con.execute(
        """SELECT o.*, g.name AS game, g.new_price, li.rank, o.price / g.new_price AS ratio
           FROM offers o JOIN games g USING(bgg_id) JOIN list_items li USING(bgg_id)
           WHERE li.list_id=? AND g.new_price > 0 AND o.price <= ? * g.new_price
           ORDER BY ratio""",
        (list_id, max_ratio),
    ).fetchall()


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
