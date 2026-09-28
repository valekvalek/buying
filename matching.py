"""Сопоставление позиций корзины с товарами сервисов.

1. Провайдер каждого сервиса отдаёт до 5 кандидатов по названию.
2. LLM выбирает лучшего кандидата: точное совпадение, аналог или «нет».
3. Код ПРОВЕРЯЕТ ответ LLM: единицы измерения, фасовку, бренд, цену за кг/л.
   Всё сомнительное помечается [uncertain].
Без ANTHROPIC_API_KEY работает простой подбор по словам, и тогда ВСЕ совпадения [uncertain].
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import config
from llm import LLMError, ask_json
from models import CartItem, Match, Offer
from providers.base import PriceProvider
from providers.mock_provider import stems
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


def _match_heuristic(item: CartItem, candidates: dict[str, list[Offer]]) -> dict[str, Match]:
    """Запасной вариант без LLM: совпадение по словам. Всё помечается [uncertain]."""
    q = stems(item.name)
    kind_word = next(iter(sorted(stems(item.name.split()[0])) or [""]), "")   # «молоко», «сыр»…
    out = {}
    for sid, offers in candidates.items():
        best, best_score = None, 0.0
        for o in offers:
            s = stems(o.name + " " + o.brand)
            if kind_word and kind_word not in s:
                continue   # другой тип продукта (сыр ≠ масло того же бренда)
            score = len(q & s) / max(1, len(q | s))
            if score > best_score:
                best, best_score = o, score
        if best is None or best_score < 0.2:
            continue
        # бренд может быть только в названии (у ВкусВилла нет отдельного поля бренда)
        same_brand = item.brand.lower() == best.brand.lower() or (
            bool(item.brand) and not best.brand and item.brand.lower() in best.name.lower())
        exact = same_brand and same_pack(item.pack, best.pack)
        m = validate(item, best, "exact" if exact else "analog", "", confidence=0.0)
        m.reasons.insert(0, "подобрано без LLM, по словам в названии")
        out[sid] = m
    return out


def match_item(item: CartItem, providers: dict[str, PriceProvider], region: str) -> dict[str, Match]:
    query = f"{item.name} {item.brand}".strip()
    candidates = {sid: p.search(query, region) for sid, p in providers.items()}
    if config.LLM_ENABLED:
        try:
            return _match_llm(item, candidates)
        except LLMError as e:
            log.warning("LLM недоступна (%s), использую подбор по словам", e)
    return _match_heuristic(item, candidates)


def match_cart(items: list[CartItem], providers: dict[str, PriceProvider], region: str) -> list[dict[str, Match]]:
    """Для каждой позиции: {service_id: Match}. Сервисы без совпадения в словаре отсутствуют."""
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(lambda it: match_item(it, providers, region), items))
