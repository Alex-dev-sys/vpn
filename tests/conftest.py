import os

import pytest


TEST_DB_URL = "sqlite+aiosqlite:///data/test_bot.db"


@pytest.fixture(autouse=True)
def isolated_test_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    yield
