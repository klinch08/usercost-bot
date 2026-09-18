# -*- coding: utf-8 -*-
"""Качество оценки на всём снимке продаж Fragment.

    py -3.13 evaluate_model.py [--sample N]

Для каждого проданного ника считаем оценку так, будто его продажи не было:
похожие продажи - по префиксу из снимка без самого ника. Печатаем:
  * spearman  - совпадение порядка с реальными ценами (1.0 - идеально);
  * med_x     - медианная ошибка в разах (1.0 - точно, 2.0 - вдвое);
  * within2x / within5x - доля оценок не дальше 2 и 5 раз от реальной цены.
"""

import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import valuation  # noqa: E402

SNAP = os.path.join(ROOT, "data", "sales_snapshot.json")


def ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    r = [0] * len(values)
    for i, idx in enumerate(order):
        r[idx] = i
    return r


def run(sample=None, seed=1):
    with open(SNAP) as f:
        snap = json.load(f)
    by_prefix = defaultdict(list)
    for n, p in snap.items():
        by_prefix[n[:3]].append((n, p))

    names = list(snap)
    if sample and sample < len(names):
        random.Random(seed).shuffle(names)
        names = names[:sample]

    real, est = [], []
    for n in names:
        sales = [s for s in by_prefix[n[:3]] if s[0] != n]
        real.append(max(snap[n], 1))
        est.append(max(valuation.evaluate(n, sales).price_ton, 1))

    errs = [abs(math.log(e / r)) for e, r in zip(est, real)]
    return {
        "n": len(names),
        "spearman": round(statistics.correlation(ranks(real), ranks(est)), 3),
        "med_x": round(math.exp(statistics.median(errs)), 2),
        "within2x": round(sum(e <= math.log(2) for e in errs) / len(errs), 3),
        "within5x": round(sum(e <= math.log(5) for e in errs) / len(errs), 3),
    }


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--sample") + 1]) if "--sample" in sys.argv else None
    print(run(n))
