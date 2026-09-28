# Brettspiel-Schnäppchen

Vergleicht BGG-Ranglisten (z. B. die Top 100) mit Angeboten auf Kleinanzeigen.de und zeigt nur die,
die höchstens X % (Standard 50 %) des Neupreises kosten. Neupreise kommen aus Online-Shops, mitgelieferten Richtwerten oder von dir. Optional wird auch eBay durchsucht.

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
3. **„2. Neupreise aus Shops“** klicken – sucht jedes Spiel in den Online-Shops aus `app/shops.csv`
   und speichert den günstigsten Preis. Shops, die blockieren oder nicht erreichbar sind, werden übersprungen. Bereits eingetragene (auch manuelle) Preise werden nicht überschrieben.
   Spiele ohne Treffer werden oben als Hinweis aufgelistet.
4. **Reiter *Neupreise*:** Fehlende Preise nachtragen oder falsche korrigieren. Spiele ohne Preis stehen oben.
   Die Spalte „Quelle“ zeigt, woher der Preis kam. Zusätzlich gibt es den Import mehrerer Zeilen im Format
   `Spielname;Preis`.
   - **Suchname** (optional): Findet Kleinanzeigen/ein Shop ein Spiel nicht, weil es dort einen anderen,
     meist deutschen Titel hat (z. B. „Brass: Birmingham“ → „Brass Birmingham“, „Terraforming Mars“ →
     „Terraforming Mars Brettspiel“), trage hier den Titel ein, wie man ihn dort findet. Er wird für beide
     Suchen benutzt.
5. **„3. Angebote scannen“** klicken (Kleinanzeigen und – falls eingerichtet – eBay). Fehlt einem Spiel der Neupreis, schätzt die App ihn dabei
   automatisch als Median der Anzeigen, die als „NEU“/„OVP“/„ungespielt“ inseriert sind (mind. 2).
   Manuell eingetragene Preise werden nie überschrieben; Quelle steht im Reiter *Neupreise*.
   Weiter: – sucht zu jedem Spiel Angebote. Das dauert bei 100 Spielen
   mehrere Minuten (bewusst 1,5 s Pause pro Anfrage). Fortschritt: Seite neu laden.
6. **Reiter *Schnäppchen*:** Liste wählen, „mindestens X % günstiger als neu“ einstellen (Standard 50 %), „Zeigen“.
   Die Untergrenze („nicht unter 10 % vom Neupreis“) blendet Spottpreise aus, die fast immer Zubehör oder Fehltreffer sind. Angezeigt werden nur
   Angebote von Spielen mit bekanntem Neupreis. Ein Klick auf den Titel öffnet die Anzeige.

Neupreise musst du nur beim ersten Mal holen; danach reicht es, Schritt 5 zu wiederholen, um neue Angebote zu sehen.

### Weitere Listen (Kampagnenspiele, Familienspiele, …)
Auf boardgamegeek.com die gewünschte Suche/Browse-Ansicht **nach Rang sortiert** aufrufen (z. B. über
*Advanced Search* mit Kategorie/Mechanik/Familie), die Adresse aus der Browserzeile kopieren und als neue
Liste einfügen. Spiele, die in mehreren Listen vorkommen, teilen sich Neupreis und Suchnamen.

### Ohne Browser (Kommandozeile)
    python -m app refresh <listen-id>   # BGG laden
    python -m app prices  <listen-id>   # Neupreise aus Shops
    python -m app scan    <listen-id>   # Kleinanzeigen scannen

### Woher kommen die Neupreise? (Reihenfolge)
1. **Manuell** im Reiter *Neupreise* eingetragen – wird nie überschrieben.
2. **Shop-Preis** („2. Neupreise aus Shops“): günstigster Preis aus den Shops in `app/shops.csv`.
   Die App liest die strukturierten Produktdaten (schema.org), die fast jeder Shop für Google einbettet –
   darum funktioniert jeder Shop ohne eigenen Parser. **Eigenen Shop hinzufügen:** im Browser dort nach
   „Brass Birmingham“ suchen, Adresse kopieren, den Suchbegriff durch `{q}` ersetzen und als neue Zeile
   eintragen. Im Reiter *Diagnose* siehst du, welche Shops funktionieren.
3. **Richtwert** aus `app/reference.csv` (ca. UVP für ~130 bekannte Spiele, grob geschätzt – bitte prüfen).
4. **Kleinanzeigen-Schätzung**: Median von mind. 3 Anzeigen mit „NEU/OVP/ungespielt“ (Ausreißer entfernt).

### Wie werden falsche Treffer vermieden?
- Suche nur in der Kleinanzeigen-Kategorie für Spiele (Bücher, Kleidung, Autoteile … fallen raus).
- Der Spielname muss als zusammenhängende Wortfolge im Titel stehen.
- Globale Ausschlusswörter (Lego, Manga, Erweiterung, Sleeves, 3D-Druck, Figuren …) in `app/matching.py`.
- Pro Spiel: deutsche Suchnamen und eigene Ausschlusswörter im Reiter *Neupreise* (Vorgaben in `app/reference.csv`).
- Enthält ein anderes Spiel der Liste den Namen (Gloomhaven → „Gloomhaven: Pranken des Löwen“), wird es ausgeschlossen.

### eBay einrichten (optional, kostenlos)
eBay verbietet das automatische Auslesen seiner Webseiten, bietet aber eine offizielle, kostenlose Schnittstelle:
1. Auf https://developer.ebay.com registrieren (eBay-Konto reicht) und unter *Application Keys* ein
   **Production**-Schlüsselpaar erzeugen.
2. Die Datei `data/ebay.json` anlegen:
   `{"client_id": "DEINE-App-ID", "client_secret": "DEIN-Cert-ID"}`
3. App neu starten. Ab jetzt sucht „3. Angebote scannen“ auch auf eBay.de (Artikelstandort Deutschland).
   Auktionen sind mit „Auktion“ markiert – der Preis ist dort nur das aktuelle Gebot.

### Schnäppchen-Ansicht
- **Gruppiert** (Standard): eine Zeile pro Spiel mit dem besten Angebot; „n Angebote ▾“ klappt die übrigen auf.
- **Sortieren** nach Ersparnis %, Ersparnis €, Preis, BGG-Rang, Name oder zuletzt gesehen.
- **Quellen** Kleinanzeigen/eBay einzeln an- und abwählen.

## 4. Probleme? Zuerst die Diagnose

    python -m app check          # oder im Browser: Reiter „Diagnose“

Das testet BGG, Kleinanzeigen, jeden Shop und (falls eingerichtet) eBay mit „Brass Birmingham“ und zeigt HTTP-Status, wie viele Einträge
gelesen wurden und speichert die Roh-Seiten unter `data/debug/*.html`. Bei „HTTP 403“ oder „0 Einträge“ ist die
Seite blockiert oder hat ihr Layout geändert – die Ausgabe (und ggf. die HTML-Datei) reicht, um den Parser anzupassen.

Nach jedem Lauf zeigt die App eine Zusammenfassung („12 Neupreise gefunden …“, „0 Anzeigen gelesen …“).
Rot hinterlegte Meldungen sind Fehler. „Fertig“ mit 0 Treffern bedeutet **nicht**, dass es geklappt hat.

**Wenn BGG blockiert:** Beim Anlegen einer Liste die URL leer lassen und die Spielnamen manuell eintragen
(einer pro Zeile). Dann laufen Shops und Kleinanzeigen trotzdem.



| Symptom | Ursache / Lösung |
|---|---|
| „BGG antwortete mit HTTP 401/403“ oder „Keine Spiele gefunden“ | BGG blockiert Bot-Zugriffe oder hat das Layout geändert → Parser in `app/bgg.py` anpassen |
| Viele Spiele ohne Shop-Preis | In *Diagnose* prüfen, welche Shops gehen; Such-URL in `app/shops.csv` korrigieren oder Shops ergänzen; sonst gilt der Richtwert |
| Keine Schnäppchen | Neupreise eingetragen? Kleinanzeigen gescannt? Prozentgrenze höher stellen |
| Falsche Treffer | Suchname präzisieren; Ausschlusswörter stehen in `app/matching.py` |

## Hinweise
- **Wichtig:** Die HTML-Parser für BGG, Kleinanzeigen und die Shops wurden nur gegen Beispiel-HTML getestet
  (`pytest`), nicht gegen die Live-Seiten. Sie können bei Layout-Änderungen oder Bot-Schutz nachgebessert werden müssen.
- Der Shop-Preis ist der günstigste gefundene Ladenpreis, nicht die UVP.
- Beachte die Nutzungsbedingungen von BGG, Kleinanzeigen, eBay und den Shops und scanne nicht übermäßig oft.
