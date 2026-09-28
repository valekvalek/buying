"""Провайдер MCP ВкусВилла на поддельном сервере (без сети)."""
import json

import httpx

from comparison import Option, StoreOrder
from matching import validate
from models import CartItem, Match
from providers.vkusvill_mcp import VkusvillMcpProvider, simplify_query
from units import Pack

ITEMS = [
    {"id": 143, "xml_id": 143, "name": "Сметана 20%, 350&nbsp;г", "unit": "шт",
     "price": {"current": 158}, "weight": {"value": 0.35, "unit": "кг"}},
    {"id": 731, "xml_id": 731, "name": "Бананы", "unit": "кг", "price": {"current": 168}},
    {"id": 24116, "xml_id": 24116, "name": "Сок апельсиновый прямого отжима, 1&nbsp;л", "unit": "шт",
     "price": {"current": 565}, "weight": {"value": 1, "unit": "кг"}},
]


def _server(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        name, args = body["params"]["name"], body["params"]["arguments"]
        calls.append((name, args))
        if name == "vkusvill_products_search":
            # как настоящий поиск: запрос с фасовкой и процентами ничего не находит
            data = {"items": [] if any(ch.isdigit() for ch in args["q"]) else ITEMS}
        else:
            data = {"link": "https://vkusvill.ru/?share_basket=1"}
        text = json.dumps({"ok": True, "data": data}, ensure_ascii=False)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1,
                                         "result": {"content": [{"type": "text", "text": text}]}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_simplify_query():
    assert simplify_query("Сметана Простоквашино 20% 350 г") == "Сметана Простоквашино"


def test_search_maps_offers_and_retries_simpler_query():
    calls = []
    p = VkusvillMcpProvider(url="https://mcp.test/mcp", client=_server(calls))
    offers = p.search("Сметана Простоквашино 20% 350 г", "Москва")
    assert len(calls) == 2   # полный запрос ничего не нашёл -> повтор без цифр
    smetana, bananas, juice = offers
    assert smetana.name == "Сметана 20%, 350 г" and smetana.pack == Pack(0.35, "кг")
    assert bananas.by_weight and bananas.pack == Pack(1.0, "кг")
    assert juice.pack == Pack(1.0, "л")   # фасовка из названия, а не «1 кг» из веса
    assert smetana.source == "vkusvill-mcp" and smetana.fetched_at and "адрес не учитывается" in smetana.region


def test_weight_goods_bought_by_weight():
    p = VkusvillMcpProvider(url="https://mcp.test/mcp", client=_server([]))
    bananas = p.search("Бананы", "Москва")[1]
    m = validate(CartItem("Бананы", pack=Pack(1.5, "кг"), qty=1, price=150), bananas, "exact", "", 0.9)
    assert m.packs_needed == 1.5 and m.cost == 252


def test_cart_link():
    calls = []
    p = VkusvillMcpProvider(url="https://mcp.test/mcp", client=_server(calls))
    offer = p.search("Сметана", "Москва")[0]
    link = p.cart_link([Match(CartItem("Сметана"), "vkusvill", offer, "exact", packs_needed=2)])
    assert link == "https://vkusvill.ru/?share_basket=1"
    assert calls[-1] == ("vkusvill_cart_link_create", {"products": [{"xml_id": 143, "q": 2.0}]})


def test_unavailable_server_returns_empty():
    def down(request):
        raise httpx.ConnectError("нет сети")
    p = VkusvillMcpProvider(url="https://mcp.test/mcp", client=httpx.Client(transport=httpx.MockTransport(down)))
    assert p.search("Сметана", "Москва") == []
    assert "недоступен" in p.source_note()


def test_checkout_uses_cart_link():
    from report import checkout_section
    p = VkusvillMcpProvider(url="https://mcp.test/mcp", client=_server([]))
    offer = p.search("Сметана", "Москва")[0]
    m = Match(CartItem("Сметана"), "vkusvill", offer, "exact", packs_needed=1)
    text = checkout_section(Option([StoreOrder("vkusvill", [m], 158, 0, 0)]), {"vkusvill": p})
    assert "https://vkusvill.ru/?share_basket=1" in text and "заказ не оформлен" in text
