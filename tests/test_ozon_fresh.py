"""Озон Фреш: цены из корзин пользователя."""
from datetime import date, timedelta

import pytest

import config
import price_history
from matching import validate
from parsers.text_parser import parse_text
from pipeline import analyze
from providers import get_providers
from providers.ozon_fresh import OzonFreshHistoryProvider

OZON_CART = """Озон Фреш
Молоко Простоквашино 2,5% 930 мл — 2 шт — 91.99 ₽
Бананы 1 кг — 1 шт — 129 ₽
"""


@pytest.fixture(autouse=True)
def tmp_prices(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USER_PRICES_PATH", str(tmp_path / "prices.json"))


def test_ozon_service_recognised():
    items = parse_text(OZON_CART)
    assert {i.service for i in items} == {"ozon_fresh"}


def test_remember_and_search_per_user():
    assert price_history.remember(1, parse_text(OZON_CART)) == 2
    assert price_history.remember(None, parse_text(OZON_CART)) == 0   # без пользователя не сохраняем
    p = OzonFreshHistoryProvider(1)
    offers = p.search("Молоко Простоквашино", "Москва")
    assert offers[0].price == 91.99 and offers[0].source == "user-cart"
    assert not OzonFreshHistoryProvider(2).has_data   # чужие цены не видны


def test_newer_price_replaces_older():
    price_history.remember(1, parse_text(OZON_CART), today="2026-09-01")
    price_history.remember(1, parse_text("Озон Фреш\nБананы 1 кг — 1 шт — 119 ₽"), today="2026-09-20")
    bananas = [e for e in price_history.entries(1, "ozon_fresh") if e["name"].startswith("Бананы")]
    assert len(bananas) == 1 and bananas[0]["price"] == 119 and bananas[0]["date"] == "2026-09-20"


def test_ozon_only_in_comparison_when_user_has_data():
    assert "ozon_fresh" not in get_providers(7)
    price_history.remember(7, parse_text(OZON_CART))
    assert "ozon_fresh" in get_providers(7)


def test_stale_price_is_uncertain():
    old = (date.today() - timedelta(days=45)).isoformat()
    price_history.remember(1, parse_text(OZON_CART), today=old)
    item = parse_text("Молоко Простоквашино 2,5% 930 мл — 1 шт — 95 ₽")[0]
    offer = OzonFreshHistoryProvider(1).search("Молоко Простоквашино", "Москва")[0]
    m = validate(item, offer, "exact", "", 1.0)
    assert m.uncertain and any("45 дн." in r for r in m.reasons)


def test_full_pipeline_with_ozon(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    first = "\n".join(analyze(parse_text(OZON_CART), "Москва", user_id=5))
    assert "Запомнил цены Озон Фреш" in first
    later = "\n".join(analyze(parse_text("Пятёрочка\nМолоко Простоквашино 2,5% 930 мл — 2 шт — 96.99 ₽"),
                              "Москва", user_id=5))
    assert "Озон Фреш: Молоко Простоквашино" in later and "цена из вашей корзины от" in later
    assert "текущие цены не проверяются" in later
