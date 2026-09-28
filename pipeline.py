"""Полный цикл: позиции корзины -> сопоставление -> расчёт -> текст отчёта."""
from __future__ import annotations

from typing import Optional

import price_history
from comparison import compare
from matching import match_cart
from models import CartItem
from providers import get_providers
from report import build_report


def analyze(items: list[CartItem], region: str, user_id: Optional[int] = None) -> list[str]:
    saved = price_history.remember(user_id, items)   # цены Озон Фреш из этой корзины
    providers = get_providers(user_id)
    terms = {sid: p.delivery_terms(region) for sid, p in providers.items()}
    matched = match_cart(items, providers, region)
    cmp = compare(items, matched, terms)
    messages = build_report(items, matched, cmp, terms, providers, region)
    if saved:
        messages[0] += f"\n💾 Запомнил цены Озон Фреш из этой корзины: {saved} шт."
    return messages
