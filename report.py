"""Текст ответа бота: сопоставление, итоги, экономия и инструкция для ручного заказа."""
from __future__ import annotations

from comparison import Comparison, Option
from models import CartItem, DeliveryTerms, Match
from providers.base import PriceProvider
from providers.mock_provider import MockProvider
from services import display_name
from units import parse_pack, unit_price


def rub(x: float) -> str:
    return f"{x:,.2f} ₽".replace(",", " ")


def _unit_price_text(price: float, item_or_offer) -> str:
    up = unit_price(price, item_or_offer.pack)
    return f" ({rub(up)}/{item_or_offer.pack.unit})" if up is not None else ""


def _match_line(m: Match) -> str:
    o = m.offer
    head = f"  • {display_name(m.service)}: {o.name}"
    if o.pack and not o.by_weight and parse_pack(o.name) != o.pack:
        head += f", {o.pack}"
    qty = f"{m.packs_needed:g} кг" if o.by_weight else f"{m.packs_needed:g}"
    head += f" — {rub(o.price)}{'/кг' if o.by_weight else ''} × {qty} = {rub(m.cost)}{_unit_price_text(o.price, o)}"
    tags = []
    if m.kind == "analog":
        tags.append("«аналог»")
    if m.uncertain:
        tags.append("[uncertain]")
    if tags:
        head += " " + " ".join(tags)
    if m.reasons and (m.kind == "analog" or m.uncertain):
        head += f"\n      причина: {'; '.join(m.reasons)}"
    return head


def matches_section(items: list[CartItem], matched: list[dict[str, Match]], services: list[str]) -> str:
    lines = ["📋 СОПОСТАВЛЕНИЕ ТОВАРОВ"]
    for n, (it, ms) in enumerate(zip(items, matched), 1):
        head = f"\n{n}. {it.name}"
        if it.pack and parse_pack(it.name) != it.pack:
            head += f", {it.pack}"
        head += f" × {it.qty:g}"
        if it.price is not None:
            head += f" — было {rub(it.price)}{_unit_price_text(it.price, it)}"
        if it.service:
            head += f" ({display_name(it.service)})"
        lines.append(head)
        for sid in services:
            lines.append(_match_line(ms[sid]) if sid in ms else f"  • {display_name(sid)}: нет подходящего товара")
    return "\n".join(lines)


def _option_text(opt: Option) -> str:
    parts = []
    for o in opt.orders:
        line = (f"{display_name(o.service)}: товары {rub(o.subtotal)} + доставка "
                f"{rub(o.delivery) if o.delivery else 'бесплатно'} = {rub(o.total)}")
        if o.below_min:
            line += f" ⚠️ не набрана мин. сумма заказа {rub(o.min_order)} (не хватает {rub(o.below_min)})"
        parts.append(line)
    return "\n".join(parts)


def totals_section(cmp: Comparison) -> str:
    lines = ["🏪 ВСЁ ИЗ ОДНОГО МАГАЗИНА"]
    for opt in cmp.singles:
        text = _option_text(opt)
        if opt.missing:
            text += f" ⚠️ нет {len(opt.missing)} поз.: " + ", ".join(i.name for i in opt.missing)
        lines.append(("✅ " if opt is cmp.best_single else "   ") + text)
    lines.append("")
    if cmp.best_single:
        lines.append(f"Лучший вариант из одного магазина: {display_name(cmp.best_single.orders[0].service)} — "
                     f"{rub(cmp.best_single.total)}")
    else:
        lines.append("Ни в одном магазине нельзя собрать всю корзину целиком (нет товаров или не набрана мин. сумма).")

    lines.append("\n🔀 РАЗБИТЬ МЕЖДУ ДВУМЯ СЕРВИСАМИ")
    if cmp.best_split:
        lines.append(_option_text(cmp.best_split))
        lines.append(f"Итого: {rub(cmp.best_split.total)}")
    else:
        lines.append("Подходящей разбивки на два сервиса нет.")

    lines.append("\n💰 ЭКОНОМИЯ")
    b = cmp.baseline
    best = min((o for o in (cmp.best_single, cmp.best_split) if o), key=lambda o: o.total, default=None)
    if b.total is not None:
        lines.append(f"Ваша корзина, как вы её покупали: {rub(b.total)}" + (f" ({b.note})" if b.note else ""))
        if cmp.best_single:
            lines.append(f"  • всё из одного магазина: {rub(b.total - cmp.best_single.total)}")
        if cmp.best_split:
            lines.append(f"  • разбивка на два сервиса: {rub(b.total - cmp.best_split.total)}")
    else:
        lines.append(f"Сравнить с исходной корзиной нельзя: {b.note}.")
    if cmp.best_single and cmp.best_split:
        diff = cmp.best_single.total - cmp.best_split.total
        if diff > 0:
            lines.append(f"Разбивка дешевле лучшего одного магазина на {rub(diff)}.")
        else:
            lines.append(f"Разбивка не выгоднее одного магазина (разница {rub(-diff)} в пользу одного магазина).")
    if best is not None and b.total is not None and b.total - best.total <= 0:
        lines.append("Ваша исходная корзина уже не дороже найденных вариантов.")
    return "\n".join(lines)


def checkout_section(opt: Option, providers: dict[str, PriceProvider]) -> str:
    """Список для ручного оформления заказа. Автоматического заказа нет."""
    lines = ["🧾 КАК ОФОРМИТЬ (вручную, автозаказа нет)"]
    for o in opt.orders:
        p = providers[o.service]
        lines.append(f"\n{p.display_name} — {rub(o.total)}")
        link = p.cart_link(o.matches)
        if link:
            lines.append(f"Ссылка на корзину (товары уже добавлены, заказ не оформлен): {link}")
            lines.append("Откройте ссылку, укажите адрес, проверьте наличие и оформите заказ сами.")
        else:
            lines.append(f"Сайт (главная страница, адрес не проверен — убедитесь сами): {p.homepage}")
            lines.append(p.order_instruction())
        for m in o.matches:
            mark = " (аналог)" if m.kind == "analog" else ""
            mark += " [uncertain — проверьте товар]" if m.uncertain else ""
            o_ = m.offer
            pack = f", {o_.pack}" if o_.pack and not o_.by_weight and parse_pack(o_.name) != o_.pack else ""
            qty = f"{m.packs_needed:g} кг" if m.offer.by_weight else f"{m.packs_needed:g} шт."
            lines.append(f"  ☐ {m.offer.name}{pack} — {qty}{mark}")
    return "\n".join(lines)


def build_report(items: list[CartItem], matched: list[dict[str, Match]], cmp: Comparison,
                 terms: dict[str, DeliveryTerms], providers: dict[str, PriceProvider], region: str) -> list[str]:
    """Возвращает список сообщений (Telegram ограничивает длину одного сообщения)."""
    header = f"🛒 Позиций в корзине: {len(items)}\n📍 Ваш регион: {region}\n🗂 Источники цен:"
    for sid, p in providers.items():
        header += f"\n  • {p.display_name}: {p.source_note()}"
    if any(isinstance(p, MockProvider) for p in providers.values()):
        header += "\n⚠️ Там, где указано mock, ЦЕНЫ ВЫМЫШЛЕННЫЕ — это не реальные цены сервисов!"

    messages = [header, matches_section(items, matched, list(terms)), totals_section(cmp)]
    best = min((o for o in (cmp.best_single, cmp.best_split) if o), key=lambda o: o.total, default=None)
    if best:
        messages.append(checkout_section(best, providers))
    return messages
