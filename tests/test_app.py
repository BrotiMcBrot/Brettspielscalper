import os
import tempfile

os.environ["BSS_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")

from app import bgg, db, kleinanzeigen, matching  # noqa: E402

BGG_HTML = """<table><tr id='row_'><td class='collection_rank'><a name='1'></a>1</td>
<td class='collection_objectname'><div><a href='/boardgame/224517/brass-birmingham' class='primary'>Brass: Birmingham</a>
<span class='smallerfont dull'>(2018)</span></div></td></tr></table>"""

KA_HTML = """<article data-adid="111" data-href="/s-anzeige/brass-birmingham/111-1-1"><h2><a class="ellipsis" href="/s-anzeige/x/111">Brass Birmingham Brettspiel</a></h2>
<p class="aditem-main--middle--price-shipping--price">25 € VB</p><div class="aditem-main--top--left">80331 München</div></article>
<article data-adid="222"><h2><a class="ellipsis" href="/s-anzeige/x/222">Brass Birmingham Erweiterung</a></h2><p class="aditem-main--middle--price-shipping--price">10 €</p></article>
<article data-adid="333"><h2><a class="ellipsis" href="/s-anzeige/x/333">Brass Birmingham</a></h2><p class="aditem-main--middle--price-shipping--price">Zu verschenken</p></article>"""


def test_bgg_parse():
    assert bgg.parse_ranking(BGG_HTML) == [(1, 224517, "Brass: Birmingham", "2018")]


def test_page_url():
    assert bgg.page_url("https://boardgamegeek.com/browse/boardgame", 2).endswith("/browse/boardgame/page/2")
    assert "page=2" in bgg.page_url("https://boardgamegeek.com/search/boardgame?sort=rank", 2)


def test_price():
    assert kleinanzeigen.parse_price("1.234,50 € VB") == (1234.5, True)
    assert kleinanzeigen.parse_price("Zu verschenken")[0] is None


def test_matching_and_offers():
    res = kleinanzeigen.parse_results(KA_HTML)
    assert len(res) == 3 and res[0]["price"] == 25 and res[0]["negotiable"]
    ok = [o["ad_id"] for o in res if o["price"] and matching.matches("Brass Birmingham", o["title"])]
    assert ok == ["111"]


def test_deals_threshold():
    con = db.connect()
    lid = db.add_list(con, "t", "u")
    db.save_ranking(con, lid, [(1, 224517, "Brass: Birmingham", "2018")])
    db.set_price(con, 224517, 60)
    db.replace_offers(con, 224517, [
        {"ad_id": "a", "title": "x", "price": 25, "negotiable": False, "location": "", "url": "u"},
        {"ad_id": "b", "title": "y", "price": 45, "negotiable": False, "location": "", "url": "u"}])
    assert [r["ad_id"] for r in db.deals(con, lid, 0.5)] == ["a"]


def test_manual_games():
    con = db.connect()
    lid = db.add_list(con, "manuell", "")
    db.add_manual_games(con, lid, ["Spiel A", "", "Spiel B"])
    assert [(g["rank"], g["name"]) for g in db.games_of_list(con, lid)] == [(1, "Spiel A"), (2, "Spiel B")]


KA_NEW = """<article data-adid="9" data-href="/s-anzeige/brass-birmingham-de-neu/9-23-1"><a href="/s-anzeige/brass-birmingham-de-neu/9-23-1"><span>4</span></a>
<div><a href="/s-anzeige/brass-birmingham-de-neu/9-23-1">Brass Birmingham DE neu</a><div class="hashed123">35 € VB</div><div>+ Versand ab 4,99 €</div></div></article>
<article data-adid="10" data-href="/s-anzeige/brass-birmingham-x/10-23-1"><a href="/s-anzeige/brass-birmingham-x/10-23-1"><span>7</span></a></article>"""


def test_kleinanzeigen_robust_parse():
    a, b = kleinanzeigen.parse_results(KA_NEW)
    assert (a["title"], a["price"], a["negotiable"]) == ("Brass Birmingham DE neu", 35.0, True)
    assert b["title"] == "brass birmingham x" and b["price"] is None


def test_bgg_csv():
    txt = "id,name,yearpublished,rank,is_expansion,strategygames_rank\n1,B,2000,2,0,1\n2,A,2001,1,0,0\n3,E,2002,3,1,2\n"
    assert [r[2] for r in bgg.parse_csv(txt)] == ["A", "B"]
    assert [r[2] for r in bgg.parse_csv(txt, "strategygames_rank")] == ["B"]


def test_estimate_new_price():
    mk = lambda t, p: {"title": t, "price": p}  # noqa: E731
    offers = [mk("Brass Birmingham NEU OVP", 60), mk("Brass Birmingham neu", 70), mk("Brass Birmingham gebraucht neuwertig", 30),
              mk("Brass Birmingham", 25)]
    assert kleinanzeigen.estimate_new_price(offers + [mk("Brass Birmingham OVP", 65)]) == (65, 3)
    assert kleinanzeigen.estimate_new_price(offers)[0] is None
    # Ausreißer (Sämaschine 6000 €) darf die Schätzung nicht kaputtmachen
    many = [mk("Agricola neu", 50), mk("Agricola OVP", 55), mk("Agricola neu", 60), mk("Agricola neu", 6000), mk("Agricola", 20)]
    assert kleinanzeigen.estimate_new_price(many) == (55, 3)


def test_matching_real_false_positives():
    m = matching.matches
    assert not m("Star Wars Rebellion", "Star Wars Rebels Soundbuch: Der Funke einer Rebellion")
    assert not m("Barrage Brettspiel", "manga barrage")
    assert not m("On Mars", "LEGO Space/ Life on Mars - 7311 Red Planet Cruiser")
    assert not m("Brass Lancashire", "Roxley Iron Clays - 10x100er - Brass Birmingham Lancashire")
    assert not m("Pandemic Legacy Season 2", "Pandemic Legacy Season 1 + 2 gespielt")
    assert not m("Wingspan", "Wingspan / Flügelschlag: Fan Art Pack")
    assert not m("Frosthaven", "4 Game Trays Gloomhaven/ Frosthaven, Kartenhalter Brettspiel")
    assert not m("Gloomhaven", "Gloomhaven - die Pranken des Löwen", ["Gloomhaven Pranken des Löwen"])
    assert m("Gloomhaven Pranken des Löwen", "Gloomhaven: Die Pranken des Löwen")
    assert m("Burgen von Burgund", "Die Burgen von Burgund - Alea, neuwertig")
    assert m("Star Wars Rebellion", "Star Wars: Rebellion Brettspiel deutsch")


def test_base_name():
    assert matching.base_name("Through the Ages: A New Story of Civilization") == "Through the Ages"
    assert matching.base_name("Twilight Imperium: Fourth Edition") == "Twilight Imperium"
    assert matching.base_name("Pandemic Legacy: Season 1") == "Pandemic Legacy: Season 1"
    assert matching.base_name("Mage Knight Board Game") == "Mage Knight"


def test_category_and_search_url():
    assert kleinanzeigen.ad_category("/s-anzeige/brass/3524703610-23-1291") == "23"
    assert kleinanzeigen.search_url("Brass: Birmingham", "23").endswith("/s-brass-birmingham/k0c23")


def test_search_plan_and_reference_prices():
    from app import scan
    con = db.connect()
    lid = db.add_list(con, "plan", "")
    db.save_ranking(con, lid, [(1, 174430, "Gloomhaven", None), (2, 291457, "Gloomhaven: Jaws of the Lion", None),
                               (3, 999, "Unbekanntes Spiel", None)])
    plan = scan.search_plan(db.games_of_list(con, lid))
    assert "Gloomhaven Pranken des Löwen" in plan[174430][1]
    assert plan[999][0] == ["Unbekanntes Spiel"] and plan[999][2] is False
    assert scan.apply_reference_prices(con, lid) == 2
    db.set_price(con, 174430, 99, "manuell")
    assert scan.apply_reference_prices(con, lid) == 0   # manuelle Preise bleiben


def test_real_kleinanzeigen_titles():
    """Echte Titel aus einem Lauf: Spiel|Titel|1=soll passen / 0=soll aussortiert werden."""
    from app import scan
    path = os.path.join(os.path.dirname(__file__), "fixtures", "real_titles.txt")
    pairs = [line.split("|") for line in open(path, encoding="utf-8").read().splitlines() if line]
    names = sorted({p[0] for p in pairs})
    games = [{"bgg_id": i, "name": n, "search_name": None, "exclude": None} for i, n in enumerate(names)]
    plan = scan.search_plan(games)
    by_name = {g["name"]: plan[g["bgg_id"]] for g in games}
    wrong = [(g, t) for g, t, exp in pairs
             if any(matching.matches(n, t, by_name[g][1], by_name[g][2]) for n in by_name[g][0]) != (exp == "1")]
    assert wrong == []


class FakeResp:
    def __init__(self, text, url="https://shop.de/s", status=200):
        self.text, self.url, self.status_code = text, url, status


def test_shop_price_via_search_and_product_page():
    from unittest import mock
    from app import http, shops
    pages = {
        "https://shop.de/search?q=Arche+Nova": FakeResp('<a href="/p/1">Arche Nova</a><a href="/p/2">Arche Nova Erweiterung Meeresbiologen</a>',
                                                         "https://shop.de/search?q=Arche+Nova"),
        "https://shop.de/p/1": FakeResp('<script type="application/ld+json">{"@type":"Product","name":"Arche Nova",'
                                        '"offers":{"@type":"Offer","price":"52.99"}}</script>', "https://shop.de/p/1"),
    }
    shop = {"name": "Test", "search_url": "https://shop.de/search?q={q}"}
    with mock.patch.object(http, "get", side_effect=lambda u, **k: pages[u]):
        price, note = shops.find_price(["Arche Nova"], [shop])
    assert price == 52.99 and "https://shop.de/p/1" in note

    def blocked(u, **k):
        raise http.Blocked("shop.de blockiert")
    seen = {}
    with mock.patch.object(http, "get", side_effect=blocked):
        assert shops.find_price(["Arche Nova"], [shop], seen) is None
    assert "Test" in seen


def test_fetch_prices_keeps_manual():
    from unittest import mock
    from app import scan, shops
    con = db.connect()
    lid = db.add_list(con, "shops", "")
    db.save_ranking(con, lid, [(1, 501, "Ark Nova", None), (2, 502, "Wingspan", None)])
    scan.apply_reference_prices(con, lid)
    db.set_price(con, 502, 33, "manuell")
    with mock.patch.object(shops, "load", return_value=[{"name": "T", "search_url": "x"}]), \
         mock.patch.object(shops, "find_price", return_value=(49.0, "Shop T")):
        errors, summary = scan.fetch_prices(con, lid)
    prices = {g["bgg_id"]: (g["new_price"], g["price_note"]) for g in db.games_of_list(con, lid)}
    assert prices[501] == (49.0, "Shop T") and prices[502] == (33, "manuell")


def test_deals_grouped_and_sources():
    from app.web import app
    con = db.connect()
    lid = db.add_list(con, "grp", "")
    db.save_ranking(con, lid, [(1, 601, "Spiel X", None)])
    db.set_price(con, 601, 100, "manuell")
    mk = lambda i, p: {"ad_id": i, "title": f"Spiel X {i}", "price": p, "negotiable": False, "location": "", "url": "u"}  # noqa: E731
    db.replace_offers(con, 601, [mk("k1", 30), mk("k2", 40)])
    db.replace_offers(con, 601, [dict(mk("e1", 20), auction=True)], "ebay")
    c = app.test_client()
    html = c.get(f"/?list={lid}").get_data(as_text=True)
    assert html.count('class="grp"') == 1 and "3 Angebote" in html and "Auktion" in html
    html = c.get(f"/?list={lid}&src=kleinanzeigen&group=0&sort=price").get_data(as_text=True)
    assert "Spiel X e1" not in html and html.index("Spiel X k1") < html.index("Spiel X k2")


def test_bgg_collection_csv():
    txt = ("objectname;objectid;rank;yearpublished;itemtype;own\n"
           "Spirit Island;162886;11;2017;standalone;1\n"
           "Wingspan;266192;38;2019;standalone;0\n"
           "Unbekannt;999;0;2024;standalone;1\n"
           "Wingspan Asien;366161;500;2022;expansion;0\n"
           "Wingspan;266192;38;2019;standalone;0\n")
    assert bgg.parse_csv(txt) == [(1, 162886, "Spirit Island", "2017"), (2, 266192, "Wingspan", "2019"), (3, 999, "Unbekannt", "2024")]


def test_unknown_csv_and_bad_upload_show_message():
    import io
    import pytest
    from app.web import app, job
    with pytest.raises(ValueError):
        bgg.parse_csv("foo,bar\n1,2\n")
    c = app.test_client()
    r = c.post("/lists", data={"name": "x", "size": "", "column": "rank", "csv": (io.BytesIO(b"foo,bar\n1,2\n"), "x.csv")},
               content_type="multipart/form-data")
    assert r.status_code == 302 and "Unbekanntes CSV-Format" in job["text"]
    r = c.post("/lists", data={"name": "leer", "size": "", "url": "", "manual": "A"})
    assert r.status_code == 302


def test_error_page_instead_of_500_text():
    from unittest import mock
    from app import web
    with mock.patch.object(web.db, "games_of_list", side_effect=RuntimeError("kaputt")):
        c = web.app.test_client()
        con = db.connect()
        lid = db.add_list(con, "e", "")
        r = c.get(f"/prices?list={lid}")
    assert r.status_code == 500 and "kaputt" in r.get_data(as_text=True) and "Traceback" in r.get_data(as_text=True)
