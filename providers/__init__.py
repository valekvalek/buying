"""Реестр провайдеров. Чтобы подключить реальный источник — поменяйте класс здесь."""
from __future__ import annotations

from typing import Optional

import config
from providers.base import PriceProvider
from providers.mock_provider import MockProvider

SERVICE_IDS = ["pyaterochka", "samokat", "lavka", "vkusvill", "chizhik"]


def get_providers(user_id: Optional[int] = None) -> dict[str, PriceProvider]:
    providers: dict[str, PriceProvider] = {sid: MockProvider(sid) for sid in SERVICE_IDS}
    if config.VKUSVILL_SOURCE == "mcp":
        from providers.vkusvill_mcp import VkusvillMcpProvider
        providers["vkusvill"] = VkusvillMcpProvider()
    # Озон Фреш участвует, только если вы уже загружали его корзины
    from providers.ozon_fresh import OzonFreshHistoryProvider
    ozon = OzonFreshHistoryProvider(user_id)
    if ozon.has_data:
        providers["ozon_fresh"] = ozon
    # Остальные сервисы пока на mock-данных (см. TODO в providers/<сервис>.py)
    return providers
