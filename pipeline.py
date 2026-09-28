"""Полный цикл: позиции корзины -> сопоставление -> расчёт -> текст отчёта."""
from __future__ import annotations

from comparison import compare
from matching import match_cart
from models import CartItem
from providers import get_providers
from report import build_report


def analyze(items: list[CartItem], region: str) -> list[str]:
    providers = get_providers()
    terms = {sid: p.delivery_terms(region) for sid, p in providers.items()}
    matched = match_cart(items, providers, region)
    cmp = compare(items, matched, terms)
    return build_report(items, matched, cmp, terms, providers, region)
