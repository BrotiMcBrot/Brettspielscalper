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
    ok = [o["ad_id"] for o in res if o["price"] and matching.matches("Brass: Birmingham", o["title"])]
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
