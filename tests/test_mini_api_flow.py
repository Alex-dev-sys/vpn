import importlib
import os
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///data/test_bot.db"
os.environ["DASHBOARD_PASSWORD"] = "test-password"
os.environ["TON_WALLET"] = "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJKZ"
os.environ["BOT_TOKEN"] = "123456:TEST_TOKEN"
os.environ["MINI_APP_STRICT_AUTH"] = "0"
os.environ["HOT_WALLET_MNEMONICS"] = "test test test test test test test test test test test test test test test test test test test test test test test test"

import dashboard.app as dashboard_app_module


dashboard_app_module = importlib.reload(dashboard_app_module)


@pytest.fixture
def client(monkeypatch):
    async def fake_rate():
        return 250.0
    async def fake_get_wallet(_mnemonics: str):
        class _Wallet:
            async def get_balance(self):
                return 25.0
        return _Wallet()
    async def fake_margin(_session):
        return 10.0
    async def fake_card(_session):
        return "2200123412341234"
    async def fake_bank(_session):
        return "Сбербанк"
    async def fake_sbp(_session):
        return "+79990000000"

    monkeypatch.setattr(dashboard_app_module, "get_ton_rub_rate", fake_rate)
    monkeypatch.setattr(dashboard_app_module, "get_wallet", fake_get_wallet)
    monkeypatch.setattr(dashboard_app_module, "get_margin_percent", fake_margin)
    monkeypatch.setattr(dashboard_app_module, "get_card_number", fake_card)
    monkeypatch.setattr(dashboard_app_module, "get_bank_name", fake_bank)
    monkeypatch.setattr(dashboard_app_module, "get_sbp_phone", fake_sbp)
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


def test_mini_p2p_full_flow(client: TestClient):
    tg_id = 40000 + int(time.time()) % 10000

    bootstrap = client.get("/api/mini/p2p/bootstrap", params={"tg_id": tg_id})
    assert bootstrap.status_code == 200
    assert bootstrap.json()["max_ton"] > 0

    quote = client.post("/api/mini/p2p/quote", json={"tg_id": tg_id, "amount_ton": 2})
    assert quote.status_code == 200
    assert quote.json()["amount_rub"] > 0

    create = client.post(
        "/api/mini/p2p/create-order",
        json={"tg_id": tg_id, "amount_ton": 2, "wallet_address": "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJKZ"},
    )
    assert create.status_code == 200
    order = create.json()
    assert order["order_id"] > 0
    assert order["payment_requisites"]["card"] == "2200123412341234"

    paid = client.post("/api/mini/p2p/mark-paid", json={"tg_id": tg_id, "order_id": order["order_id"]})
    assert paid.status_code == 200
    assert paid.json()["status"] in {"waiting_confirmation", "processing"}

    status = client.get("/api/mini/p2p/order-status", params={"tg_id": tg_id, "order_id": order["order_id"]})
    assert status.status_code == 200
    assert status.json()["stage"] in {"paid", "processing"}
