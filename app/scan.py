"""Ablauf: Rangliste laden, Angebote je Spiel suchen und speichern. Jede Funktion liefert (Meldungen, Zusammenfassung)."""
from . import bgg, db, geizhals, kleinanzeigen, reference
from .matching import base_name, contains, normalize, tokens
from .http import Blocked

ESTIMATE = "Kleinanzeigen-Schätzung"
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


def apply_reference_prices(con, list_id):
    """Richtwerte für Spiele ohne Preis (oder mit bloßer Kleinanzeigen-Schätzung) eintragen. -> Anzahl"""
    ref, n = reference.load(), 0
    for g in db.games_of_list(con, list_id):
        r = ref.get(normalize(g["name"]))
        note = g["price_note"] or ""
        if r and r["price"] and (not g["new_price"] or note.startswith(ESTIMATE)):
            db.set_price(con, g["bgg_id"], r["price"], reference.NOTE)
            n += 1
    return n


def search_plan(games):
    """Pro Spiel: Suchnamen + Ausschlüsse. Enthält ein anderes Spiel der Liste den eigenen Namen
    (Gloomhaven ⊂ Gloomhaven Pranken des Löwen, Pandemic Legacy Season 1/2 …), wird dessen Name ausgeschlossen."""
    ref = reference.load()
    plan = {}
    for g in games:
        r = ref.get(normalize(g["name"]), {})
        own = [n.strip() for n in (g["search_name"] or "").split("|") if n.strip()] or r.get("aliases") or [base_name(g["name"])]
        excl = [e.strip() for e in (g["exclude"] or "").split(",") if e.strip()] + r.get("exclude", [])
        plan[g["bgg_id"]] = (own, excl)
    for gid, (own, excl) in plan.items():
        for other, (o_names, _) in plan.items():
            if other == gid:
                continue
            for on in o_names:
                ot = tokens(on)
                if any(len(ot) > len(tokens(n)) and contains(ot, tokens(n)) for n in own):
                    excl.append(on)
    return plan


def scan_offers(con, list_id, progress=None):
    games = _games(con, list_id)
    ref_n = apply_reference_prices(con, list_id)
    games = db.games_of_list(con, list_id)  # neu lesen (Preise können sich geändert haben)
    plan = search_plan(games)
    errors, raw_total, offers_total, with_offers, estimated = [], 0, 0, 0, 0
    for i, g in enumerate(games, 1):
        try:
            names, excl = plan[g["bgg_id"]]
            offers, raw = kleinanzeigen.find_offers(names, excl)
            db.replace_offers(con, g["bgg_id"], offers)
            # Letzter Ausweg: Neupreis aus NEU/OVP-Anzeigen schätzen (nur ohne manuellen Preis / Richtwert)
            note = g["price_note"] or ""
            if not g["new_price"] or note.startswith(ESTIMATE):
                est, n = kleinanzeigen.estimate_new_price(offers)
                if est:
                    db.set_price(con, g["bgg_id"], est, f"{ESTIMATE} (Median aus {n} NEU/OVP-Anzeigen)")
                    estimated += 1
                elif note.startswith(ESTIMATE):  # alte, evtl. falsche Schätzung nicht stehen lassen
                    con.execute("UPDATE games SET new_price=NULL, price_note=NULL WHERE bgg_id=?", (g["bgg_id"],))
                    con.commit()
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
    return errors, (f"{len(games)} Spiele durchsucht, {raw_total} Anzeigen gelesen, {offers_total} passende Angebote "
                    f"für {with_offers} Spiele. Neupreise: {ref_n} Richtwerte, {estimated} aus NEU/OVP-Anzeigen geschätzt.")


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
