"""Mitgelieferte Richtwerte: ungefähre Neupreise (UVP, EUR), deutsche Suchnamen, Ausschlusswörter.

Die Preise sind grobe Schätzwerte – bitte im Reiter „Neupreise“ prüfen und korrigieren.
Manuell eingetragene Preise haben immer Vorrang."""
import csv
import os

from .matching import normalize

PATH = os.path.join(os.path.dirname(__file__), "reference.csv")
NOTE = "Richtwert (ca. UVP, bitte prüfen)"


def load():
    """-> {normalisierter BGG-Name: {'aliases': [...], 'price': float|None, 'exclude': [...]}}"""
    out = {}
    with open(PATH, encoding="utf-8") as f:
        for r in csv.DictReader((line for line in f if not line.startswith("#")), delimiter=";"):
            out[normalize(r["name"])] = {
                "aliases": [a.strip() for a in (r["aliases"] or "").split("|") if a.strip()],
                "price": float(r["price"]) if (r["price"] or "").strip() else None,
                "exclude": [e.strip() for e in (r["exclude"] or "").split("|") if e.strip()],
            }
    return out
