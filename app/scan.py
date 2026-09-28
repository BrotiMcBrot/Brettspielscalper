"""Ablauf: Rangliste laden, Angebote je Spiel suchen und speichern."""
from . import bgg, db, geizhals, kleinanzeigen


def refresh_list(con, list_id):
    row = con.execute("SELECT * FROM lists WHERE id=?", (list_id,)).fetchone()
    db.save_ranking(con, list_id, bgg.fetch_ranking(row["bgg_url"], row["size"]))


def scan_offers(con, list_id, progress=None, only_priced=False):
    games = db.games_of_list(con, list_id)
    errors = []
    for i, g in enumerate(games, 1):
        if only_priced and not g["new_price"]:
            continue
        try:
            db.replace_offers(con, g["bgg_id"], kleinanzeigen.find_offers(g["name"], g["search_name"]))
        except Exception as e:  # ein Fehler soll den Gesamtlauf nicht abbrechen
            errors.append(f"{g['name']}: {e}")
        if progress:
            progress(i, len(games), g["name"])
    return errors


def fetch_prices(con, list_id, progress=None, overwrite=False):
    """Neupreise von Geizhals holen. Manuell eingetragene Preise bleiben unangetastet (außer overwrite)."""
    games = db.games_of_list(con, list_id)
    errors, missing = [], []
    for i, g in enumerate(games, 1):
        if g["new_price"] and not overwrite:
            continue
        try:
            found = geizhals.find_price(g["name"], g["search_name"])
            if found:
                db.set_price(con, g["bgg_id"], found[0], found[1])
            else:
                missing.append(g["name"])
        except Exception as e:
            errors.append(f"{g['name']}: {e}")
        if progress:
            progress(i, len(games), g["name"])
    return errors, missing
