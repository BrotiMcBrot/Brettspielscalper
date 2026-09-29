#!/usr/bin/env bash
# Startet die App mit einem Befehl: aktualisieren, Pakete installieren, Server starten, Browser öffnen.
#   ./start.sh         -> App starten (Browser öffnet sich automatisch)
#   ./start.sh check   -> nur Diagnose ausführen
cd "$(dirname "$0")"
echo ">> Hole Updates ..."
git pull --ff-only || echo "   (Update fehlgeschlagen – starte mit der vorhandenen Version)"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
if [ "$1" = "check" ]; then
    python -m app check
else
    echo ">> App läuft auf http://127.0.0.1:5000  –  Beenden mit Strg+C"
    (sleep 2; xdg-open http://127.0.0.1:5000 >/dev/null 2>&1) &
    python -m app serve
fi
