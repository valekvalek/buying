"""Нормализация названий товаров: слова, «основы» слов, жирность."""
from __future__ import annotations

import html
import re
from typing import Optional

_ENDINGS = sorted([
    "ами", "ями", "ого", "его", "ому", "ему", "ыми", "ими",
    "ов", "ев", "ей", "ой", "ый", "ий", "ая", "яя", "ое", "ее", "ые", "ие", "ую", "юю",
    "ом", "ем", "ам", "ям", "ах", "ях", "ых", "их",
    "а", "я", "о", "е", "ы", "и", "у", "ю", "ь", "й",
], key=len, reverse=True)

# Слова, которые ничего не говорят о товаре
STOP_WORDS = {"в", "во", "с", "со", "и", "для", "на", "из", "по", "без", "шт", "г", "гр", "кг", "мл", "л",
              "уп", "упаковка", "вес", "пакет", "бутылке", "бутылка", "пэт", "ст", "б"}

FAT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def clean(text: str) -> str:
    """HTML-сущности, неразрывные пробелы, ё -> е, нижний регистр."""
    return html.unescape(text or "").replace("\xa0", " ").lower().replace("ё", "е")


def words(text: str) -> list[str]:
    """Слова без цифр (фасовка и проценты разбираются отдельно). «С1», «С0» сохраняются."""
    out = []
    for w in re.findall(r"[a-zа-я0-9]+", clean(text)):
        if w in STOP_WORDS:
            continue
        if re.fullmatch(r"[сc][0-9в]", w):   # категория яиц: С0, С1, СВ
            out.append(w.replace("c", "с"))
        elif not re.search(r"\d", w) and len(w) >= 2:
            out.append(w)
    return out


def stem(word: str) -> str:
    """Очень простая «основа» слова: срезаем окончание и берём первые 5 букв.
    бананы/банан -> банан, яйцо/яйца -> яйц, сгущенное/сгущенка -> сгуще."""
    for end in _ENDINGS:
        if word.endswith(end) and len(word) - len(end) >= 3:
            word = word[: -len(end)]
            break
    return word[:5]


def stems(text: str) -> set[str]:
    return {stem(w) for w in words(text)}


def first_stem(text: str) -> str:
    """Основа первого значимого слова — обычно это тип товара («молоко», «сыр»)."""
    ws = words(text)
    return stem(ws[0]) if ws else ""


def fat_percent(text: str) -> Optional[float]:
    m = FAT_RE.search(clean(text))
    return float(m.group(1).replace(",", ".")) if m else None
