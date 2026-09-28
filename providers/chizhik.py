"""Провайдер цен «Чижик».

Сейчас используется MockProvider("chizhik") (вымышленные данные).

TODO: реальный источник цен НЕ ПРОВЕРЕН. Официального публичного API у сервиса нет.
Прежде чем что-то подключать, проверьте:
  - пользовательское соглашение сервиса (разрешён ли автоматический сбор цен);
  - есть ли партнёрская программа / выгрузка / легальный агрегатор с данными.
Не обходите авторизацию по SMS и антибот-защиту. Эндпоинты и поля здесь не указаны намеренно.
"""
from __future__ import annotations

from models import DeliveryTerms, Offer
from providers.base import PriceProvider


class ChizhikRealProvider(PriceProvider):
    service_id = "chizhik"
    display_name = "Чижик"

    def search(self, query: str, region: str, limit: int = 5) -> list[Offer]:
        # TODO: реализовать через проверенный легальный источник.
        # Каждый Offer обязан содержать region и fetched_at (цены зависят от адреса и времени).
        raise NotImplementedError("Реальный источник цен для «Чижик» не подключён")

    def delivery_terms(self, region: str) -> DeliveryTerms:
        # TODO: условия доставки зависят от адреса — брать из проверенного источника.
        raise NotImplementedError("Условия доставки «Чижик» не подключены")
