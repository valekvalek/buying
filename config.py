"""Настройки из файла .env."""
import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5").strip()
# Адрес/регион, для которого запрашиваются цены (цены зависят от адреса!)
REGION = os.getenv("REGION", "Москва").strip()

# Откуда брать цены ВкусВилла: "mcp" — официальный MCP-сервер ВкусВилла, "mock" — вымышленные данные
VKUSVILL_SOURCE = os.getenv("VKUSVILL_SOURCE", "mcp").strip().lower()
VKUSVILL_MCP_URL = os.getenv("VKUSVILL_MCP_URL", "https://mcp.vkusvill.ru/mcp").strip()

# Цены из ваших корзин (Озон Фреш): где хранить
USER_PRICES_PATH = os.getenv("USER_PRICES_PATH", "data/user_prices.json").strip()


def _money(name: str, default: str = "0") -> float:
    try:
        return float(os.getenv(name, default).replace(",", ".") or 0)
    except ValueError:
        return 0.0


# Условия доставки Озон Фреш неизвестны — впишите их сами, если хотите учитывать (0 = не учитывать)
OZON_FRESH_DELIVERY_FEE = _money("OZON_FRESH_DELIVERY_FEE")
OZON_FRESH_FREE_FROM = _money("OZON_FRESH_FREE_FROM") or None
OZON_FRESH_MIN_ORDER = _money("OZON_FRESH_MIN_ORDER")

LLM_ENABLED = bool(ANTHROPIC_API_KEY)
