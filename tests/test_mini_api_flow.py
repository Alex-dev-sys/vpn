import importlib
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///data/test_bot.db"
os.environ["DASHBOARD_PASSWORD"] = "test-password"
os.environ["TON_WALLET"] = "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJKZ"
os.environ["BOT_TOKEN"] = "123456:TEST_TOKEN"
os.environ["MINI_APP_STRICT_AUTH"] = "0"

import dashboard.app as dashboard_app_module


dashboard_app_module = importlib.reload(dashboard_app_module)


@pytest.fixture
def client(monkeypatch):
    async def fake_rate():
        return 250.0

    monkeypatch.setattr(dashboard_app_module, "get_ton_rub_rate", fake_rate)
    return TestClient(dashboard_app_module.app)


def test_mini_bootstrap_and_faq(client: TestClient):
    res_bootstrap = client.get("/api/mini/bootstrap", params={"tg_id": 10101})
    assert res_bootstrap.status_code == 200
    bootstrap = res_bootstrap.json()
    assert len(bootstrap["prices"]["plans"]) == 3

    res_faq = client.get("/api/mini/faq")
    assert res_faq.status_code == 200
    assert len(res_faq.json()["items"]) >= 3


def test_create_payment_idempotency_and_status(client: TestClient):
    payload = {"tg_id": 20202, "product": "vpn", "idempotency_key": "abc123"}
    r1 = client.post("/api/mini/create-payment", json=payload)
    r2 = client.post("/api/mini/create-payment", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200

    p1 = r1.json()
    p2 = r2.json()
    assert p1["payment_code"] == p2["payment_code"]
    assert p1["ton_link"].startswith("https://app.tonkeeper.com/transfer/")

    status = client.get(
        "/api/mini/payment-status",
        params={"tg_id": 20202, "payment_code": p1["payment_code"]},
    )
    assert status.status_code == 200
    assert status.json()["stage"] == "created"


def test_mini_auth_fallback_response(client: TestClient, monkeypatch):
    def _raise(*_args, **_kwargs):
        raise HTTPException(status_code=401, detail="Invalid Telegram initData")

    monkeypatch.setattr(dashboard_app_module, "_verify_mini_auth", _raise)
    res = client.get("/api/mini/bootstrap", params={"tg_id": 30303})
    assert res.status_code == 401
    body = res.json()
    assert body["error"] == "auth_failed"
    assert "fallback" in body
