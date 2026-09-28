"""Провайдер «Озон Фреш» на ценах из ВАШИХ прошлых корзин.

Официального API или MCP с ценами Озон Фреш для покупателей нет (проверено 28.09.2026),
поэтому текущие цены не запрашиваются: бот знает только то, что вы сами загрузили,
с датой загрузки. Сайт Озона не парсится, защита не обходится.

Условия доставки Озон Фреш неизвестны: по умолчанию не учитываются (0 ₽),
их можно указать в .env: OZON_FRESH_DELIVERY_FEE, OZON_FRESH_FREE_FROM, OZON_FRESH_MIN_ORDER.
"""
from __future__ import annotations

from typing import Optional

import config
import price_history
from models import DeliveryTerms, Offer
from providers.base import PriceProvider
from textnorm import stems
from units import Pack


class OzonFreshHistoryProvider(PriceProvider):
    service_id = "ozon_fresh"
    display_name = "Озон Фреш"
    homepage = "https://www.ozon.ru"   # главная страница Озона; раздел Фреш — в приложении/на сайте

    def __init__(self, user_id: Optional[int]):
        self.user_id = user_id
        self._entries = price_history.entries(user_id, self.service_id)

    @property
    def has_data(self) -> bool:
        return bool(self._entries)

    def search(self, query: str, region: str, limit: int = 5) -> list[Offer]:
        q = stems(query)
        scored = []
        for n, e in enumerate(self._entries):
            score = len(q & stems(e["name"] + " " + e.get("brand", "")))
            if score:
                scored.append((score, n, e))
        scored.sort(key=lambda x: -x[0])
        return [
            Offer(
                offer_id=f"ozh-{n}", service=self.service_id, name=e["name"], brand=e.get("brand", ""),
                pack=Pack(e["pack"][0], e["pack"][1]) if e.get("pack") else None,
                price=float(e["price"]), region="цена из вашей корзины",
                fetched_at=e["date"], source="user-cart",
            )
            for _, n, e in scored[:limit]
        ]

    def delivery_terms(self, region: str) -> DeliveryTerms:
        return DeliveryTerms(
            service=self.service_id, delivery_fee=config.OZON_FRESH_DELIVERY_FEE,
            free_delivery_from=config.OZON_FRESH_FREE_FROM, min_order=config.OZON_FRESH_MIN_ORDER,
            region=region, fetched_at="", source="user-settings",
            unknown=not (config.OZON_FRESH_DELIVERY_FEE or config.OZON_FRESH_MIN_ORDER),
        )

    def source_note(self) -> str:
        last = max((e["date"] for e in self._entries), default="—")
        delivery = ("доставка — из ваших настроек" if config.OZON_FRESH_DELIVERY_FEE or config.OZON_FRESH_MIN_ORDER
                    else "доставка и мин. заказ неизвестны — не учтены")
        return (f"цены из ваших корзин (товаров: {len(self._entries)}, последняя загрузка {last}), "
                f"текущие цены не проверяются; {delivery}")

    def order_instruction(self) -> str:
        return ("Откройте приложение Ozon → раздел «Fresh», укажите адрес и найдите товары поиском. "
                "Цены могли измениться с момента вашей прошлой покупки.")
