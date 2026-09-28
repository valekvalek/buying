"""Разбор скриншота корзины через Claude (распознавание изображения)."""
from __future__ import annotations

import base64

import config
from llm import LLMError, ask_json
from models import CartItem
from parsers.brands import detect_brand
from services import normalize_service
from units import parse_pack

SCHEMA = {
    "type": "object",
    "properties": {
        "service": {"type": "string", "description": "Название сервиса, если видно на скриншоте, иначе пусто"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "brand": {"type": "string"},
                    "pack": {"type": "string", "description": "Фасовка как на экране, например '930 мл', или пусто"},
                    "qty": {"type": "number"},
                    "price_per_pack": {"type": ["number", "null"]},
                },
                "required": ["name", "brand", "pack", "qty", "price_per_pack"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["service", "items"],
    "additionalProperties": False,
}

SYSTEM = (
    "Ты извлекаешь позиции из скриншота корзины сервиса доставки продуктов. "
    "Переписывай только то, что видно на изображении, ничего не придумывай. "
    "Если на экране указана сумма за несколько штук, раздели её на количество, чтобы получить цену за упаковку. "
    "Если значение не видно — оставь пустую строку или null."
)


def parse_image(data: bytes, media_type: str = "image/jpeg") -> list[CartItem]:
    if not config.LLM_ENABLED:
        raise LLMError("Для распознавания скриншотов нужен ANTHROPIC_API_KEY в файле .env")
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                     "data": base64.standard_b64encode(data).decode("ascii")}},
        {"type": "text", "text": "Извлеки позиции корзины."},
    ]
    result = ask_json(SYSTEM, content, SCHEMA)
    service = normalize_service(result.get("service", ""))
    items = []
    for it in result["items"]:
        name = it["name"].strip()
        if not name:
            continue
        items.append(CartItem(
            name=name,
            brand=it["brand"].strip() or detect_brand(name),
            pack=parse_pack(it["pack"]) or parse_pack(name),
            qty=it["qty"] or 1,
            price=it["price_per_pack"],
            service=service,
        ))
    return items
