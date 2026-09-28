"""Сопоставление по правилам (без LLM)."""
from models import CartItem, Offer
from rules import best_offer, score
from textnorm import stems
from units import Pack, parse_pack


def offer(name, pack=None, brand="", price=100.0, by_weight=False):
    return Offer(name, "vkusvill", name, brand, parse_pack(pack or name), price, "Москва", "2026-09-28",
                 "test", by_weight=by_weight)


def item(name, brand="", qty=1):
    return CartItem(name, brand, parse_pack(name), qty, 100.0)


def test_stems_handle_word_forms():
    assert stems("Бананы") == stems("Банан")
    assert stems("Яйца куриные") == stems("Яйцо куриное")


def test_multipack():
    assert parse_pack("Гречка 5х80 г") == Pack(0.4, "кг")
    assert parse_pack("Вода 6 x 1,5 л") == Pack(9.0, "л")


def test_ground_coffee_never_matches_instant():
    it = item("Кофе молотый Jacobs Monarch 230 г", "Jacobs Monarch")
    assert score(it, offer("Кофе растворимый Monarch Original сублимированный 95 г")) is None
    assert score(it, offer("Кофе молотый Egoiste Espresso 250 г")) is not None


def test_product_type_must_match():
    it = item("Голубика 125 г")
    assert score(it, offer("Орехово-шоколадный микс с голубикой 30 г")) is None
    assert score(item("Сыр Российский Брест-Литовск 50% 200 г", "Брест-Литовск"),
                 offer("Масло сливочное Брест-Литовск 82,5% 180 г")) is None


def test_exact_when_brand_in_name_and_same_pack():
    it = item("Сыр Российский Брест-Литовск 50% 200 г", "Брест-Литовск")
    value, reasons = score(it, offer("Сыр Савушкин продукт Брест-Литовск Российский 50% полутвердый 200 г"))
    assert reasons == [] and value >= 0.75


def test_analog_reasons():
    it = item("Молоко Простоквашино 2,5% 930 мл", "Простоквашино")
    value, reasons = score(it, offer("Молоко 3,2% 1 л"))
    assert "другой бренд" in reasons[0]
    assert any("фасовка" in r for r in reasons) and any("жирность (3.2% вместо 2.5%)" in r for r in reasons)


def test_prefers_plain_product_over_flavoured():
    it = item("Круассан классический")
    o, _, _ = best_offer(it, [offer("Круассан с малиной, кафе 90 г"), offer("Круассан классический. Пекарня 56 г")])
    assert o.name.startswith("Круассан классический")


def test_soft_flag_makes_analog():
    _, reasons = score(item("Сгущенное молоко цельное 380 г"), offer("Молоко сгущенное вареное 380 г"))
    assert any("варёная" in r for r in reasons)
