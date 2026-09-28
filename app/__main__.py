"""CLI: python -m app init|refresh|scan|serve"""
import argparse

from . import db, scan


def main():
    p = argparse.ArgumentParser(prog="app")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    for name in ("refresh", "prices", "scan"):
        s = sub.add_parser(name)
        s.add_argument("list_id", type=int)
    args = p.parse_args()
    con = db.connect()
    if args.cmd == "serve":
        from .web import app
        app.run(host="127.0.0.1", port=5000)
    elif args.cmd == "refresh":
        scan.refresh_list(con, args.list_id)
        print("Rangliste aktualisiert.")
    elif args.cmd == "prices":
        errs, missing = scan.fetch_prices(con, args.list_id, lambda i, n, name: print(f"[{i}/{n}] {name}"))
        print("Kein Geizhals-Treffer (bitte manuell eintragen):", ", ".join(missing) or "-")
        print("\n".join(errs))
    else:
        errs = scan.scan_offers(con, args.list_id, lambda i, n, name: print(f"[{i}/{n}] {name}"))
        print("\n".join(errs) or "Fertig.")


main()
