import threading

from flask import Flask, redirect, render_template, request, url_for

from . import db, scan
from .matching import normalize

app = Flask(__name__)
PRESETS = {
    "Top 100 Brettspiele": "https://boardgamegeek.com/browse/boardgame",
}
job = {"running": False, "text": "", "errors": []}
app.jinja_env.globals["job"] = job


def _run(kind, list_id):
    con = db.connect()
    try:
        if kind == "prices":
            errors, missing = scan.fetch_prices(
                con, list_id, lambda i, n, name: job.update(text=f"Geizhals {i}/{n}: {name}"))
            job["errors"] = errors + [f"Kein Treffer: {n}" for n in missing]
        elif kind == "refresh":
            job["text"] = "Lade BGG-Rangliste …"
            scan.refresh_list(con, list_id)
        else:
            job["errors"] = scan.scan_offers(
                con, list_id, lambda i, n, name: job.update(text=f"Kleinanzeigen {i}/{n}: {name}"))
        job["text"] = "Fertig."
    except Exception as e:
        job["text"] = f"Fehler: {e}"
    finally:
        job["running"] = False
        con.close()


def _start(kind, list_id):
    if not job["running"]:
        job.update(running=True, text="Starte …", errors=[])
        threading.Thread(target=_run, args=(kind, list_id), daemon=True).start()


def _current(con):
    lists = con.execute("SELECT * FROM lists ORDER BY id").fetchall()
    lid = request.args.get("list", type=int) or (lists[0]["id"] if lists else None)
    return lists, lid


@app.route("/")
def deals():
    con = db.connect()
    lists, lid = _current(con)
    percent = request.args.get("percent", 50, type=int)
    rows = db.deals(con, lid, percent / 100) if lid else []
    return render_template("deals.html", lists=lists, lid=lid, percent=percent, rows=rows)


@app.route("/prices")
def prices():
    con = db.connect()
    lists, lid = _current(con)
    games = db.games_of_list(con, lid) if lid else []
    games = sorted(games, key=lambda g: (g["new_price"] is not None, g["rank"]))
    return render_template("prices.html", lists=lists, lid=lid, games=games)


@app.post("/prices")
def save_prices():
    con = db.connect()
    for key, val in request.form.items():
        if key.startswith("price_"):
            gid = int(key[6:])
            val = val.replace(",", ".").strip()
            con.execute("UPDATE games SET search_name=? WHERE bgg_id=?",
                        (request.form.get(f"alias_{gid}", "").strip() or None, gid))
            if val:
                db.set_price(con, gid, float(val), "manuell")
            else:
                con.execute("UPDATE games SET new_price=NULL WHERE bgg_id=?", (gid,))
    con.commit()
    return redirect(url_for("prices", list=request.form.get("list")))


@app.post("/prices/bulk")
def bulk_prices():
    """Zeilen 'Spielname;Preis' einfügen – Zuordnung über normalisierten Namen."""
    con = db.connect()
    by_name = {normalize(g["name"]): g["bgg_id"] for g in con.execute("SELECT bgg_id, name FROM games")}
    for line in request.form.get("bulk", "").splitlines():
        if ";" in line:
            name, _, price = line.rpartition(";")
            gid = by_name.get(normalize(name))
            try:
                if gid:
                    db.set_price(con, gid, float(price.replace(",", ".").replace("€", "").strip()), "Import")
            except ValueError:
                pass
    return redirect(url_for("prices", list=request.form.get("list")))


@app.route("/lists", methods=["GET", "POST"])
def lists_page():
    con = db.connect()
    if request.method == "POST":
        db.add_list(con, request.form["name"], request.form["url"], int(request.form.get("size", 100)))
        return redirect(url_for("lists_page"))
    return render_template("lists.html", lists=con.execute("SELECT * FROM lists").fetchall(), presets=PRESETS)


@app.post("/lists/<int:list_id>/<action>")
def list_action(list_id, action):
    if action in ("refresh", "prices", "scan"):
        _start(action, list_id)
    return redirect(request.referrer or url_for("lists_page"))
