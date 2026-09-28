"""Сопоставление товаров по правилам — без LLM и без платных API.

Как выбирается кандидат:
  1. Тип товара должен совпасть: первое слово названия («Молоко», «Сыр», «Кофе»)
     есть в названии кандидата, и первое слово кандидата есть в позиции корзины.
  2. Взаимоисключающие виды товара отсекаются: молотый ≠ растворимый ≠ в зёрнах,
     газированная ≠ негазированная.
  3. Среди оставшихся считается балл: доля совпавших слов из названия (без бренда),
     плюс бренд, фасовка и жирность; лишние слова у кандидата («с малиной») — минус.
  4. Отличия бренда, фасовки, жирности и вида записываются причиной («аналог: другой бренд»).
     Слабые совпадения (низкий балл) помечаются [uncertain].
"""
from __future__ import annotations

from typing import Optional

from models import CartItem, Offer
from textnorm import clean, fat_percent, first_stem, stems, words
from units import same_pack

MIN_COVERAGE = 0.5   # меньше половины слов совпало — не считаем совпадением

# Внутри группы виды взаимоисключающие: кандидат другого вида отбрасывается
HARD_GROUPS = [
    {"молотый": ("молот",), "в зёрнах": ("зерн", "зерно"), "растворимый": ("раствор", "сублим"),
     "в капсулах": ("капсул",)},
    {"негазированная": ("негаз",), "газированная": ("газир",)},
]
# Признаки, отличие по которым допустимо, но делает товар аналогом
SOFT_FLAGS = {
    "варёная": ("варен",), "безлактозная": ("безлактоз",), "копчёная": ("копчен",),
    "сушёная": ("сушен",), "замороженная": ("зам", "заморож"), "мини": ("мини",),
    "детская": ("детск",), "в дрип-пакетах": ("дрип", "фильтр"),
}


def _has(ws: list[str], prefixes: tuple[str, ...]) -> bool:
    return any(w.startswith(p) for w in ws for p in prefixes)


def _kind_in_group(ws: list[str], group: dict) -> Optional[str]:
    for kind, prefixes in group.items():
        if _has(ws, prefixes):
            return kind
    return None


def brand_matches(item: CartItem, offer: Offer) -> bool:
    if not item.brand:
        return True
    b = clean(item.brand)
    return b == clean(offer.brand) or (not offer.brand and b in clean(offer.name))


def score(item: CartItem, offer: Offer) -> Optional[tuple[float, list[str]]]:
    """Балл совпадения и список отличий. None — это не тот товар."""
    item_words, offer_words = words(item.name), words(offer.name + " " + offer.brand)
    item_stems, offer_stems = stems(item.name), stems(offer.name + " " + offer.brand)
    brand_stems = stems(item.brand)

    # 1. тип товара
    if not first_stem(item.name) or first_stem(item.name) not in offer_stems:
        return None
    if first_stem(offer.name) not in item_stems:
        return None

    # 2. взаимоисключающие виды
    reasons = []
    for group in HARD_GROUPS:
        a, b = _kind_in_group(item_words, group), _kind_in_group(offer_words, group)
        if a and b and a != b:
            return None

    # 3. балл
    core = item_stems - brand_stems or item_stems
    coverage = len(core & offer_stems) / len(core)
    if coverage < MIN_COVERAGE:
        return None
    extra = offer_stems - item_stems - stems(offer.brand)
    value = coverage - min(0.3, 0.05 * len(extra))

    if brand_matches(item, offer):
        value += 0.1 if item.brand else 0
    else:
        reasons.append(f"другой бренд{f' ({offer.brand})' if offer.brand else ''}")

    if item.pack and offer.pack:
        if same_pack(item.pack, offer.pack):
            value += 0.2
        elif item.pack.unit == offer.pack.unit and not offer.by_weight:
            reasons.append(f"другая фасовка ({offer.pack} вместо {item.pack})")

    f1, f2 = fat_percent(item.name), fat_percent(offer.name)
    if f1 is not None and f2 is not None:
        if abs(f1 - f2) < 0.05:
            value += 0.1
        else:
            value -= 0.15
            reasons.append(f"другая жирность ({f2:g}% вместо {f1:g}%)")

    for label, prefixes in SOFT_FLAGS.items():
        if _has(item_words, prefixes) != _has(offer_words, prefixes):
            value -= 0.2
            where = "только у аналога" if _has(offer_words, prefixes) else "нет у аналога"
            reasons.append(f"отличается вид: «{label}» {where}")
    return value, reasons


def best_offer(item: CartItem, offers: list[Offer]) -> Optional[tuple[Offer, float, list[str]]]:
    best = None
    for o in offers:
        s = score(item, o)
        if s and (best is None or s[0] > best[1]):
            best = (o, s[0], s[1])
    return best
