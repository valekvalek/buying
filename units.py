"""Фасовка и единицы измерения: всё приводим к кг, л или шт."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

# единица в тексте -> (базовая единица, множитель)
_UNITS = {
    "кг": ("кг", 1.0), "kg": ("кг", 1.0),
    "г": ("кг", 0.001), "гр": ("кг", 0.001), "g": ("кг", 0.001),
    "л": ("л", 1.0), "l": ("л", 1.0),
    "мл": ("л", 0.001), "ml": ("л", 0.001),
    "шт": ("шт", 1.0), "pcs": ("шт", 1.0),
}

PACK_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(кг|kg|гр|г|g|мл|ml|л|l|шт|pcs)\.?(?![a-zа-яё])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Pack:
    amount: float   # в базовых единицах
    unit: str       # "кг" | "л" | "шт"

    def __str__(self) -> str:
        if self.unit == "кг" and self.amount < 1:
            return f"{self.amount * 1000:g} г"
        if self.unit == "л" and self.amount < 1:
            return f"{self.amount * 1000:g} мл"
        return f"{self.amount:g} {self.unit}"


def parse_pack(text: str) -> Optional[Pack]:
    """Находит фасовку в строке: '930 мл' -> Pack(0.93, 'л'). Берёт последнее совпадение."""
    if not text:
        return None
    found = PACK_RE.findall(text)
    if not found:
        return None
    number, unit = found[-1]
    base, factor = _UNITS[unit.lower()]
    return Pack(round(float(number.replace(",", ".")) * factor, 6), base)


def unit_price(price: float, pack: Optional[Pack]) -> Optional[float]:
    """Цена за 1 кг / 1 л / 1 шт."""
    if not pack or pack.amount <= 0:
        return None
    return price / pack.amount


def packs_needed(total_amount: Optional[float], pack: Optional[Pack], fallback_qty: float) -> int:
    """Сколько упаковок нужно, чтобы набрать тот же объём (допуск недобора 10%)."""
    if total_amount is None or pack is None or pack.amount <= 0:
        return max(1, math.ceil(fallback_qty))
    return max(1, math.ceil(total_amount / pack.amount - 0.1))


def same_pack(a: Optional[Pack], b: Optional[Pack], tolerance: float = 0.05) -> bool:
    if not a or not b or a.unit != b.unit:
        return False
    return abs(a.amount - b.amount) <= tolerance * max(a.amount, b.amount)
