import asyncio
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import select
import pytest

# Mock bot instance before importing scheduler to avoid circular deps or init issues
class DummyBot:
    async def send_message(self, chat_id, text, reply_markup=None):
        encoding = (getattr(sys.stdout, "encoding", None) or "utf-8")
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(f"\n--- NOTIFICATION to {chat_id} ---")
        print(safe_text)
        if reply_markup:
            print("KEYBOARD PRESENT")
        print("-------------------------------\n")

@pytest.mark.asyncio
async def test():
    # Setup DB
    from bot.database.core import init_db, async_session_factory
    from bot.database.models import User, Server, VPNKey
    from bot.services.scheduler import send_expiry_reminders, set_bot_instance

    # Ensure DB is initialized
    await init_db()
    set_bot_instance(DummyBot())

    async with async_session_factory() as session:
        # Create dummy user
        test_tg_id = 999999999
        stmt = select(User).where(User.telegram_id == test_tg_id)
        user = (await session.execute(stmt)).scalar()
        
        if not user:
            user = User(telegram_id=test_tg_id, username="test_notification_user")
            session.add(user)
            await session.commit()
            print(f"Created test user {user.id}")
        else:
            print(f"Using existing test user {user.id}")

        # Create dummy server if needed
        stmt = select(Server)
        server = (await session.execute(stmt)).scalar()
        if not server:
            server = Server(outline_api_url="http://mock", adguard_api_url="http://mock", adguard_user="u", adguard_pass="p")
            session.add(server)
            await session.commit()

        # Create VPN Key expiring in 2 days
        key = VPNKey(
            user_id=user.id,
            server_id=server.id,
            outline_key_id="test_notif_key",
            access_url="ss://test",
            expires_at=datetime.now() + timedelta(days=2),
            is_active=True,
            notification_status=0
        )
        session.add(key)
        await session.commit()
        print(f"Created key {key.id} expiring at {key.expires_at}")

        # Run scheduler task
        print("Running send_expiry_reminders...")
        try:
            await send_expiry_reminders()
        except Exception as e:
            print(f"Error: {e}")

        # Verify status updated
        await session.refresh(key)
        print(f"Key notification status: {key.notification_status}")
        assert key.notification_status == 1
        
        # Cleanup
        await session.delete(key)
        # Don't delete user/server to avoid breaking FKs if other checks run, but here it's isolated
        await session.commit()
        print("Cleanup done.")

if __name__ == "__main__":
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        pass
