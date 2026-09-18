# -*- coding: utf-8 -*-
"""Алгоритм должен ставить реально проданные ники в правильный порядок.

Цены - продажи Fragment из data/sales_snapshot.json. Сами эти ники
calibrate.py из подгонки исключает, а похожие продажи берутся по префиксу
без самого ника: как будто продажи этого ника ещё не было.
"""

import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import features  # noqa: E402
import valuation  # noqa: E402

with open(os.path.join(ROOT, "tests", "known_sales.json")) as f:
    KNOWN = json.load(f)
with open(os.path.join(ROOT, "data", "sales_snapshot.json")) as f:
    SNAP = json.load(f)


def estimate(name):
    prefix = name[:3]
    sales = [(n, p) for n, p in SNAP.items() if n.startswith(prefix) and n != name]
    return valuation.evaluate(name, sales).price_ton


ESTIMATES = {n: estimate(n) for n in KNOWN}


def _ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    r = [0] * len(values)
    for i, idx in enumerate(order):
        r[idx] = i
    return r


def test_enough_cases():
    assert len(KNOWN) >= 30


def test_spearman():
    names = list(KNOWN)
    a = _ranks([KNOWN[n] for n in names])
    b = _ranks([ESTIMATES[n] for n in names])
    rho = statistics.correlation(a, b)
    print("spearman", round(rho, 3))
    assert rho >= 0.8


def test_pairs_far_apart_are_ordered():
    """Если один ник продан хотя бы в 10 раз дороже другого, оценка это видит."""
    names = list(KNOWN)
    pairs = bad = 0
    for x in names:
        for y in names:
            if KNOWN[x] >= KNOWN[y] * 10:
                pairs += 1
                bad += ESTIMATES[x] < ESTIMATES[y]
    print("пар", pairs, "ошибок", bad)
    assert bad / pairs <= 0.05


def test_tiers_increase():
    tiers = [(0, 50), (50, 1000), (1000, 20000), (20000, 10 ** 7)]
    means = []
    for lo, hi in tiers:
        vals = [ESTIMATES[n] for n, p in KNOWN.items() if lo <= p < hi]
        means.append(statistics.geometric_mean(vals))
    assert means == sorted(means)


def test_random_name_is_creation_price():
    sales = [("pgtie", 10), ("pgtpg", 10), ("pgtrc", 10), ("pgtv8", 10), ("pgteam", 104)]
    r = valuation.evaluate("pgtgg", sales, creation_ton=10)
    assert r.rank == 1 and not r.valuable and r.stars == 1
    assert any("Случайный набор" in c for c in r.cons)


def test_features():
    assert features.analyze("pgtgg").random_letters
    assert features.analyze("crypto").word_kind == "brand"
    assert features.analyze("7777").repeat_pretty
    assert features.analyze("abab").repeat_pretty
    assert features.analyze("moneyrain").two_words
    assert features.analyze("dengi").word_kind == "translit"
