"""Справочник сервисов: как пользователь может их написать -> внутренний id."""
from __future__ import annotations

SERVICE_NAMES = {
    "pyaterochka": "Пятёрочка",
    "samokat": "Самокат",
    "lavka": "Яндекс Лавка",
    "vkusvill": "ВкусВилл",
    "chizhik": "Чижик",
}

_ALIASES = {
    "pyaterochka": ["пятёрочка", "пятерочка", "5ka", "пятерка", "пятёрка", "pyaterochka"],
    "samokat": ["самокат", "samokat"],
    "lavka": ["яндекс лавка", "лавка", "yandex lavka", "lavka"],
    "vkusvill": ["вкусвилл", "вкус вилл", "vkusvill"],
    "chizhik": ["чижик", "chizhik"],
}


def normalize_service(text: str) -> str:
    """'Пятерочка' -> 'pyaterochka'. Пустая строка, если не распознали."""
    t = (text or "").lower().strip()
    for sid, aliases in _ALIASES.items():
        if any(a in t for a in aliases):
            return sid
    return ""


def display_name(service_id: str) -> str:
    return SERVICE_NAMES.get(service_id, service_id or "неизвестный сервис")
