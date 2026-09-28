"""Цены из корзин пользователя — для сервисов без легального источника цен (Озон Фреш).

Хранится в JSON-файле (по умолчанию data/user_prices.json, в git не попадает).
Цены раздельные для каждого пользователя Telegram.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import date
from pathlib import Path
from typing import Optional

import config
from models import CartItem
from textnorm import clean
from units import Pack

_lock = threading.Lock()

# Для каких сервисов запоминаем цены из корзин
HISTORY_SERVICES = {"ozon_fresh"}


def _path() -> Path:
    return Path(config.USER_PRICES_PATH)


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}   # испорченный файл не должен ронять бота


def _key(name: str, pack: Optional[Pack]) -> str:
    return f"{clean(name)}|{pack.amount:g}{pack.unit}" if pack else clean(name)


def remember(user_id: Optional[int], items: list[CartItem], today: Optional[str] = None) -> int:
    """Сохраняет цены позиций из сервисов HISTORY_SERVICES. Возвращает, сколько цен сохранено."""
    if user_id is None:
        return 0
    today = today or date.today().isoformat()
    saved = 0
    with _lock:
        data = _load()
        for it in items:
            if it.service not in HISTORY_SERVICES or it.price is None:
                continue
            entries = data.setdefault(str(user_id), {}).setdefault(it.service, {})
            entries[_key(it.name, it.pack)] = {
                "name": it.name, "brand": it.brand,
                "pack": [it.pack.amount, it.pack.unit] if it.pack else None,
                "price": it.price, "date": today,
            }
            saved += 1
        if saved:
            _path().parent.mkdir(parents=True, exist_ok=True)
            tmp = _path().with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, _path())
    return saved


def entries(user_id: Optional[int], service: str) -> list[dict]:
    if user_id is None:
        return []
    with _lock:
        return list(_load().get(str(user_id), {}).get(service, {}).values())
