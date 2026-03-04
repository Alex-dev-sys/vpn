"""
Admin Dashboard - FastAPI Web Application
"""
import os
import asyncio
import secrets
import bcrypt
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from urllib.parse import quote, parse_qsl

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()

# Sentry
import sentry_sdk
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)

# Import models
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.database.models import Base, User, Payment, VPNKey, DNSAccess, P2POrder, P2POrderStatus
from bot.services.rate_service import get_ton_rub_rate

# Database setup
DATABASE_URL = "sqlite+aiosqlite:///data/bot.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Password handling
ADMIN_PASSWORD_RAW = os.getenv("DASHBOARD_PASSWORD", "").strip()
if not ADMIN_PASSWORD_RAW:
    raise RuntimeError("DASHBOARD_PASSWORD is required and must not be empty")

# Check if already hashed (starts with $2b$)
if ADMIN_PASSWORD_RAW.startswith("$2b$"):
    ADMIN_PASSWORD_HASH = ADMIN_PASSWORD_RAW.encode()
else:
    ADMIN_PASSWORD_HASH = bcrypt.hashpw(ADMIN_PASSWORD_RAW.encode(), bcrypt.gensalt())

def verify_password(password: str) -> bool:
    return bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH)

# Session storage (simple in-memory with TTL)
sessions = {}
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "43200"))  # 12h
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1").strip() == "1"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    COOKIE_SAMESITE = "lax"

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Admin Dashboard", lifespan=lifespan)
app.state.limiter = limiter
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limit error handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "error": "Слишком много попыток. Подождите минуту."
    }, status_code=429)

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)
templates = Jinja2Templates(directory=templates_dir)

# IP Whitelist
ALLOWED_IPS = os.getenv("ALLOWED_IPS", "").strip()
allowed_ip_list = [ip.strip() for ip in ALLOWED_IPS.split(",") if ip.strip()] if ALLOWED_IPS else []

@app.middleware("http")
async def ip_whitelist_middleware(request: Request, call_next):
    """Block requests from non-whitelisted IPs (if whitelist is configured)"""
    if allowed_ip_list:
        client_ip = request.client.host
        # Allow localhost variations
        if client_ip not in allowed_ip_list and client_ip not in ["127.0.0.1", "::1", "localhost"]:
            return HTMLResponse("🚫 Access denied. Your IP is not whitelisted.", status_code=403)
    return await call_next(request)


def check_auth(request: Request) -> bool:
    """Check if user is authenticated"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return False
    expires_at = sessions.get(session_id)
    if not expires_at:
        return False
    if datetime.now() > expires_at:
        sessions.pop(session_id, None)
        return False
    return True


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not check_auth(request):
        return RedirectResponse("/login")
    return RedirectResponse("/dashboard")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# 2FA TOTP
import pyotp
TOTP_SECRET = os.getenv("TOTP_SECRET", "")  # If empty, 2FA is disabled

def verify_totp(code: str) -> bool:
    """Verify TOTP code"""
    if not TOTP_SECRET:
        return True  # 2FA disabled
    totp = pyotp.TOTP(TOTP_SECRET)
    return totp.verify(code, valid_window=1)


@app.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, password: str = Form(...), totp_code: str = Form("")):
    if not verify_password(password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный пароль"})
    
    # Check 2FA if enabled
    if TOTP_SECRET and not verify_totp(totp_code):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный 2FA код", "show_2fa": True})
    
    session_id = secrets.token_hex(16)
    sessions[session_id] = datetime.now() + timedelta(seconds=SESSION_TTL_SECONDS)
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=SESSION_TTL_SECONDS,
    )
    return response


@app.get("/2fa/setup", response_class=HTMLResponse)
async def setup_2fa(request: Request):
    """Generate new 2FA secret and QR code"""
    if not check_auth(request):
        return RedirectResponse("/login")
    
    new_secret = pyotp.random_base32()
    totp = pyotp.TOTP(new_secret)
    qr_uri = totp.provisioning_uri(name="Admin", issuer_name="VPN Bot Dashboard")
    
    return templates.TemplateResponse("2fa_setup.html", {
        "request": request,
        "secret": new_secret,
        "qr_uri": qr_uri
    })


@app.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id in sessions:
        del sessions[session_id]
    response = RedirectResponse("/login")
    response.delete_cookie("session_id")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not check_auth(request):
        return RedirectResponse("/login")
    
    async with async_session() as session:
        # Users stats
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        
        # Active subscriptions
        now = datetime.now()
        active_vpn = (await session.execute(
            select(func.count(VPNKey.id)).where(VPNKey.is_active == True, VPNKey.expires_at > now)
        )).scalar() or 0
        active_dns = (await session.execute(
            select(func.count(DNSAccess.id)).where(DNSAccess.is_active == True, DNSAccess.expires_at > now)
        )).scalar() or 0
        
        # Payments (VPN/DNS)
        completed_payments = (await session.execute(
            select(func.count(Payment.id)).where(Payment.status == "completed")
        )).scalar() or 0
        total_revenue_ton = (await session.execute(
            select(func.sum(Payment.amount_ton)).where(Payment.status == "completed")
        )).scalar() or 0
        
        # P2P Orders
        p2p_completed = (await session.execute(
            select(func.count(P2POrder.id)).where(P2POrder.status == P2POrderStatus.COMPLETED.value)
        )).scalar() or 0
        p2p_pending = (await session.execute(
            select(func.count(P2POrder.id)).where(P2POrder.status.in_([
                P2POrderStatus.PENDING.value, 
                P2POrderStatus.WAITING_CONFIRMATION.value
            ]))
        )).scalar() or 0
        p2p_revenue_ton = (await session.execute(
            select(func.sum(P2POrder.amount_ton)).where(P2POrder.status == P2POrderStatus.COMPLETED.value)
        )).scalar() or 0
        p2p_revenue_rub = (await session.execute(
            select(func.sum(P2POrder.amount_rub)).where(P2POrder.status == P2POrderStatus.COMPLETED.value)
        )).scalar() or 0
        
        # Today stats
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_users = (await session.execute(
            select(func.count(User.id)).where(User.created_at >= today)
        )).scalar() or 0
        today_payments = (await session.execute(
            select(func.count(Payment.id)).where(Payment.completed_at >= today, Payment.status == "completed")
        )).scalar() or 0
        today_p2p = (await session.execute(
            select(func.count(P2POrder.id)).where(P2POrder.completed_at >= today, P2POrder.status == P2POrderStatus.COMPLETED.value)
        )).scalar() or 0
    
    stats = {
        "total_users": total_users,
        "active_vpn": active_vpn,
        "active_dns": active_dns,
        "completed_payments": completed_payments,
        "total_revenue_ton": round(total_revenue_ton or 0, 2),
        "p2p_completed": p2p_completed,
        "p2p_pending": p2p_pending,
        "p2p_revenue_ton": round(p2p_revenue_ton or 0, 2),
        "p2p_revenue_rub": int(p2p_revenue_rub or 0),
        "today_users": today_users,
        "today_payments": today_payments,
        "today_p2p": today_p2p,
    }
    
    return templates.TemplateResponse("dashboard.html", {"request": request, "stats": stats})


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, q: str = ""):
    if not check_auth(request):
        return RedirectResponse("/login")
    
    async with async_session() as session:
        if q:
            # Search by telegram_id or username
            result = await session.execute(
                select(User).where(
                    (User.username.ilike(f"%{q}%")) | 
                    (User.telegram_id == int(q) if q.isdigit() else False)
                ).order_by(User.created_at.desc()).limit(100)
            )
        else:
            result = await session.execute(
                select(User).order_by(User.created_at.desc()).limit(100)
            )
        users = result.scalars().all()
    
    return templates.TemplateResponse("users.html", {"request": request, "users": users, "query": q})


@app.get("/logs", response_class=HTMLResponse)
async def audit_logs_page(request: Request):
    """View audit logs"""
    if not check_auth(request):
        return RedirectResponse("/login")
    
    async with async_session() as session:
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)
        )
        logs = result.scalars().all()
    
    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs})


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request):
    if not check_auth(request):
        return RedirectResponse("/login")
    
    async with async_session() as session:
        # VPN/DNS payments
        payments_result = await session.execute(
            select(Payment).order_by(Payment.created_at.desc()).limit(50)
        )
        payments = payments_result.scalars().all()
        
        # P2P orders
        p2p_result = await session.execute(
            select(P2POrder).order_by(P2POrder.created_at.desc()).limit(50)
        )
        p2p_orders = p2p_result.scalars().all()
    
    return templates.TemplateResponse("orders.html", {
        "request": request, 
        "payments": payments,
        "p2p_orders": p2p_orders
    })


# ============ CHART API ============

@app.get("/api/stats/chart")
async def chart_data(request: Request):
    """Get chart data for last 30 days"""
    if not check_auth(request):
        raise HTTPException(status_code=401)
    
    from datetime import date
    
    labels = []
    users_data = []
    revenue_data = []
    
    async with async_session() as session:
        for i in range(29, -1, -1):
            day = date.today() - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            
            # Users registered that day
            users_count = (await session.execute(
                select(func.count(User.id)).where(
                    User.created_at >= day_start,
                    User.created_at <= day_end
                )
            )).scalar() or 0
            
            # Revenue that day (completed payments)
            revenue = (await session.execute(
                select(func.sum(Payment.amount_ton)).where(
                    Payment.completed_at >= day_start,
                    Payment.completed_at <= day_end,
                    Payment.status == "completed"
                )
            )).scalar() or 0
            
            labels.append(day.strftime("%d.%m"))
            users_data.append(users_count)
            revenue_data.append(round(float(revenue), 2))
    
    return {
        "labels": labels,
        "users": users_data,
        "revenue": revenue_data
    }


# ============ ADMIN ACTIONS ============

from bot.database.models import AuditLog

async def log_action(session: AsyncSession, action: str, target_type: str, target_id: int, admin_ip: str, details: str = None):
    """Log admin action to audit log"""
    log = AuditLog(action=action, target_type=target_type, target_id=target_id, admin_ip=admin_ip, details=details)
    session.add(log)


@app.post("/api/user/{user_id}/ban")
async def ban_user(request: Request, user_id: int):
    """Ban a user"""
    if not check_auth(request):
        raise HTTPException(status_code=401)
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.is_banned = True
        await log_action(session, "ban_user", "user", user_id, request.client.host, f"@{user.username}")
        await session.commit()
    
    return RedirectResponse("/users", status_code=302)


@app.post("/api/user/{user_id}/unban")
async def unban_user(request: Request, user_id: int):
    """Unban a user"""
    if not check_auth(request):
        raise HTTPException(status_code=401)
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.is_banned = False
        await log_action(session, "unban_user", "user", user_id, request.client.host, f"@{user.username}")
        await session.commit()
    
    return RedirectResponse("/users", status_code=302)


@app.post("/api/p2p/{order_id}/confirm")
async def confirm_p2p_order(request: Request, order_id: int):
    """Confirm P2P order and send TON"""
    if not check_auth(request):
        raise HTTPException(status_code=401)
    
    async with async_session() as session:
        result = await session.execute(select(P2POrder).where(P2POrder.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Send TON to user wallet
        try:
            from bot.services.ton_wallet import send_ton
            tx_hash = await send_ton(order.wallet_address, order.amount_ton)
            order.tx_hash = tx_hash
            order.status = P2POrderStatus.COMPLETED.value
            order.completed_at = datetime.now()
            await log_action(session, "confirm_p2p", "p2p_order", order_id, request.client.host, f"{order.amount_ton} TON")
            await session.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return RedirectResponse("/orders", status_code=302)


@app.post("/api/p2p/{order_id}/cancel")
async def cancel_p2p_order(request: Request, order_id: int, reason: str = Form("")):
    """Cancel P2P order"""
    if not check_auth(request):
        raise HTTPException(status_code=401)
    
    async with async_session() as session:
        result = await session.execute(select(P2POrder).where(P2POrder.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        order.status = P2POrderStatus.CANCELED.value
        order.cancel_reason = reason or "Отменено админом"
        await log_action(session, "cancel_p2p", "p2p_order", order_id, request.client.host, reason)
        await session.commit()
    
    return RedirectResponse("/orders", status_code=302)


@app.post("/api/vpn/{key_id}/revoke")
async def revoke_vpn_key(request: Request, key_id: int):
    """Revoke VPN key"""
    if not check_auth(request):
        raise HTTPException(status_code=401)
    
    async with async_session() as session:
        result = await session.execute(select(VPNKey).where(VPNKey.id == key_id))
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(status_code=404, detail="Key not found")
        
        key.is_active = False
        await session.commit()
    
    return RedirectResponse("/users", status_code=302)


@app.get("/user/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: int):
    """User detail page"""
    if not check_auth(request):
        return RedirectResponse("/login")
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404)
        
        # Get user's VPN keys
        vpn_result = await session.execute(
            select(VPNKey).where(VPNKey.user_id == user_id)
        )
        vpn_keys = vpn_result.scalars().all()
        
        # Get user's DNS accesses
        dns_result = await session.execute(
            select(DNSAccess).where(DNSAccess.user_id == user_id)
        )
        dns_accesses = dns_result.scalars().all()
        
        # Get user's P2P orders
        p2p_result = await session.execute(
            select(P2POrder).where(P2POrder.user_id == user_id).order_by(P2POrder.created_at.desc())
        )
        p2p_orders = p2p_result.scalars().all()
        
        # Get user's payments
        payments_result = await session.execute(
            select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
        )
        payments = payments_result.scalars().all()
    
    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user": user,
        "vpn_keys": vpn_keys,
        "dns_accesses": dns_accesses,
        "p2p_orders": p2p_orders,
        "payments": payments
    })


# ============ MINI APP API ============

TON_WALLET = os.getenv("TON_WALLET", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "dns_saler_bot")
DNS_SERVER_IP = os.getenv("DNS_SERVER_IP", "")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "dns_vpn_support")
VPN_PRICE_RUB = int(os.getenv("VPN_PRICE_RUB", "150"))
DNS_PRICE_RUB = int(os.getenv("DNS_PRICE_RUB", "100"))
PRO_PRICE_RUB = int(os.getenv("PRO_PRICE_RUB", "200"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MINI_APP_STRICT_AUTH = os.getenv("MINI_APP_STRICT_AUTH", "0").strip() == "1"
TELEGRAM_INITDATA_MAX_AGE = int(os.getenv("TELEGRAM_INITDATA_MAX_AGE", "86400"))


def _verify_telegram_init_data(init_data: str) -> dict | None:
    """
    Validate Telegram WebApp initData signature.
    Returns parsed fields on success, None on failure.
    """
    if not init_data or not BOT_TOKEN:
        return None

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    recv_hash = parsed.get("hash")
    if not recv_hash:
        return None

    data_check_items = []
    for key in sorted(parsed.keys()):
        if key == "hash":
            continue
        data_check_items.append(f"{key}={parsed[key]}")
    data_check_string = "\n".join(data_check_items)

    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, recv_hash):
        return None

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        return None
    if auth_date <= 0:
        return None
    if (datetime.now() - datetime.fromtimestamp(auth_date)).total_seconds() > TELEGRAM_INITDATA_MAX_AGE:
        return None

    return parsed


def _verify_mini_auth(tg_id: int, init_data: str | None):
    """Verify tg_id against signed Telegram initData when strict mode is enabled."""
    if not MINI_APP_STRICT_AUTH:
        return

    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN is required for strict mini app auth")
    if not init_data:
        raise HTTPException(status_code=401, detail="Telegram initData is required")

    parsed = _verify_telegram_init_data(init_data)
    if not parsed:
        raise HTTPException(status_code=401, detail="Invalid Telegram initData")

    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="initData.user is missing")
    try:
        user_obj = json.loads(user_raw)
    except Exception:
        raise HTTPException(status_code=401, detail="initData.user is invalid")
    user_id = int(user_obj.get("id", 0))
    if user_id != tg_id:
        raise HTTPException(status_code=401, detail="tg_id mismatch")


def _generate_payment_code() -> str:
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(chars) for _ in range(8))


def _ton_to_nanoton(amount: float) -> int:
    return int(amount * 1_000_000_000)


def _ton_link(wallet: str, amount_ton: float, comment: str) -> str:
    nanotons = _ton_to_nanoton(amount_ton)
    return f"https://app.tonkeeper.com/transfer/{wallet}?amount={nanotons}&text={quote(comment)}"


async def _find_or_create_user(session: AsyncSession, tg_id: int) -> User:
    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(telegram_id=tg_id, username=None)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@app.get("/api/mini/bootstrap")
@limiter.limit("60/minute")
async def mini_bootstrap(request: Request, tg_id: int, init_data: str = ""):
    """Mini app bootstrap data: profile, prices, active subscriptions, support info."""
    _verify_mini_auth(tg_id, init_data)

    async with async_session() as session:
        user = await _find_or_create_user(session, tg_id)
        now = datetime.now()

        vpn_result = await session.execute(
            select(VPNKey).where(
                VPNKey.user_id == user.id,
                VPNKey.is_active == True,
                VPNKey.expires_at > now,
            ).order_by(VPNKey.expires_at.desc())
        )
        dns_result = await session.execute(
            select(DNSAccess).where(
                DNSAccess.user_id == user.id,
                DNSAccess.is_active == True,
                DNSAccess.expires_at > now,
            ).order_by(DNSAccess.expires_at.desc())
        )
        referrals_result = await session.execute(select(func.count(User.id)).where(User.referrer_id == user.id))
        vpn_keys = vpn_result.scalars().all()
        dns_accesses = dns_result.scalars().all()
        referrals_count = referrals_result.scalar() or 0

        rate = await get_ton_rub_rate()
        if not rate or rate <= 0:
            rate = 100.0

        def plan_item(code: str, title: str, subtitle: str, price_rub: int):
            return {
                "code": code,
                "title": title,
                "subtitle": subtitle,
                "price_rub": price_rub,
                "price_ton": round(price_rub / rate, 2),
            }

        plans = [
            plan_item("vpn", "VPN Start", "Стабильный Outline VPN на 30 дней", VPN_PRICE_RUB),
            plan_item("dns", "DNS Shield", "Приватный DNS с блокировкой рекламы", DNS_PRICE_RUB),
            plan_item("pro", "PRO Combo", "VPN + DNS + приоритетная поддержка", PRO_PRICE_RUB),
        ]

        ref_link = f"https://t.me/{BOT_USERNAME}?start={user.telegram_id}"
        active_until = None
        if vpn_keys or dns_accesses:
            max_vpn = max([v.expires_at for v in vpn_keys], default=None)
            max_dns = max([d.expires_at for d in dns_accesses], default=None)
            active_until = max(x for x in [max_vpn, max_dns] if x is not None).strftime("%d.%m.%Y")

        return JSONResponse(
            {
                "user": {
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "balance_ton": round(user.balance or 0.0, 2),
                    "referrals_count": referrals_count,
                    "ref_link": ref_link,
                },
                "status": {
                    "vpn_active": len(vpn_keys) > 0,
                    "dns_active": len(dns_accesses) > 0,
                    "active_until": active_until,
                    "state": "online" if (vpn_keys or dns_accesses) else "offline",
                },
                "prices": {
                    "rate_rub_per_ton": round(rate, 2),
                    "plans": plans,
                },
                "links": {
                    "bot": f"https://t.me/{BOT_USERNAME}",
                    "p2p": f"https://t.me/{BOT_USERNAME}?start=p2p",
                    "support": f"https://t.me/{SUPPORT_USERNAME}",
                },
                "install": {
                    "vpn_keys": [
                        {
                            "key_id": key.id,
                            "access_url": key.access_url,
                            "expires_at": key.expires_at.strftime("%d.%m.%Y"),
                        }
                        for key in vpn_keys
                    ],
                    "dns": [
                        {
                            "access_id": access.id,
                            "dns_server_ip": DNS_SERVER_IP,
                            "current_ip": access.current_ip,
                            "expires_at": access.expires_at.strftime("%d.%m.%Y"),
                        }
                        for access in dns_accesses
                    ],
                },
            }
        )


@app.post("/api/mini/create-payment")
@limiter.limit("20/minute")
async def mini_create_payment(request: Request, payload: dict):
    """
    Create payment for mini app checkout.
    Body: { "tg_id": 123, "product": "vpn|dns|pro" }
    """
    tg_id = int(payload.get("tg_id", 0))
    product = str(payload.get("product", "")).lower().strip()
    init_data = str(payload.get("init_data", "")).strip()
    if not tg_id or product not in {"vpn", "dns", "pro"}:
        raise HTTPException(status_code=400, detail="Invalid tg_id or product")
    _verify_mini_auth(tg_id, init_data)
    if not TON_WALLET:
        raise HTTPException(status_code=400, detail="TON wallet not configured")

    async with async_session() as session:
        user = await _find_or_create_user(session, tg_id)
        rate = await get_ton_rub_rate()
        if not rate or rate <= 0:
            rate = 100.0

        rub_prices = {"vpn": VPN_PRICE_RUB, "dns": DNS_PRICE_RUB, "pro": PRO_PRICE_RUB}
        amount_rub = rub_prices[product]
        amount_ton = round(amount_rub / rate, 2)

        payment_code = _generate_payment_code()
        for _ in range(10):
            exists = await session.execute(select(Payment).where(Payment.payment_code == payment_code))
            if not exists.scalar_one_or_none():
                break
            payment_code = _generate_payment_code()

        payment = Payment(
            user_id=user.id,
            payment_code=payment_code,
            product_type=product,
            amount_ton=amount_ton,
            status="pending",
            expires_at=datetime.now() + timedelta(minutes=30),
        )
        session.add(payment)
        await session.commit()

        return JSONResponse(
            {
                "payment_code": payment.payment_code,
                "amount_ton": amount_ton,
                "amount_rub": amount_rub,
                "expires_at": payment.expires_at.strftime("%d.%m.%Y %H:%M"),
                "ton_link": _ton_link(TON_WALLET, amount_ton, payment.payment_code),
                "bot_check_link": f"https://t.me/{BOT_USERNAME}?start=pay_{payment.payment_code}",
            }
        )


@app.get("/api/mini/faq")
async def mini_faq():
    """Frequently asked questions for mini app support section."""
    return JSONResponse(
        {
            "items": [
                {
                    "q": "Как быстро активируется подписка после оплаты?",
                    "a": "Обычно в течение 1-2 минут после подтверждения платежа в боте.",
                },
                {
                    "q": "Как установить VPN на другом устройстве?",
                    "a": "Откройте mini app на новом устройстве и используйте раздел Настройка. Ключ можно установить по ссылке в 1 тап.",
                },
                {
                    "q": "Как купить TON за рубли (P2P)?",
                    "a": "Нажмите кнопку P2P в витрине. Бот проведет по шагам: сумма, адрес кошелька, перевод и подтверждение.",
                },
                {
                    "q": "Куда писать, если не работает DNS/VPN?",
                    "a": f"Свяжитесь с поддержкой: https://t.me/{SUPPORT_USERNAME}",
                },
            ]
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

