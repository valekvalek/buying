"""Разбор CSV-файла с корзиной.

Колонки (русские или английские названия, порядок любой):
    название/name, бренд/brand, фасовка/pack, количество/qty, цена/price, сервис/service
Обязательна только колонка с названием. Разделитель — запятая или точка с запятой.
"""
from __future__ import annotations

import csv
import io

from models import CartItem
from parsers.brands import detect_brand
from services import normalize_service
from units import parse_pack

COLUMNS = {
    "name": ["название", "товар", "наименование", "name", "title"],
    "brand": ["бренд", "марка", "brand"],
    "pack": ["фасовка", "вес", "объем", "объём", "pack", "size"],
    "qty": ["количество", "кол-во", "кол", "qty", "quantity"],
    "price": ["цена", "price"],
    "service": ["сервис", "магазин", "service", "shop", "store"],
}


def _num(value: str) -> float | None:
    v = (value or "").replace("₽", "").replace("руб", "").replace(" ", "").replace(",", ".").strip(". ")
    try:
        return float(v)
    except ValueError:
        return None


def parse_csv(data: bytes) -> list[CartItem]:
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    header_map = {}
    for h in reader.fieldnames or []:
        key = h.strip().lower()
        for field, variants in COLUMNS.items():
            if key in variants:
                header_map[field] = h
    if "name" not in header_map:
        raise ValueError("В CSV нет колонки «название» (или name)")

    def get(row, field):
        return (row.get(header_map[field]) or "").strip() if field in header_map else ""

    items = []
    for row in reader:
        name = get(row, "name")
        if not name:
            continue
        pack_text = get(row, "pack")
        items.append(CartItem(
            name=name,
            brand=get(row, "brand") or detect_brand(name),
            pack=parse_pack(pack_text) or parse_pack(name),
            qty=_num(get(row, "qty")) or 1,
            price=_num(get(row, "price")),
            service=normalize_service(get(row, "service")),
        ))
    return items
