# -*- coding: utf-8 -*-
"""Каждый день (GitHub Actions): ключевая ставка с сайта Банка России → key_rates.json для программы и сайта."""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
import keyrate as K

pts, src = None, ""
for name, fn in (("cbr soap", K.from_cbr_soap), ("cbr html", K.from_cbr_html)):
    try:
        p = fn("2013-09-13")
        print(name, "points:", len(p), p[-3:], "valid:", K.validate(p))
        print(name, "mismatch with built-in table:", K.mismatches(p))
        if K.validate(p) and pts is None:
            pts, src = p, name
    except Exception as e:
        print(name, "error:", repr(e))
if not pts:
    sys.exit("no valid data")
table = K.merge(K.BUILTIN, pts)
path = os.path.join(os.path.dirname(__file__), "..", "key_rates.json")
old = None
if os.path.exists(path):
    old = json.load(open(path, encoding="utf-8")).get("rates")
if old == [list(x) for x in table]:
    print("unchanged"); sys.exit(0)
json.dump({"rates": table, "source": "Банк России (" + src + ")", "updated": dt.date.today().isoformat()},
          open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("written", table[-3:])
