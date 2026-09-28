"""Определение бренда в названии товара."""
from __future__ import annotations

import re

from providers.mock_provider import load_catalog


def known_brands() -> set[str]:
    brands = set()
    for s in load_catalog()["services"].values():
        brands |= {p["brand"] for p in s["products"] if p["brand"]}
    return brands


def detect_brand(name: str) -> str:
    """Бренд в кавычках «...» или "..." , иначе — известный бренд из каталога."""
    m = re.search(r"[«\"]([^»\"]+)[»\"]", name)
    if m:
        return m.group(1).strip()
    low = name.lower()
    # длинные бренды проверяем первыми: «Jacobs Monarch» раньше, чем «Jacobs»
    for b in sorted(known_brands(), key=len, reverse=True):
        if b.lower() in low:
            return b
    return ""
