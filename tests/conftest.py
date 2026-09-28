"""Тесты не ходят в сеть: ВкусВилл в тестах берётся из mock-данных.
Цены из корзин пишутся во временный файл, а не в data/user_prices.json."""
import os
import tempfile

os.environ["VKUSVILL_SOURCE"] = "mock"
os.environ["USER_PRICES_PATH"] = os.path.join(tempfile.mkdtemp(), "user_prices.json")
