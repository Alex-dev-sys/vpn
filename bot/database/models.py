from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PaymentStatus(enum.Enum):
    """Статусы платежа"""
    PENDING = "pending"      # Ожидает оплаты
    COMPLETED = "completed"  # Оплачен
    EXPIRED = "expired"      # Истёк
    CANCELLED = "cancelled"  # Отменён


class ProductType(enum.Enum):
    """Типы продуктов"""
    VPN = "vpn"
    DNS = "dns"
    PRO = "pro"


class User(Base):
    """Таблица пользователей"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    referrer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_banned: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    vpn_keys: Mapped[list["VPNKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    dns_accesses: Mapped[list["DNSAccess"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    p2p_orders: Mapped[list["P2POrder"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.telegram_id} ({self.username})>"


class Server(Base):
    """Таблица серверов (Outline + AdGuard)"""
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="Server 1")
    outline_api_url: Mapped[str] = mapped_column(Text)  # https://IP:PORT/Secret
    adguard_api_url: Mapped[str] = mapped_column(Text)  # http://IP:3000
    adguard_user: Mapped[str] = mapped_column(String(100))
    adguard_pass: Mapped[str] = mapped_column(String(100))
    users_count: Mapped[int] = mapped_column(Integer, default=0)
    max_users: Mapped[int] = mapped_column(Integer, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    vpn_keys: Mapped[list["VPNKey"]] = relationship(back_populates="server")
    dns_accesses: Mapped[list["DNSAccess"]] = relationship(back_populates="server")

    def __repr__(self):
        return f"<Server {self.id} ({self.name})>"


class VPNKey(Base):
    """Таблица ключей VPN (подписки Outline)"""
    __tablename__ = "vpn_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    outline_key_id: Mapped[str] = mapped_column(String(50))  # ID ключа в Outline
    access_url: Mapped[str] = mapped_column(Text)  # ss://...
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_status: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="vpn_keys")
    server: Mapped["Server"] = relationship(back_populates="vpn_keys")

    def __repr__(self):
        return f"<VPNKey {self.id} user={self.user_id} active={self.is_active}>"


class DNSAccess(Base):
    """Таблица доступа к DNS (подписки AdGuard)"""
    __tablename__ = "dns_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"))
    current_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 max length
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_status: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="dns_accesses")
    server: Mapped["Server"] = relationship(back_populates="dns_accesses")

    def __repr__(self):
        return f"<DNSAccess {self.id} user={self.user_id} ip={self.current_ip}>"


class Payment(Base):
    """Таблица платежей для трекинга"""
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # Уникальный код платежа (для комментария в TON)
    payment_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    
    product_type: Mapped[str] = mapped_column(String(50))  # vpn, dns, pro, extend_vpn:123
    amount_ton: Mapped[float] = mapped_column(Float)  # Сумма в TON
    
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, completed, expired
    
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # Время жизни платежа (15 мин)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Promo code used
    promo_code_id: Mapped[Optional[int]] = mapped_column(ForeignKey("promo_codes.id"), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="payments")

    def __repr__(self):
        return f"<Payment {self.payment_code} user={self.user_id} status={self.status}>"


class P2POrderStatus(enum.Enum):
    """Статусы P2P заказа"""
    PENDING = "pending"                      # Ожидает оплаты
    WAITING_CONFIRMATION = "waiting_confirmation"  # Пользователь нажал "Я оплатил"
    COMPLETED = "completed"                  # Выполнен, TON отправлен
    CANCELED = "canceled"                    # Отменён


class P2POrder(Base):
    """Таблица P2P заказов (покупка TON за рубли)"""
    __tablename__ = "p2p_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # Purchase details
    amount_ton: Mapped[float] = mapped_column(Float)
    amount_rub: Mapped[int] = mapped_column(Integer)
    exchange_rate: Mapped[float] = mapped_column(Float)  # Rate at order creation
    
    # Client wallet
    wallet_address: Mapped[str] = mapped_column(String(100))
    
    # Status
    status: Mapped[str] = mapped_column(String(30), default=P2POrderStatus.PENDING.value)
    
    # Transaction hash after sending
    tx_hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Cancellation reason
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Completion time
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="p2p_orders")

    def __repr__(self):
        return f"<P2POrder #{self.id} {self.amount_ton} TON status={self.status}>"


class Settings(Base):
    """Таблица настроек бота"""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text)

    def __repr__(self):
        return f"<Setting {self.key}={self.value}>"


# Settings keys
SETTING_CARD_NUMBER = "card_number"
SETTING_BANK_NAME = "bank_name"
SETTING_MARGIN_PERCENT = "margin_percent"
SETTING_SBP_PHONE = "sbp_phone"


class AuditLog(Base):
    """Таблица логов действий администратора"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(100))  # ban_user, confirm_p2p, etc.
    target_type: Mapped[str] = mapped_column(String(50))  # user, p2p_order, vpn_key
    target_id: Mapped[int] = mapped_column(Integer)
    admin_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<AuditLog {self.action} {self.target_type}:{self.target_id}>"


class PromoCode(Base):
    """Таблица промокодов"""
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    discount_percent: Mapped[int] = mapped_column(Integer)  # 1-100
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    current_uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<PromoCode {self.code} -{self.discount_percent}%>"


