from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from bot.database.core import async_session_factory, init_db
from bot.database.models import Payment, Server, User, VPNKey
from bot.handlers import payment as payment_module


class DummyBot:
    async def send_message(self, *_args, **_kwargs):
        return None


class DummyMessage:
    def __init__(self):
        self.bot = DummyBot()
        self.edited_text = None
        self.answered_text = None

    async def edit_text(self, text, reply_markup=None):
        self.edited_text = text
        return None

    async def answer(self, text, reply_markup=None):
        self.answered_text = text
        return None


class FakeOutlineKey:
    def __init__(self, key_id: str, access_url: str):
        self.id = key_id
        self.access_url = access_url


class FakeOutlineAPI:
    def __init__(self, _url: str):
        self.url = _url

    async def create_key(self, name: str):
        return FakeOutlineKey(key_id=f"fake-{name}", access_url=f"ss://fake-{name}")


@pytest.mark.asyncio
async def test_vpn_key_issued_after_payment_activation(monkeypatch):
    await init_db()
    monkeypatch.setattr(payment_module, "OutlineAPI", FakeOutlineAPI)

    unique_tg_id = int(datetime.now().timestamp() * 1000)

    async with async_session_factory() as session:
        server = Server(
            name="TestServer",
            outline_api_url="http://outline.local",
            adguard_api_url="http://adguard.local",
            adguard_user="admin",
            adguard_pass="pass",
            users_count=0,
            max_users=10,
            is_active=True,
        )
        user = User(telegram_id=unique_tg_id, username="issuance_test_user")
        session.add_all([server, user])
        await session.commit()
        await session.refresh(server)
        await session.refresh(user)

        payment = Payment(
            user_id=user.id,
            payment_code=f"T{unique_tg_id}",
            product_type="vpn",
            amount_ton=1.23,
            status="pending",
            expires_at=datetime.now() + timedelta(minutes=30),
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)

        message = DummyMessage()
        await payment_module.activate_subscription(session, user, payment, message)

        await session.refresh(payment)
        assert payment.status == "completed"
        assert payment.completed_at is not None

        created_key = (
            await session.execute(
                select(VPNKey).where(
                    VPNKey.user_id == user.id,
                    VPNKey.is_active == True,
                )
            )
        ).scalar_one_or_none()
        assert created_key is not None
        assert created_key.access_url.startswith("ss://fake-")

        await session.delete(created_key)
        await session.delete(payment)
        await session.delete(user)
        await session.delete(server)
        await session.commit()
