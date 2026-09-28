# Brettspiel-Schnäppchen

Vergleicht BGG-Ranglisten (z. B. die Top 100) mit Angeboten auf Kleinanzeigen.de und zeigt nur die,
die höchstens X % (Standard 50 %) des Neupreises kosten. Die Neupreise kommen automatisch von Geizhals.de.

## 1. Installation

Voraussetzung: **Python 3.10 oder neuer** (`python3 --version` prüfen; Download: https://www.python.org/downloads/).

    git clone https://github.com/BrotiMcBrot/Brettspielscalper.git
    cd Brettspielscalper
    python3 -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    pip install -r requirements.txt

Die App läuft komplett lokal auf deinem Rechner, Daten liegen in `data/app.db` (SQLite, wird automatisch angelegt).

## 2. Starten

    python -m app serve

Dann im Browser **http://127.0.0.1:5000** öffnen. Beenden mit `Strg+C`.
Beim nächsten Mal reicht: Ordner öffnen, `source .venv/bin/activate`, `python -m app serve`.

## 3. Benutzung – Schritt für Schritt

Alles passiert in der Weboberfläche mit den drei Reitern **Schnäppchen**, **Neupreise**, **Listen**.

1. **Liste anlegen** (Reiter *Listen* → „Neue Liste“). BGG und Geizhals blockieren automatische Abfragen
   per Cloudflare (HTTP 403) – das umgeht die App nicht. Deshalb der empfohlene Weg für BGG:
   - Auf https://boardgamegeek.com/data_dumps/bg_ranks (Login nötig) die ZIP herunterladen und entpacken
     → `boardgames_ranks.csv`.
   - Bei „Neue Liste“ Name eintragen, die CSV hochladen und die gewünschte Rangliste wählen
     (Gesamt, Strategie-, Familien-, Thematic-, Party-, Kriegsspiele …), Anzahl `100`, „Anlegen“.
     Die Spiele sind sofort drin; „1. BGG laden“ ist dann nicht nötig.
   - Alternativ: Spielnamen manuell eintragen (einer pro Zeile), oder – nur falls BGG bei dir doch antwortet –
     eine BGG-URL wie `https://boardgamegeek.com/browse/boardgame` und „1. BGG laden“.
3. **„2. Neupreise (Geizhals)“** klicken (bricht bei Cloudflare-Sperre sofort mit Hinweis ab – dann Preise
   im Reiter *Neupreise* von Hand eintragen bzw. per `Name;Preis`-Import einfügen) – sucht jedes Spiel auf Geizhals und speichert den günstigsten
   aktuellen Neupreis. Bereits eingetragene (auch manuelle) Preise werden nicht überschrieben.
   Spiele ohne Treffer werden oben als Hinweis aufgelistet.
4. **Reiter *Neupreise*:** Fehlende Preise nachtragen oder falsche korrigieren. Spiele ohne Preis stehen oben.
   Die Spalte „Quelle“ zeigt, woher der Preis kam. Zusätzlich gibt es den Import mehrerer Zeilen im Format
   `Spielname;Preis`.
   - **Suchname** (optional): Findet Geizhals/Kleinanzeigen ein Spiel nicht, weil es dort einen anderen,
     meist deutschen Titel hat (z. B. „Brass: Birmingham“ → „Brass Birmingham“, „Terraforming Mars“ →
     „Terraforming Mars Brettspiel“), trage hier den Titel ein, wie man ihn dort findet. Er wird für beide
     Suchen benutzt.
5. **„3. Kleinanzeigen scannen“** klicken. Fehlt einem Spiel der Neupreis, schätzt die App ihn dabei
   automatisch als Median der Anzeigen, die als „NEU“/„OVP“/„ungespielt“ inseriert sind (mind. 2).
   Manuell eingetragene Preise werden nie überschrieben; Quelle steht im Reiter *Neupreise*.
   Weiter: – sucht zu jedem Spiel Angebote. Das dauert bei 100 Spielen
   mehrere Minuten (bewusst 1,5 s Pause pro Anfrage). Fortschritt: Seite neu laden.
6. **Reiter *Schnäppchen*:** Liste wählen, Prozentgrenze einstellen, „Zeigen“. Angezeigt werden nur
   Angebote von Spielen mit bekanntem Neupreis. Ein Klick auf den Titel öffnet die Anzeige.

Neupreise musst du nur beim ersten Mal holen; danach reicht es, Schritt 5 zu wiederholen, um neue Angebote zu sehen.

### Weitere Listen (Kampagnenspiele, Familienspiele, …)
Auf boardgamegeek.com die gewünschte Suche/Browse-Ansicht **nach Rang sortiert** aufrufen (z. B. über
*Advanced Search* mit Kategorie/Mechanik/Familie), die Adresse aus der Browserzeile kopieren und als neue
Liste einfügen. Spiele, die in mehreren Listen vorkommen, teilen sich Neupreis und Suchnamen.

### Ohne Browser (Kommandozeile)
    python -m app refresh <listen-id>   # BGG laden
    python -m app prices  <listen-id>   # Neupreise von Geizhals
    python -m app scan    <listen-id>   # Kleinanzeigen scannen

## 4. Probleme? Zuerst die Diagnose

    python -m app check          # oder im Browser: Reiter „Diagnose“

Das testet BGG, Geizhals und Kleinanzeigen mit „Brass Birmingham“ und zeigt HTTP-Status, wie viele Einträge
gelesen wurden und speichert die Roh-Seiten unter `data/debug/*.html`. Bei „HTTP 403“ oder „0 Einträge“ ist die
Seite blockiert oder hat ihr Layout geändert – die Ausgabe (und ggf. die HTML-Datei) reicht, um den Parser anzupassen.

Nach jedem Lauf zeigt die App eine Zusammenfassung („12 Neupreise gefunden …“, „0 Anzeigen gelesen …“).
Rot hinterlegte Meldungen sind Fehler. „Fertig“ mit 0 Treffern bedeutet **nicht**, dass es geklappt hat.

**Wenn BGG blockiert:** Beim Anlegen einer Liste die URL leer lassen und die Spielnamen manuell eintragen
(einer pro Zeile). Dann laufen Geizhals und Kleinanzeigen trotzdem.



| Symptom | Ursache / Lösung |
|---|---|
| „BGG antwortete mit HTTP 401/403“ oder „Keine Spiele gefunden“ | BGG blockiert Bot-Zugriffe oder hat das Layout geändert → Parser in `app/bgg.py` anpassen |
| Viele Spiele ohne Geizhals-Preis | Suchname setzen oder Preis manuell eintragen; Geizhals-Layout ggf. in `app/geizhals.py` prüfen |
| Keine Schnäppchen | Neupreise eingetragen? Kleinanzeigen gescannt? Prozentgrenze höher stellen |
| Falsche Treffer | Suchname präzisieren; Ausschlusswörter stehen in `app/matching.py` |

## Hinweise
- **Wichtig:** Die HTML-Parser für BGG, Kleinanzeigen und Geizhals wurden nur gegen Beispiel-HTML getestet
  (`pytest`), nicht gegen die Live-Seiten. Sie können bei Layout-Änderungen oder Bot-Schutz nachgebessert werden müssen.
- Der Geizhals-Preis ist der günstigste aktuelle Marktpreis für das Spiel, nicht die UVP.
- Beachte die Nutzungsbedingungen von BGG, Kleinanzeigen und Geizhals und scanne nicht übermäßig oft.
