"""Общий интерфейс провайдера цен. Каждый сервис = отдельный класс с этим интерфейсом."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from models import DeliveryTerms, Match, Offer


class PriceProvider(ABC):
    service_id: str = ""
    display_name: str = ""
    # Главная страница сервиса — только для ручного оформления заказа.
    # Адреса НЕ проверены автоматически: перед использованием откройте их сами.
    homepage: str = ""

    @abstractmethod
    def search(self, query: str, region: str, limit: int = 5) -> list[Offer]:
        """Найти товары-кандидаты по текстовому запросу для заданного региона/адреса."""

    @abstractmethod
    def delivery_terms(self, region: str) -> DeliveryTerms:
        """Стоимость доставки, порог бесплатной доставки и минимальная сумма заказа."""

    def cart_link(self, matches: list[Match]) -> Optional[str]:
        """Ссылка на корзину с уже добавленными товарами, если сервис это официально умеет."""
        return None

    def source_note(self) -> str:
        """Откуда цены — для заголовка отчёта."""
        return "источник не указан"

    def order_instruction(self) -> str:
        """Как оформить заказ вручную (автозаказа в проекте нет и не будет)."""
        return (f"Откройте приложение или сайт «{self.display_name}», укажите свой адрес, "
                f"найдите каждый товар поиском по названию и добавьте в корзину нужное количество.")
