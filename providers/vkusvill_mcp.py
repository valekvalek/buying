"""Провайдер «ВкусВилл» через официальный экспериментальный MCP-сервер ВкусВилла.

Проверено 28.09.2026: сервер отвечает без авторизации, инструменты
vkusvill_products_search (поиск с ценой, рейтингом, весом) и
vkusvill_cart_link_create (ссылка на корзину).

Ограничения (честно):
  - адрес/регион в поиск НЕ передаётся — цены общие, наличие по адресу видно только на сайте;
  - условий доставки и минимальной суммы заказа сервер не отдаёт — берём их из mock-данных;
  - сервер экспериментальный, формат ответа может измениться без предупреждения.
"""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime
from typing import Optional

import httpx

import config
from models import DeliveryTerms, Match, Offer
from providers.base import PriceProvider
from providers.mock_provider import MockProvider
from units import PACK_RE, Pack, parse_pack

log = logging.getLogger(__name__)

SEARCH_FIELDS = ["id", "xml_id", "name", "price", "unit", "weight", "rating", "url"]
CART_MAX_PRODUCTS = 20   # лимит инструмента vkusvill_cart_link_create
CART_MAX_QTY = 40


class VkusvillMcpError(RuntimeError):
    pass


def _clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(name).replace("\xa0", " ")).strip()


def simplify_query(query: str) -> str:
    """«Молоко Простоквашино 2,5% 930 мл» -> «Молоко Простоквашино»: без фасовки и цифр."""
    q = PACK_RE.sub(" ", query)
    words = [w for w in q.split() if not re.search(r"\d", w)]
    return " ".join(words)


def to_offer(item: dict, fetched_at: str) -> Offer:
    """Товар из ответа MCP -> Offer."""
    name = _clean_name(item["name"])
    by_weight = item.get("unit") == "кг" and not item.get("weight")
    if by_weight:
        pack = Pack(1.0, "кг")   # весовой товар: цена указана за 1 кг
    else:
        weight = item.get("weight") or {}
        pack = parse_pack(name)
        if pack is None and weight.get("value") and weight.get("unit") == "кг":
            pack = Pack(round(float(weight["value"]), 6), "кг")
    return Offer(
        offer_id=str(item["xml_id"]), service="vkusvill", name=name, brand="",
        pack=pack, price=float(item["price"]["current"]),
        region="адрес не учитывается (общие цены MCP ВкусВилла)",
        fetched_at=fetched_at, source="vkusvill-mcp", by_weight=by_weight,
    )


class VkusvillMcpProvider(PriceProvider):
    service_id = "vkusvill"
    display_name = "ВкусВилл"
    homepage = "https://vkusvill.ru"

    def __init__(self, url: str = "", client: Optional[httpx.Client] = None):
        self.url = url or config.VKUSVILL_MCP_URL
        self._client = client or httpx.Client(timeout=30)
        self._mock_terms = MockProvider("vkusvill")
        self.last_error = ""
        self.last_fetched_at = ""

    def _call(self, tool: str, arguments: dict) -> dict:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": tool, "arguments": arguments}}
        try:
            r = self._client.post(self.url, json=body,
                                  headers={"Accept": "application/json, text/event-stream"})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise VkusvillMcpError(f"MCP ВкусВилла недоступен: {e}") from e

        text = r.text
        if "text/event-stream" in r.headers.get("content-type", ""):
            # потоковый ответ: берём последнюю строку «data: {...}»
            data_lines = [l[5:].strip() for l in text.splitlines() if l.startswith("data:")]
            text = data_lines[-1] if data_lines else ""
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError as e:
            raise VkusvillMcpError("MCP ВкусВилла вернул не JSON") from e
        if "error" in envelope:
            raise VkusvillMcpError(f"MCP ВкусВилла: {envelope['error'].get('message', envelope['error'])}")
        result = envelope.get("result", {})
        payload = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise VkusvillMcpError(f"Неожиданный ответ MCP ВкусВилла: {payload[:200]}") from e
        if result.get("isError") or not data.get("ok", False):
            raise VkusvillMcpError(f"MCP ВкусВилла вернул ошибку: {payload[:200]}")
        return data["data"]

    def search(self, query: str, region: str, limit: int = 5) -> list[Offer]:
        # region не передаётся: у MCP ВкусВилла нет такого параметра
        queries = [query, simplify_query(query), " ".join(simplify_query(query).split()[:2])]
        seen = []
        for q in queries:
            if q and q not in seen:
                seen.append(q)
        fetched_at = datetime.now().astimezone().isoformat(timespec="minutes")
        try:
            for q in seen:
                data = self._call("vkusvill_products_search", {
                    "q": q[:255], "vvonly": 0, "mode": "custom", "fields": SEARCH_FIELDS})
                items = data.get("items") or []
                if items:
                    self.last_fetched_at = fetched_at
                    return [to_offer(it, fetched_at) for it in items[:limit]]
        except VkusvillMcpError as e:
            log.warning("%s", e)
            self.last_error = str(e)
        return []

    def delivery_terms(self, region: str) -> DeliveryTerms:
        # TODO: MCP ВкусВилла не отдаёт условия доставки — используем mock-значения
        return self._mock_terms.delivery_terms(region)

    def cart_link(self, matches: list[Match]) -> Optional[str]:
        products = [{"xml_id": int(m.offer.offer_id), "q": min(float(m.packs_needed), CART_MAX_QTY)}
                    for m in matches if m.offer]
        if not products or len(products) > CART_MAX_PRODUCTS:
            return None
        try:
            return self._call("vkusvill_cart_link_create", {"products": products}).get("link")
        except VkusvillMcpError as e:
            log.warning("%s", e)
            self.last_error = str(e)
            return None

    def source_note(self) -> str:
        if self.last_error and not self.last_fetched_at:
            return f"источник недоступен ({self.last_error})"
        when = self.last_fetched_at.replace("T", " ") or "—"
        return (f"реальные цены из MCP ВкусВилла на {when}, адрес не учитывается; "
                f"доставка и мин. заказ — mock")
