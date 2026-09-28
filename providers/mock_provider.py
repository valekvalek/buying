"""Провайдер на mock-данных из data/mock_catalog.json. Цены ВЫМЫШЛЕННЫЕ."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from models import DeliveryTerms, Offer
from providers.base import PriceProvider
from textnorm import stems
from units import parse_pack

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


class MockProvider(PriceProvider):
    def __init__(self, service_id: str):
        data = load_catalog()["services"][service_id]
        self.service_id = service_id
        self.display_name = data["name"]
        self.homepage = data["homepage"]
        self._data = data

    def search(self, query: str, region: str, limit: int = 5) -> list[Offer]:
        catalog = load_catalog()
        q = stems(query)
        scored = []
        for p in self._data["products"]:
            if not p.get("in_stock", True):
                continue
            score = len(q & stems(p["name"] + " " + p["brand"]))
            if score:
                scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        return [
            Offer(
                offer_id=p["id"], service=self.service_id, name=p["name"], brand=p["brand"],
                pack=parse_pack(p["pack"]), price=float(p["price"]),
                # mock-каталог один на все регионы; реальный провайдер обязан учитывать region
                region=catalog["region"], fetched_at=catalog["fetched_at"], source="mock",
            )
            for _, p in scored[:limit]
        ]

    def source_note(self) -> str:
        return f"mock — вымышленные цены и доставка (дата данных {load_catalog()['fetched_at'][:10]})"

    def delivery_terms(self, region: str) -> DeliveryTerms:
        catalog = load_catalog()
        d = self._data
        return DeliveryTerms(
            service=self.service_id, delivery_fee=d["delivery_fee"],
            free_delivery_from=d.get("free_delivery_from"), min_order=d["min_order"],
            region=catalog["region"], fetched_at=catalog["fetched_at"], source="mock",
        )
