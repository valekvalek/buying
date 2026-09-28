"""Проверки логики без сети. Запуск: python -m pytest"""
from pathlib import Path

import config
import matching
from comparison import compare, split_two
from models import CartItem, DeliveryTerms, Match, Offer
from parsers.csv_parser import parse_csv
from parsers.text_parser import parse_text
from pipeline import analyze
from units import Pack, packs_needed, parse_pack

DATA = Path(__file__).resolve().parent.parent / "data"


def test_parse_pack():
    assert parse_pack("Молоко 930 мл") == Pack(0.93, "л")
    assert parse_pack("Вода 1,5л") == Pack(1.5, "л")
    assert parse_pack("Сыр 200 г") == Pack(0.2, "кг")
    assert parse_pack("Яйца С1 10 шт") == Pack(10, "шт")
    assert parse_pack("Хлеб") is None


def test_packs_needed():
    assert packs_needed(1.86, Pack(0.95, "л"), 2) == 2   # 2×930 мл -> 2×950 мл
    assert packs_needed(1.86, Pack(0.5, "л"), 2) == 4
    assert packs_needed(None, None, 3) == 3


def test_parse_text_sample():
    items = parse_text((DATA / "sample_cart.txt").read_text(encoding="utf-8"))
    assert len(items) == 9
    milk = items[0]
    assert milk.brand == "Простоквашино" and milk.qty == 2 and milk.price == 96.99
    assert milk.pack == Pack(0.93, "л") and milk.service == "pyaterochka"
    assert items[-1].service == "samokat"


def test_parse_text_inline_formats():
    items = parse_text("Бананы 1 кг x2 139 руб (Самокат)\nХлеб Бородинский 400 г; 1; 55; Чижик")
    assert items[0].name == "Бананы 1 кг" and items[0].qty == 2 and items[0].price == 139
    assert items[0].service == "samokat"
    assert items[1].price == 55 and items[1].service == "chizhik"


def test_parse_csv_sample():
    items = parse_csv((DATA / "sample_cart.csv").read_bytes())
    assert len(items) == 5
    assert items[0].brand == "Домик в деревне" and items[0].service == "lavka"


def _offer(pack="930 мл", brand="Простоквашино", price=90.0, sid="samokat"):
    return Offer("x", sid, "Молоко", brand, parse_pack(pack), price, "Москва", "2026-09-28", "mock")


def test_validate_downgrades_exact_to_analog():
    item = CartItem("Молоко", "Простоквашино", Pack(0.93, "л"), 2, 95.0, "pyaterochka")
    m = matching.validate(item, _offer(brand="Домик в деревне", pack="1 л"), "exact", "", 0.9)
    assert m.kind == "analog" and not m.uncertain
    assert any("бренд" in r for r in m.reasons) and any("фасовка" in r for r in m.reasons)


def test_validate_flags_uncertain():
    item = CartItem("Молоко", "Простоквашино", Pack(0.93, "л"), 1, 95.0)
    assert matching.validate(item, _offer(), "exact", "", 0.5).uncertain            # низкая уверенность
    assert matching.validate(item, _offer(pack="900 г"), "analog", "", 0.9).uncertain  # л vs кг
    assert matching.validate(item, _offer(price=500), "exact", "", 0.9).uncertain     # цена за л ×5


def test_llm_answer_is_checked(monkeypatch):
    """Ответ LLM с выдуманным id или чужим сервисом отбрасывается."""
    monkeypatch.setattr(config, "LLM_ENABLED", True)
    fake = {"matches": [
        {"service": "samokat", "candidate_id": "x", "match_type": "exact", "reason": "", "confidence": 0.95},
        {"service": "chizhik", "candidate_id": "no-such-id", "match_type": "exact", "reason": "", "confidence": 1},
        {"service": "lavka", "candidate_id": "x", "match_type": "exact", "reason": "", "confidence": 1},
    ]}
    monkeypatch.setattr(matching, "ask_json", lambda *a, **k: fake)
    item = CartItem("Молоко", "Простоквашино", Pack(0.93, "л"), 1, 95.0)
    res = matching._match_llm(item, {"samokat": [_offer()], "chizhik": [], "lavka": []})
    assert list(res) == ["samokat"] and res["samokat"].kind == "exact"


def _terms(sid, fee=100, free=None, min_order=0):
    return DeliveryTerms(sid, fee, free, min_order, "Москва", "2026-09-28", "mock")


def test_split_respects_min_order():
    items = [CartItem("A", pack=Pack(1, "кг"), price=100), CartItem("B", pack=Pack(1, "кг"), price=100)]

    def m(sid, price):
        return Match(items[0], sid, _offer(sid=sid, price=price), "exact", packs_needed=1)

    matched = [{"a": m("a", 100), "b": m("b", 50)}, {"a": m("a", 100), "b": m("b", 60)}]
    terms = {"a": _terms("a", fee=0), "b": _terms("b", fee=0, min_order=200)}
    # b дешевле, но его мин. сумма 200 недостижима -> разбивки нет
    assert split_two("a", "b", items, matched, terms) is None
    terms["b"] = _terms("b", fee=0, min_order=0)
    split = split_two("a", "b", items, matched, terms)
    assert split.total == 150   # в каждом магазине минимум одна позиция
    cmp = compare(items, matched, terms)
    assert cmp.best_single.orders[0].service == "b" and cmp.best_single.total == 110
    assert cmp.best_split.total > cmp.best_single.total


def test_full_pipeline_without_llm(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    items = parse_text((DATA / "sample_cart.txt").read_text(encoding="utf-8"))
    text = "\n".join(analyze(items, "Москва"))
    assert "ВСЁ ИЗ ОДНОГО МАГАЗИНА" in text and "РАЗБИТЬ МЕЖДУ ДВУМЯ" in text
    assert "ЭКОНОМИЯ" in text and "[uncertain]" in text and "ВЫМЫШЛЕННЫЕ" in text
    assert "Москва" in text and "2026-09-28" in text   # регион и дата цен видны в отчёте
