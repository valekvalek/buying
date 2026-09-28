"""Общие структуры данных проекта."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from units import Pack


@dataclass
class CartItem:
    """Позиция из загруженной корзины пользователя."""
    name: str
    brand: str = ""
    pack: Optional[Pack] = None       # фасовка, например 930 мл
    qty: float = 1                    # сколько упаковок купили
    price: Optional[float] = None     # цена за 1 упаковку, ₽
    service: str = ""                 # id сервиса, где покупали (pyaterochka, ...)

    @property
    def total_amount(self) -> Optional[float]:
        """Общее количество в базовых единицах (кг / л / шт)."""
        return self.pack.amount * self.qty if self.pack else None


@dataclass
class Offer:
    """Товар из каталога сервиса (от провайдера цен)."""
    offer_id: str
    service: str
    name: str
    brand: str
    pack: Optional[Pack]
    price: float
    region: str          # адрес/регион, для которого получена цена
    fetched_at: str      # когда получена цена (ISO-дата)
    source: str          # "mock" или название реального источника
    in_stock: bool = True


@dataclass
class DeliveryTerms:
    service: str
    delivery_fee: float
    free_delivery_from: Optional[float]
    min_order: float
    region: str
    fetched_at: str
    source: str

    def fee_for(self, subtotal: float) -> float:
        if self.free_delivery_from is not None and subtotal >= self.free_delivery_from:
            return 0.0
        return self.delivery_fee


@dataclass
class Match:
    """Результат сопоставления позиции корзины с товаром одного сервиса."""
    item: CartItem
    service: str
    offer: Optional[Offer]
    kind: str = "none"          # "exact" | "analog" | "none"
    reasons: list[str] = field(default_factory=list)
    uncertain: bool = False
    packs_needed: int = 0       # сколько упаковок купить, чтобы набрать тот же объём

    @property
    def cost(self) -> float:
        return self.offer.price * self.packs_needed if self.offer else 0.0
