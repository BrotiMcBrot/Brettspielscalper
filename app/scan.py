"""Ablauf: Rangliste laden, Angebote je Spiel suchen und speichern. Jede Funktion liefert (Meldungen, Zusammenfassung)."""
from . import bgg, db, geizhals, kleinanzeigen
from .http import Blocked

BLOCKED_HINT = "Nichts von der Seite lesbar (Bot-Schutz oder geändertes Layout?) – bitte `python -m app check` ausführen."


def refresh_list(con, list_id):
    row = con.execute("SELECT * FROM lists WHERE id=?", (list_id,)).fetchone()
    if not row["bgg_url"]:
        raise RuntimeError("Diese Liste hat keine BGG-URL (manuelle Liste) – nichts zu laden.")
    items = bgg.fetch_ranking(row["bgg_url"], row["size"])
    db.save_ranking(con, list_id, items)
    return [], f"{len(items)} Spiele von BGG geladen."


def _games(con, list_id):
    games = db.games_of_list(con, list_id)
    if not games:
        raise RuntimeError("Die Liste enthält noch keine Spiele – zuerst „1. BGG laden“ (oder Spiele manuell eintragen).")
    return games


def scan_offers(con, list_id, progress=None):
    games, errors, raw_total, offers_total, with_offers = _games(con, list_id), [], 0, 0, 0
    for i, g in enumerate(games, 1):
        try:
            offers, raw = kleinanzeigen.find_offers(g["name"], g["search_name"])
            db.replace_offers(con, g["bgg_id"], offers)
            raw_total += raw
            offers_total += len(offers)
            with_offers += bool(offers)
        except Blocked as e:
            errors.insert(0, f"{e} Abbruch. Später erneut versuchen.")
            break
        except Exception as e:  # ein Fehler soll den Gesamtlauf nicht abbrechen
            errors.append(f"{g['name']}: {e}")
        if progress:
            progress(i, len(games), g["name"])
    if not raw_total and not errors:
        errors.insert(0, BLOCKED_HINT)
    return errors, f"{len(games)} Spiele durchsucht, {raw_total} Anzeigen gelesen, {offers_total} passende Angebote für {with_offers} Spiele."


def fetch_prices(con, list_id, progress=None, overwrite=False):
    """Neupreise von Geizhals holen. Manuell eingetragene Preise bleiben unangetastet (außer overwrite)."""
    games, errors, raw_total, found_n, skipped = _games(con, list_id), [], 0, 0, 0
    for i, g in enumerate(games, 1):
        if g["new_price"] and not overwrite:
            skipped += 1
            continue
        try:
            found, raw = geizhals.find_price(g["name"], g["search_name"])
            raw_total += raw
            if found:
                db.set_price(con, g["bgg_id"], found[0], found[1])
                found_n += 1
            else:
                errors.append(f"Kein Treffer: {g['name']} ({raw} Produkte gelesen)")
        except Blocked as e:
            errors.insert(0, f"{e} Abbruch – trage Neupreise auf der Seite „Neupreise“ manuell ein (oder Import Name;Preis).")
            break
        except Exception as e:
            errors.append(f"{g['name']}: {e}")
        if progress:
            progress(i, len(games), g["name"])
    if not raw_total and not errors and skipped < len(games):
        errors.insert(0, BLOCKED_HINT)
    return errors, f"{found_n} Neupreise gefunden, {skipped} schon vorhanden, {len(games) - skipped - found_n} ohne Preis."
