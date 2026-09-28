"""CLI: python -m app init|refresh|scan|serve"""
import argparse

from . import db, scan


def main():
    p = argparse.ArgumentParser(prog="app")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    sub.add_parser("check")
    for name in ("refresh", "prices", "scan"):
        s = sub.add_parser(name)
        s.add_argument("list_id", type=int)
    args = p.parse_args()
    if args.cmd == "check":
        from . import check
        return print(check.run())
    con = db.connect()
    if args.cmd == "serve":
        from .web import app
        app.run(host="127.0.0.1", port=5000)
    elif args.cmd == "refresh":
        print(scan.refresh_list(con, args.list_id)[1])
    elif args.cmd == "prices":
        errs, msg = scan.fetch_prices(con, args.list_id, lambda i, n, name: print(f"[{i}/{n}] {name}"))
        print("\n".join(errs), msg, sep="\n")
    else:
        errs, msg = scan.scan_offers(con, args.list_id, lambda i, n, name: print(f"[{i}/{n}] {name}"))
        print("\n".join(errs), msg, sep="\n")


main()
