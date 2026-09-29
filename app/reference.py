"""Mitgelieferte Suchhilfen je Spiel: deutsche Suchnamen, Ausschlusswörter, Kontext-Pflicht.
Enthält keine Preise – Neupreise kommen ausschließlich aus Shop-Daten oder von dir."""
import csv
import os

from .matching import normalize

PATH = os.path.join(os.path.dirname(__file__), "reference.csv")


def load():
    """-> {normalisierter BGG-Name: {'aliases': [...], 'price': float|None, 'exclude': [...]}}"""
    out = {}
    with open(PATH, encoding="utf-8") as f:
        for r in csv.DictReader((line for line in f if not line.startswith("#")), delimiter=";"):
            out[normalize(r["name"])] = {
                "aliases": [a.strip() for a in (r["aliases"] or "").split("|") if a.strip()],
                "price": float(r["price"]) if (r["price"] or "").strip() else None,
                "exclude": [e.strip() for e in (r["exclude"] or "").split("|") if e.strip()],
                "context": (r.get("context") or "").strip() == "1",
            }
    return out
