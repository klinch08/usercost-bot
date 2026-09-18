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
# плюс все буквы и частые двухбуквенные начала: так в снимок попадают не только
# «тематические» ники, а весь рынок
QUERIES += list("abcdefghijklmnopqrstuvwxyz0123456789")
QUERIES += [c + v for c in "bcdfghklmnprstvwz" for v in "aeiou"]


def refresh():
    # дописываем к старому снимку, а не затираем его
    with open(SNAP) as f:
        out = json.load(f)
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
    coef, report = fit_model(sales, known)
    with open(OUT, "w") as f:
        json.dump({"medians": table, "creation_ton": creation,
                   "holdout": report,
                   "samples": sum(map(len, buckets.values()))}, f, indent=1, sort_keys=True)
    print("классов", len(table), "цена создания", creation)
    print("проверка на отложенных 20%:", report)
    # Регрессия (fit_model) на отложенных 20% проиграла медианам классов:
    # 1.69x против 1.53x медианной ошибки, поэтому в модель её коэффициенты
    # не пишем. Оставлена, чтобы сравнивать при следующих калибровках.


def fit_model(sales, known, ridge=1.0):
    """Гребневая регрессия log(цены) по признакам valuation.design.

    Похожие продажи для каждого ника берутся без него самого. Сначала учим на
    80% и меряем на отложенных 20% (это и есть честная точность), потом
    учим на всём.
    """
    import math
    import random
    import statistics
    import numpy as np
    import features
    import valuation

    by_prefix = defaultdict(list)
    for n, p in sales.items():
        by_prefix[n[:3]].append((n, p))
    rows, y, names = [], [], []
    for n, p in sales.items():
        if n in known:
            continue
        f = features.analyze(n)
        others = [s for s in by_prefix[n[:3]] if s[0] != n]
        same, _ = valuation.similar_sales(f, others)
        rows.append(valuation.design(f, [q for _, q in same], [q for _, q in others]))
        y.append(math.log(max(p, 1)))
        names.append(n)

    keys = sorted({k for r in rows for k in r})
    idx = {k: i for i, k in enumerate(keys)}
    X = np.zeros((len(rows), len(keys)))
    for i, r in enumerate(rows):
        for k, v in r.items():
            X[i, idx[k]] = v
    Y = np.array(y)

    def solve(mask):
        """Медианная регрессия (IRLS): цены на Fragment идут пиками по 10, 104,
        5050 TON, и обычная регрессия по среднему промахивается мимо всех пиков."""
        A, b = X[mask], Y[mask]
        reg = ridge * np.eye(len(keys))
        reg[idx["bias"], idx["bias"]] = 0
        wts = np.ones(len(b))
        for _ in range(40):
            Aw = A * wts[:, None]
            w = np.linalg.solve(A.T @ Aw + reg, Aw.T @ b)
            wts = 1.0 / np.maximum(np.abs(A @ w - b), 0.05)
        return w

    order = list(range(len(rows)))
    random.Random(7).shuffle(order)
    test = np.zeros(len(rows), bool)
    test[order[: len(rows) // 5]] = True
    w = solve(~test)
    pred, real = X[test] @ w, Y[test]
    err = np.abs(pred - real)
    rp = np.argsort(np.argsort(pred)).astype(float)
    rr = np.argsort(np.argsort(real)).astype(float)
    report = {"n": int(test.sum()),
              "spearman": round(float(np.corrcoef(rp, rr)[0, 1]), 3),
              "med_x": round(float(np.exp(np.median(err))), 2),
              "within2x": round(float((err <= math.log(2)).mean()), 3),
              "within5x": round(float((err <= math.log(5)).mean()), 3)}

    # тот же тест для старого способа: медиана класса по 80% данных
    med = defaultdict(list)
    for i in np.where(~test)[0]:
        f = features.analyze(names[i])
        med[valuation.name_class(f) + ":" + str(valuation.length_bucket(f.length))].append(Y[i])
    med = {k: float(np.median(v)) for k, v in med.items()}
    base = []
    for i in np.where(test)[0]:
        f = features.analyze(names[i])
        base.append(med.get(valuation.name_class(f) + ":" + str(valuation.length_bucket(f.length)),
                            math.log(10)))
    berr = np.abs(np.array(base) - real)
    report["old_medians"] = {"med_x": round(float(np.exp(np.median(berr))), 2),
                             "within2x": round(float((berr <= math.log(2)).mean()), 3)}

    w = solve(np.ones(len(rows), bool))
    return {k: round(float(w[idx[k]]), 4) for k in keys}, report


if __name__ == "__main__":
    main()
