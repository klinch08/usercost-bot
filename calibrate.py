# -*- coding: utf-8 -*-
"""Пересчитать data/calibration.json по снимку продаж Fragment.

    py -3.13 calibrate.py            # по data/sales_snapshot.json
    py -3.13 calibrate.py --refresh  # сначала обновить снимок с сайта

Ники из tests/known_sales.json в подгонку не попадают, чтобы тест
проверял алгоритм, а не заучивание.
"""

import json
import os
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(ROOT, "data", "sales_snapshot.json")
OUT = os.path.join(ROOT, "data", "calibration.json")
KNOWN = os.path.join(ROOT, "tests", "known_sales.json")

QUERIES = [""] + ("crypto bank gold nft ton shop game news love king money bet ai bot app "
                  "cat dog art pay car girl boy music club tech coin win play aa zz qx xy vk "
                  "ru pro one top vip star moon").split()


def refresh():
    out = {}
    for q in QUERIES:
        for sort in ("price_desc", "price_asc"):
            url = "https://fragment.com/?query=%s&filter=sold&sort=%s" % (q, sort)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                html = urllib.request.urlopen(req, timeout=20).read().decode()
            except Exception as e:
                print(q, e)
                continue
            for row in re.findall(r'<tr class="tm-row-selectable">(.*?)</tr>', html, re.S):
                n = re.search(r'tm-value">@([a-z0-9_]+)<', row)
                p = re.search(r'icon-ton">([\d,]+)<', row)
                if n and p:
                    out[n.group(1)] = int(p.group(1).replace(",", ""))
            time.sleep(0.6)
    with open(SNAP, "w") as f:
        json.dump(out, f, indent=0)


def main():
    sys.path.insert(0, ROOT)
    import valuation
    if "--refresh" in sys.argv:
        refresh()
    with open(SNAP) as f:
        sales = json.load(f)
    with open(KNOWN) as f:
        known = set(json.load(f))

    buckets = defaultdict(list)
    for name, price in sales.items():
        if name in known:
            continue
        cls = valuation.name_class(valuation.features.analyze(name))
        buckets[cls + ":" + str(valuation.length_bucket(len(name)))].append(price)

    table = {k: round(statistics.median(v), 1) for k, v in buckets.items() if len(v) >= 3}
    randoms = [p for k, v in buckets.items() if k.startswith(("random:", "pronounce:"))
               and not k.endswith(":4") for p in v]
    creation = Counter(randoms).most_common(1)[0][0]
    with open(OUT, "w") as f:
        json.dump({"medians": table, "creation_ton": creation,
                   "samples": sum(map(len, buckets.values()))}, f, indent=1, sort_keys=True)
    print("классов", len(table), "цена создания", creation)


if __name__ == "__main__":
    main()
