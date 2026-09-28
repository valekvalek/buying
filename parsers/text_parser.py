"""Разбор корзины, присланной текстом.

Поддерживаемый формат (одна позиция на строку):
    Пятёрочка
    Молоко Простоквашино 2,5% 930 мл — 2 шт — 89.99 ₽
    Бананы 1 кг x1 139 руб
    Хлеб Бородинский 400 г; 1; 55; Самокат
Строка, в которой есть только название сервиса, задаёт сервис для следующих строк.
"""
from __future__ import annotations

import re

from models import CartItem
from parsers.brands import detect_brand
from services import normalize_service
from units import PACK_RE, parse_pack

SEP_RE = re.compile(r"\s+[—–-]\s+|\s*[;|\t]\s*")
PRICE_RE = re.compile(r"(\d+(?:[.,]\d{1,2})?)\s*(?:₽|руб\.?|р\.)", re.IGNORECASE)
QTY_X_RE = re.compile(r"(?:^|\s)[x×х\*]\s*(\d+)(?!\S)|(?:^|\s)(\d+)\s*[x×х](?=\s|$)", re.IGNORECASE)
QTY_FIELD_RE = re.compile(r"^(\d+)\s*(?:шт\.?|уп\.?)?$", re.IGNORECASE)
NUMBER_RE = re.compile(r"^\d+(?:[.,]\d{1,2})?$")


def _to_float(s: str) -> float:
    return float(s.replace(",", "."))


def parse_line(line: str, current_service: str) -> CartItem | None:
    fields = [f.strip() for f in SEP_RE.split(line) if f.strip()]
    if not fields:
        return None
    name, price, qty, service = fields[0], None, None, current_service

    # Поля после названия: цена, количество, сервис
    for f in fields[1:]:
        m = PRICE_RE.search(f)
        if m:
            price = _to_float(m.group(1))
        elif QTY_FIELD_RE.match(f) and qty is None:
            qty = float(QTY_FIELD_RE.match(f).group(1))
        elif NUMBER_RE.match(f):
            price = _to_float(f)            # голое число после количества = цена
        elif normalize_service(f):
            service = normalize_service(f)
        else:
            name += " " + f

    # Цена и количество могли остаться внутри названия: «Бананы 1 кг x1 139 руб»
    if price is None:
        m = None
        for m in PRICE_RE.finditer(name):
            pass
        if m:
            price = _to_float(m.group(1))
            name = name[:m.start()] + name[m.end():]
    if qty is None:
        m = QTY_X_RE.search(name)
        if m:
            qty = float(m.group(1) or m.group(2))
            name = name[:m.start()] + name[m.end():]
    inline_service = normalize_service(name)
    if inline_service:
        service = inline_service
        name = re.sub(r"\((?:[^)]*)\)", "", name)   # «(Самокат)» в конце строки

    name = re.sub(r"\s+", " ", name).strip(" ,.-—")
    if not name or not re.search(r"[a-zа-яё]", name, re.IGNORECASE):
        return None
    return CartItem(
        name=name, brand=detect_brand(name), pack=parse_pack(name),
        qty=qty or 1, price=price, service=service,
    )


def parse_text(text: str) -> list[CartItem]:
    items, current_service = [], ""
    for raw in text.splitlines():
        line = re.sub(r"^\s*(?:\d+[.)]|[•*–—-])\s+", "", raw).strip()   # убираем «1.», «•», «-»
        if not line:
            continue
        service = normalize_service(line)
        # Строка-заголовок: только название сервиса, без цифр
        if service and not re.search(r"\d", line) and len(line) <= 30:
            current_service = service
            continue
        item = parse_line(line, current_service)
        if item:
            items.append(item)
    return items
