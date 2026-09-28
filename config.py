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

LLM_ENABLED = bool(ANTHROPIC_API_KEY)
