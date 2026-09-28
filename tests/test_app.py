import os
import tempfile

os.environ["BSS_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")

from app import geizhals, bgg, db, kleinanzeigen, matching  # noqa: E402

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


GH_HTML = """<div class="listview__item"><a class="listview__name-link" href="/brass-birmingham-a2100000.html">Brass: Birmingham</a>
<div class="price">ab € 49,99</div></div>
<div class="listview__item"><a href="/brass-birmingham-erweiterung-a3.html">Brass Birmingham Erweiterung</a><span>€ 12,00</span></div>"""


def test_geizhals_parse():
    res = geizhals.parse_results(GH_HTML)
    assert [r["price"] for r in res] == [49.99, 12.0]
    assert [r["name"] for r in res if matching.matches("Brass: Birmingham", r["name"])] == ["Brass: Birmingham"]


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
    assert plan[999][0] == ["Unbekanntes Spiel"]
    assert scan.apply_reference_prices(con, lid) == 2
    db.set_price(con, 174430, 99, "manuell")
    assert scan.apply_reference_prices(con, lid) == 0   # manuelle Preise bleiben
