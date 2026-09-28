"""Реестр провайдеров. Чтобы подключить реальный источник — поменяйте класс здесь."""
from __future__ import annotations

from providers.base import PriceProvider
from providers.mock_provider import MockProvider

SERVICE_IDS = ["pyaterochka", "samokat", "lavka", "vkusvill", "chizhik"]


def get_providers() -> dict[str, PriceProvider]:
    # Пример замены, когда появится проверенный источник:
    #   from providers.samokat import SamokatRealProvider
    #   providers["samokat"] = SamokatRealProvider()
    return {sid: MockProvider(sid) for sid in SERVICE_IDS}
