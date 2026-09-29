"""Ablauf: Rangliste laden, Angebote je Spiel suchen und speichern. Jede Funktion liefert (Meldungen, Zusammenfassung)."""
from . import bgg, bgprices, db, ebay, kleinanzeigen, mydealz, reference, shops
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


def clear_guessed_prices(con, list_id):
    """Früher mitgelieferte, geschätzte Richtwerte entfernen – Neupreise kommen nur noch aus echten Daten. -> Anzahl"""
    ids = [g["bgg_id"] for g in db.games_of_list(con, list_id) if (g["price_note"] or "").startswith("Richtwert")]
    for gid in ids:
        con.execute("UPDATE games SET new_price=NULL, price_note=NULL WHERE bgg_id=?", (gid,))
    con.commit()
    return len(ids)


def search_plan(games):
    """Pro Spiel: Suchnamen + Ausschlüsse. Enthält ein anderes Spiel der Liste den eigenen Namen
    (Gloomhaven ⊂ Gloomhaven Pranken des Löwen, Pandemic Legacy Season 1/2 …), wird dessen Name ausgeschlossen."""
    ref = reference.load()
    plan = {}
    for g in games:
        r = ref.get(normalize(g["name"]), {})
        own = [n.strip() for n in (g["search_name"] or "").split("|") if n.strip()] or r.get("aliases") or [base_name(g["name"])]
        excl = [e.strip() for e in (g["exclude"] or "").split(",") if e.strip()] + r.get("exclude", [])
        # einwortige Namen ohne Vorgabe sind oft mehrdeutig → Spiel-Wort im Titel verlangen
        ctx = r.get("context", False) or (not r and len(tokens(own[0])) == 1 and len(own[0]) <= 6)
        plan[g["bgg_id"]] = (own, excl, ctx)
    for gid, (own, excl, _) in plan.items():
        for other, (o_names, _, _) in plan.items():
            if other == gid:
                continue
            for on in o_names:
                ot = tokens(on)
                if any(len(ot) > len(tokens(n)) and contains(ot, tokens(n)) for n in own):
                    excl.append(on)
    return plan


def scan_offers(con, list_id, progress=None):
    """Angebote aus allen Quellen: Kleinanzeigen, eBay (falls eingerichtet), mydealz, Gebraucht-Händler."""
    games = _games(con, list_id)
    clear_guessed_prices(con, list_id)
    games = db.games_of_list(con, list_id)  # neu lesen (Preise können sich geändert haben)
    plan = search_plan(games)
    errors, raw_total, offers_total, with_offers, estimated = [], 0, 0, 0, 0
    counts = {"ebay": 0, "mydealz": 0, "used": 0}
    use_ebay = ebay.configured()
    md_deals, md_err = mydealz.fetch_all()
    errors += md_err
    used_shops, used_blocked = shops.load("used"), {}
    ka_ok = True
    for i, g in enumerate(games, 1):
        names, excl, ctx = plan[g["bgg_id"]]
        gid = g["bgg_id"]
        # mydealz: Feed wurde einmal geladen, hier nur zuordnen
        md = mydealz.for_game(md_deals, names, excl, ctx)
        db.replace_offers(con, gid, md, "mydealz")
        counts["mydealz"] += len(md)
        if use_ebay:
            try:
                eoffers, _ = ebay.find_offers(names, excl, ctx)
                db.replace_offers(con, gid, eoffers, "ebay")
                counts["ebay"] += len(eoffers)
            except Exception as e:
                errors.append(f"eBay abgeschaltet für diesen Lauf: {e}")
                use_ebay = False
        if used_shops and len(used_blocked) < len(used_shops):
            used = shops.used_offers(names, excl, used_blocked, used_shops)
            db.replace_offers(con, gid, used, "used")
            counts["used"] += len(used)
        if ka_ok:
            try:
                offers, raw = kleinanzeigen.find_offers(names, excl, ctx)
                db.replace_offers(con, gid, offers)
                # Letzter Ausweg: Neupreis aus NEU/OVP-Anzeigen berechnen (nur ohne Preis aus Shops / manuell)
                note = g["price_note"] or ""
                if not g["new_price"] or note.startswith(ESTIMATE):
                    est, n = kleinanzeigen.estimate_new_price(offers)
                    if est:
                        db.set_price(con, gid, est, f"{ESTIMATE} (Median aus {n} NEU/OVP-Anzeigen)")
                        estimated += 1
                    elif note.startswith(ESTIMATE):  # alte, evtl. falsche Schätzung nicht stehen lassen
                        con.execute("UPDATE games SET new_price=NULL, price_note=NULL WHERE bgg_id=?", (gid,))
                        con.commit()
                raw_total += raw
                offers_total += len(offers)
                with_offers += bool(offers)
            except Blocked as e:
                errors.insert(0, f"{e} Kleinanzeigen für diesen Lauf abgeschaltet.")
                ka_ok = False
            except Exception as e:  # ein Fehler soll den Gesamtlauf nicht abbrechen
                errors.append(f"{g['name']}: {e}")
        if progress:
            progress(i, len(games), g["name"])
    if not raw_total and ka_ok and not errors:
        errors.insert(0, BLOCKED_HINT)
    errors += [f"Gebraucht-Händler übersprungen: {v}" for v in used_blocked.values()]
    ebay_txt = f"eBay {counts['ebay']}" if ebay.configured() else "eBay nicht eingerichtet"
    return errors, (f"{len(games)} Spiele durchsucht. Kleinanzeigen: {raw_total} gelesen, {offers_total} passend "
                    f"({with_offers} Spiele) · {ebay_txt} · mydealz {counts['mydealz']} · Gebraucht-Händler {counts['used']}. "
                    f"{estimated} Neupreise aus NEU/OVP-Anzeigen berechnet (nur wo „2. Neupreise holen“ nichts fand).")


MANUAL_NOTES = ("manuell", "Import")


def fetch_prices(con, list_id, progress=None):
    """Neupreise aus echten Shop-Daten, günstigster gewinnt:
    brettspielpreise.de (BoardGamePrices-API, per BGG-ID) · Online-Shops aus app/shops.csv · ersatzweise eBay-Neuware.
    Manuell eingetragene oder importierte Preise werden nie überschrieben.
    Zusätzlich: ref_price = Median der Shop-Preise (Vergleichsbasis für Neuware-Angebote)."""
    games = _games(con, list_id)
    clear_guessed_prices(con, list_id)
    games = db.games_of_list(con, list_id)
    plan = search_plan(games)
    shop_list = shops.load("new")
    errors, blocked, skipped, missing = [], {}, 0, []
    stats = {"shop": 0, "bgp": 0, "ebay": 0}
    bgp, bgp_err = bgprices.fetch([g["bgg_id"] for g in games])
    if bgp_err:
        errors.append(bgp_err)
    use_ebay = ebay.configured()
    for i, g in enumerate(games, 1):
        gid = g["bgg_id"]
        names, excl, ctx = plan[gid]
        try:
            hits = shops.all_prices(names, shop_list, blocked, excl) if len(blocked) < len(shop_list) else []
            db.replace_offers(con, gid, [{"ad_id": f"shop:{shop}:{gid}", "title": f"{pname} (Neuware)", "price": p,
                                          "negotiable": False, "location": shop, "url": url}
                                         for p, shop, pname, url in hits], "shop")
            if gid in bgp:
                con.execute("UPDATE games SET ref_price=?, ref_source='brettspielpreise.de' WHERE bgg_id=?",
                            (bgp[gid]["median"], gid))
                con.commit()
            if g["new_price"] and (g["price_note"] or "") in MANUAL_NOTES:
                skipped += 1
            else:
                cands = [(p, f"Shop {shop}: {pname} – {url}", "shop") for p, shop, pname, url in hits]
                if gid in bgp:
                    cands.append((bgp[gid]["min"], bgprices.note(bgp[gid]), "bgp"))
                if not cands and use_ebay:
                    try:
                        e = ebay.new_price(names, excl, ctx)
                        if e:
                            cands.append((*e, "ebay"))
                    except Exception as ex:
                        errors.append(f"eBay abgeschaltet für diesen Lauf: {ex}")
                        use_ebay = False
                if cands:
                    price, note, src = min(cands)
                    db.set_price(con, gid, price, note)
                    stats[src] += 1
                else:
                    missing.append(g["name"])
        except Exception as e:
            errors.append(f"{g['name']}: {e}")
        if progress:
            progress(i, len(games), g["name"])
    errors = [f"Shop übersprungen: {v}" for v in blocked.values()] + errors
    if missing:
        errors.append(f"Kein Neupreis gefunden für {len(missing)} Spiele – bitte im Reiter „Neupreise“ eintragen "
                      "(manuell gelistete Spiele haben keine BGG-ID): " + ", ".join(missing[:15])
                      + (" …" if len(missing) > 15 else ""))
    return errors, (f"Neupreise: {stats['bgp']} von brettspielpreise.de, {stats['shop']} aus Shops, {stats['ebay']} von eBay; "
                    f"{skipped} manuelle Preise unverändert, {len(missing)} ohne Treffer.")
