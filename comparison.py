"""Расчёт стоимости корзины: всё в одном магазине и разбивка между двумя сервисами."""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations, product
from typing import Optional

from models import CartItem, DeliveryTerms, Match

BRUTE_FORCE_LIMIT = 14   # до 2^14 вариантов разбивки перебираем полностью


@dataclass
class StoreOrder:
    service: str
    matches: list[Match]
    subtotal: float
    delivery: float
    min_order: float
    delivery_unknown: bool = False

    @property
    def total(self) -> float:
        return self.subtotal + self.delivery

    @property
    def below_min(self) -> float:
        """Сколько не хватает до минимальной суммы заказа (0 — хватает)."""
        return max(0.0, self.min_order - self.subtotal)


@dataclass
class Option:
    orders: list[StoreOrder]
    missing: list[CartItem] = field(default_factory=list)   # чего нет в этом варианте

    @property
    def total(self) -> float:
        return sum(o.total for o in self.orders)

    @property
    def valid(self) -> bool:
        return not self.missing and all(o.below_min == 0 for o in self.orders)


@dataclass
class Baseline:
    total: Optional[float]      # сколько заплатили по исходной корзине (товары + доставка)
    note: str = ""


@dataclass
class Comparison:
    singles: list[Option]
    best_single: Optional[Option]
    best_split: Optional[Option]
    baseline: Baseline


def _order(service: str, matches: list[Match], terms: DeliveryTerms) -> StoreOrder:
    subtotal = round(sum(m.cost for m in matches), 2)
    return StoreOrder(service, matches, subtotal, terms.fee_for(subtotal), terms.min_order, terms.unknown)


def single_store(sid: str, items: list[CartItem], matched: list[dict[str, Match]],
                 terms: DeliveryTerms) -> Option:
    found = [m[sid] for m in matched if sid in m]
    missing = [it for it, m in zip(items, matched) if sid not in m]
    return Option([_order(sid, found, terms)], missing)


def split_two(a: str, b: str, items: list[CartItem], matched: list[dict[str, Match]],
              terms: dict[str, DeliveryTerms]) -> Optional[Option]:
    """Лучшая разбивка корзины между сервисами a и b (с учётом доставки и мин. суммы)."""
    fixed_a, fixed_b, choice = [], [], []
    for m in matched:
        if a in m and b in m:
            choice.append((m[a], m[b]))
        elif a in m:
            fixed_a.append(m[a])
        elif b in m:
            fixed_b.append(m[b])
        else:
            return None   # позиции нет ни там, ни там

    def build(assign) -> Option:
        sa = fixed_a + [pair[0] for pair, side in zip(choice, assign) if side == 0]
        sb = fixed_b + [pair[1] for pair, side in zip(choice, assign) if side == 1]
        return Option([_order(a, sa, terms[a]), _order(b, sb, terms[b])])

    if len(choice) <= BRUTE_FORCE_LIMIT:
        variants = product((0, 1), repeat=len(choice))
    else:   # большая корзина: жадно — каждую позицию туда, где дешевле
        variants = [tuple(0 if x.cost <= y.cost else 1 for x, y in choice)]

    best = None
    for assign in variants:
        opt = build(assign)
        if not opt.orders[0].matches or not opt.orders[1].matches:
            continue   # один магазин пустой — это вариант «всё в одном», а не разбивка
        if opt.valid and (best is None or opt.total < best.total):
            best = opt
    return best


def baseline(items: list[CartItem], terms: dict[str, DeliveryTerms]) -> Baseline:
    """Сколько стоила корзина так, как её купили (по ценам из загруженной корзины)."""
    if any(it.price is None for it in items):
        return Baseline(None, "не у всех позиций указана цена")
    by_service: dict[str, float] = {}
    for it in items:
        by_service[it.service] = by_service.get(it.service, 0.0) + it.price * it.qty
    total, note = 0.0, ""
    for sid, sub in by_service.items():
        total += sub
        if sid in terms:
            total += terms[sid].fee_for(sub)
        else:
            note = "для части позиций сервис не указан — доставка по ним не учтена"
    return Baseline(round(total, 2), note)


def compare(items: list[CartItem], matched: list[dict[str, Match]],
            terms: dict[str, DeliveryTerms]) -> Comparison:
    singles = [single_store(sid, items, matched, t) for sid, t in terms.items()]
    singles.sort(key=lambda o: (not o.valid, len(o.missing), o.total))
    valid_singles = [o for o in singles if o.valid]
    best_single = valid_singles[0] if valid_singles else None

    splits = [s for a, b in combinations(terms, 2) if (s := split_two(a, b, items, matched, terms))]
    best_split = min(splits, key=lambda o: o.total) if splits else None
    return Comparison(singles, best_single, best_split, baseline(items, terms))
