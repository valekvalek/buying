"""Вызов Claude с ответом строго по JSON-схеме."""
from __future__ import annotations

import json

import anthropic

import config

_client = None


class LLMError(RuntimeError):
    pass


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def ask_json(system: str, content: list | str, schema: dict, max_tokens: int = 8000) -> dict:
    """Отправляет запрос и возвращает разобранный JSON, соответствующий schema."""
    try:
        response = _get_client().beta.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            thinking={"type": "adaptive"},
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            # Если модель откажется отвечать, API сам повторит запрос на запасной модели.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        raise LLMError("Неверный ANTHROPIC_API_KEY") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Превышен лимит запросов к Anthropic API, попробуйте позже") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Ошибка Anthropic API: {e.status_code}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Нет соединения с Anthropic API") from e

    if response.stop_reason == "refusal":
        raise LLMError("Модель отказалась обрабатывать запрос")
    if response.stop_reason == "max_tokens":
        raise LLMError("Ответ модели обрезан (слишком большая корзина)")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError("Модель вернула некорректный JSON") from e
