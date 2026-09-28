"""Сопоставление позиций корзины с товарами сервисов.

1. Провайдер каждого сервиса отдаёт до 10 кандидатов по названию.
2. Лучший кандидат выбирается по правилам (rules.py) — это основной режим, API не нужен.
   Если задан ANTHROPIC_API_KEY, выбор делает LLM (необязательно).
3. Код проверяет выбор: единицы измерения, фасовку, бренд, цену за кг/л.
   Всё сомнительное помечается [uncertain].
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import config
from llm import LLMError, ask_json
from models import CartItem, Match, Offer
from providers.base import PriceProvider
from rules import best_offer
from units import packs_needed, same_pack, unit_price

log = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.75
MAX_UNIT_PRICE_RATIO = 2.5   # цена за кг/л отличается больше чем в 2.5 раза -> подозрительно

SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "candidate_id": {"type": "string", "description": "id кандидата или пустая строка"},
                    "match_type": {"type": "string", "enum": ["exact", "analog", "none"]},
                    "reason": {"type": "string", "description": "Кратко по-русски: чем отличается аналог"},
                    "confidence": {"type": "number"},
                },
                "required": ["service", "candidate_id", "match_type", "reason", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["matches"],
    "additionalProperties": False,
}

SYSTEM = (
    "Ты сопоставляешь продукты между сервисами доставки. Для каждого сервиса выбери из кандидатов "
    "тот же товар (exact: тот же продукт, бренд и фасовка) или ближайший аналог (analog: тот же тип "
    "продукта, но другой бренд или фасовка; жирность, вкус и сорт должны совпадать или быть очень близки). "
    "Если подходящего нет — none и пустой candidate_id. Не выбирай товар другого типа. "
    "confidence — от 0 до 1, насколько ты уверен, что это тот же или равноценный продукт."
)


def _describe(item: CartItem) -> str:
    return (f"{item.name}; бренд: {item.brand or 'не указан'}; "
            f"фасовка: {item.pack or 'не указана'}")


def _offer_line(o: Offer) -> str:
    return f"- id={o.offer_id}: {o.name}; бренд: {o.brand or 'нет'}; фасовка: {o.pack or 'не указана'}"


def validate(item: CartItem, offer: Offer, kind: str, reason: str, confidence: float) -> Match:
    """Проверка совпадения кодом — не доверяем LLM вслепую."""
    reasons = [reason] if reason else []
    uncertain = confidence < MIN_CONFIDENCE

    if item.pack and offer.pack and item.pack.unit != offer.pack.unit:
        uncertain = True
        reasons.append(f"разные единицы: {item.pack.unit} и {offer.pack.unit}, цену за единицу сравнить нельзя")
    if not item.pack or not offer.pack:
        uncertain = True
        reasons.append("фасовка неизвестна")

    if kind == "exact":
        if item.brand and offer.brand and item.brand.lower() != offer.brand.lower():
            kind = "analog"
            reasons.append(f"другой бренд ({offer.brand})")
        if item.pack and offer.pack and not same_pack(item.pack, offer.pack):
            kind = "analog"
            reasons.append(f"другая фасовка ({offer.pack} вместо {item.pack})")

    if item.price and item.pack and offer.pack and item.pack.unit == offer.pack.unit:
        mine, theirs = unit_price(item.price, item.pack), unit_price(offer.price, offer.pack)
        if mine and theirs and max(mine, theirs) / min(mine, theirs) > MAX_UNIT_PRICE_RATIO:
            uncertain = True
            reasons.append("цена за кг/л сильно отличается — возможно, другой товар")

    same_unit = item.pack and offer.pack and item.pack.unit == offer.pack.unit
    if offer.by_weight and same_unit:
        quantity = round(item.total_amount, 3)   # весовой товар берём ровно по весу
    else:
        quantity = packs_needed(item.total_amount if same_unit else None, offer.pack, item.qty)
    return Match(
        item=item, service=offer.service, offer=offer, kind=kind, reasons=reasons, uncertain=uncertain,
        packs_needed=quantity,
    )


def _match_llm(item: CartItem, candidates: dict[str, list[Offer]]) -> dict[str, Match]:
    by_id = {o.offer_id: o for offers in candidates.values() for o in offers}
    blocks = [f"Сервис {sid}:\n" + ("\n".join(_offer_line(o) for o in offers) or "(кандидатов нет)")
              for sid, offers in candidates.items()]
    prompt = (f"Товар из корзины: {_describe(item)}\n\nКандидаты:\n\n" + "\n\n".join(blocks)
              + f"\n\nВерни по одному ответу для каждого сервиса: {', '.join(candidates)}.")
    result = ask_json(SYSTEM, prompt, SCHEMA)

    out = {}
    for m in result["matches"]:
        sid = m["service"]
        offer = by_id.get(m["candidate_id"])
        if sid not in candidates or m["match_type"] == "none" or offer is None or offer.service != sid:
            continue   # несуществующий id или чужой сервис — отбрасываем
        out[sid] = validate(item, offer, m["match_type"], m["reason"], float(m["confidence"]))
    return out


def _match_rules(item: CartItem, candidates: dict[str, list[Offer]]) -> dict[str, Match]:
    """Основной режим без LLM: выбор по правилам из rules.py."""
    out = {}
    for sid, offers in candidates.items():
        found = best_offer(item, offers)
        if not found:
            continue
        offer, value, reasons = found
        kind = "analog" if reasons else "exact"
        # балл 0.75+ — уверенное совпадение; ниже — validate() пометит [uncertain]
        out[sid] = validate(item, offer, kind, "; ".join(reasons), confidence=value)
    return out


def match_item(item: CartItem, providers: dict[str, PriceProvider], region: str) -> dict[str, Match]:
    query = item.name if item.brand.lower() in item.name.lower() else f"{item.name} {item.brand}".strip()
    candidates = {sid: p.search(query, region, limit=10) for sid, p in providers.items()}
    if config.LLM_ENABLED:
        try:
            return _match_llm(item, candidates)
        except LLMError as e:
            log.warning("LLM недоступна (%s), использую подбор по правилам", e)
    return _match_rules(item, candidates)


def match_cart(items: list[CartItem], providers: dict[str, PriceProvider], region: str) -> list[dict[str, Match]]:
    """Для каждой позиции: {service_id: Match}. Сервисы без совпадения в словаре отсутствуют."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda it: match_item(it, providers, region), items))
