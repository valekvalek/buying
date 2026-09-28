"""Общий интерфейс провайдера цен. Каждый сервис = отдельный класс с этим интерфейсом."""
from __future__ import annotations

from abc import ABC, abstractmethod

from models import DeliveryTerms, Offer


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

    def order_instruction(self) -> str:
        """Как оформить заказ вручную (автозаказа в проекте нет и не будет)."""
        return (f"Откройте приложение или сайт «{self.display_name}», укажите свой адрес, "
                f"найдите каждый товар поиском по названию и добавьте в корзину нужное количество.")
