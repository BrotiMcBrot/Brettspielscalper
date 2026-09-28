# Brettspiel-Schnäppchen

Vergleicht BGG-Ranglisten (z.B. Top 100) mit Kleinanzeigen.de und zeigt nur Angebote,
die höchstens X % (Standard 50 %) des Neupreises kosten.

## Start
    pip install -r requirements.txt
    python -m app serve        # http://127.0.0.1:5000

## Ablauf
1. **Listen**: Liste anlegen (Vorschlag: Top 100 = `https://boardgamegeek.com/browse/boardgame`),
   dann „BGG laden“. Für andere Listen (Kampagnenspiele, Familienspiele …) eine BGG-Such-/Browse-URL
   nach Rang sortiert einfügen.
2. **Neupreise**: Neupreis je Spiel eintragen (einmalig, bleibt gespeichert; Bulk-Import `Name;Preis`).
   Optional „Suchname“ (deutscher Titel) für besseres Finden auf Kleinanzeigen.
3. **Listen → Kleinanzeigen scannen**, danach **Schnäppchen** ansehen.

CLI: `python -m app refresh <id>` / `python -m app scan <id>`. Tests: `pytest`.

## Hinweise
- Die HTML-Parser (BGG, Kleinanzeigen) wurden gegen Beispiel-HTML getestet, nicht gegen die Live-Seiten
  (in der Entwicklungsumgebung war kein Internetzugriff). Ändert sich deren Layout oder greift Bot-Schutz,
  müssen `app/bgg.py` / `app/kleinanzeigen.py` angepasst werden.
- Scans laufen bewusst langsam (1,5 s Pause je Request), um die Seiten nicht zu belasten.
  Beachte die Nutzungsbedingungen von BGG und Kleinanzeigen.
