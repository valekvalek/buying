"""Тесты не ходят в сеть: ВкусВилл в тестах берётся из mock-данных."""
import os

os.environ["VKUSVILL_SOURCE"] = "mock"
