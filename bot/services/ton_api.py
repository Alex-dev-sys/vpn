"""
TON API клиент для проверки платежей

Использует TonCenter API для проверки входящих транзакций.
Проверяет что платёж с нужной суммой и комментарием пришёл на кошелёк.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)

# TonCenter API (бесплатный, лимит 1 req/sec)
TONCENTER_API = "https://toncenter.com/api/v2"

# Альтернатива: TON API (tonapi.io) - более надёжный
TONAPI_URL = "https://tonapi.io/v2"


class TONPaymentChecker:
    """Проверка платежей через TON API"""
    
    def __init__(self, wallet_address: str):
        self.wallet = wallet_address
        # Конвертируем адрес в raw формат если нужно
        self.wallet_raw = wallet_address
    
    async def check_payment(
        self, 
        amount_ton: float, 
        payment_code: str,
        since_minutes: int = 30
    ) -> bool:
        """
        Проверяет есть ли входящая транзакция с нужной суммой и комментарием.
        
        Args:
            amount_ton: Ожидаемая сумма в TON
            payment_code: Код платежа (должен быть в комментарии)
            since_minutes: За какой период искать (в минутах)
            
        Returns:
            True если платёж найден, False если нет
        """
        try:
            # Пробуем TonAPI (более надёжный)
            result = await self._check_via_tonapi(amount_ton, payment_code, since_minutes)
            if result is not None:
                return result
                
            # Fallback на TonCenter
            return await self._check_via_toncenter(amount_ton, payment_code, since_minutes)
            
        except Exception as e:
            logger.error(f"Error checking TON payment: {e}")
            return False
    
    async def _check_via_tonapi(
        self, 
        amount_ton: float, 
        payment_code: str,
        since_minutes: int
    ) -> Optional[bool]:
        """Проверка через tonapi.io"""
        try:
            url = f"{TONAPI_URL}/blockchain/accounts/{self.wallet}/transactions"
            params = {"limit": 50}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        logger.warning(f"TonAPI returned {resp.status}")
                        return None
                    
                    data = await resp.json()
                    transactions = data.get("transactions", [])
                    
                    # Время начала поиска
                    since_time = datetime.now() - timedelta(minutes=since_minutes)
                    since_timestamp = int(since_time.timestamp())
                    
                    # Ожидаемая сумма в нанотонах (с погрешностью 1%)
                    expected_nano = int(amount_ton * 1_000_000_000)
                    tolerance = expected_nano * 0.01  # 1% погрешность
                    
                    for tx in transactions:
                        # Проверяем время
                        tx_time = tx.get("utime", 0)
                        if tx_time < since_timestamp:
                            continue
                        
                        # Проверяем входящие транзакции
                        in_msg = tx.get("in_msg", {})
                        if not in_msg:
                            continue
                        
                        # Проверяем сумму
                        value = int(in_msg.get("value", 0))
                        if abs(value - expected_nano) > tolerance:
                            continue
                        
                        # Проверяем комментарий
                        decoded = in_msg.get("decoded_body", {})
                        comment = decoded.get("text", "") if decoded else ""
                        
                        # Также проверяем raw message
                        if not comment:
                            msg_data = in_msg.get("msg_data", {})
                            if msg_data.get("@type") == "msg.dataText":
                                import base64
                                try:
                                    comment = base64.b64decode(msg_data.get("text", "")).decode("utf-8")
                                except:
                                    pass
                        
                        if payment_code in comment:
                            logger.info(f"Payment found via TonAPI: {payment_code}, {value} nanoTON")
                            return True
                    
                    return False
                    
        except Exception as e:
            logger.warning(f"TonAPI check failed: {e}")
            return None
    
    async def _check_via_toncenter(
        self, 
        amount_ton: float, 
        payment_code: str,
        since_minutes: int
    ) -> bool:
        """Проверка через toncenter.com"""
        try:
            url = f"{TONCENTER_API}/getTransactions"
            params = {
                "address": self.wallet,
                "limit": 50,
                "archival": "false"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        logger.error(f"TonCenter returned {resp.status}")
                        return False
                    
                    data = await resp.json()
                    
                    if not data.get("ok"):
                        logger.error(f"TonCenter error: {data}")
                        return False
                    
                    transactions = data.get("result", [])
                    
                    # Время начала поиска
                    since_time = datetime.now() - timedelta(minutes=since_minutes)
                    since_timestamp = int(since_time.timestamp())
                    
                    # Ожидаемая сумма в нанотонах
                    expected_nano = int(amount_ton * 1_000_000_000)
                    tolerance = expected_nano * 0.01
                    
                    for tx in transactions:
                        # Проверяем время
                        tx_time = tx.get("utime", 0)
                        if tx_time < since_timestamp:
                            continue
                        
                        # Проверяем входящие сообщения
                        in_msg = tx.get("in_msg", {})
                        if not in_msg:
                            continue
                        
                        # Проверяем сумму
                        value = int(in_msg.get("value", 0))
                        if abs(value - expected_nano) > tolerance:
                            continue
                        
                        # Проверяем комментарий
                        message = in_msg.get("message", "")
                        
                        if payment_code in message:
                            logger.info(f"Payment found via TonCenter: {payment_code}, {value} nanoTON")
                            return True
                    
                    return False
                    
        except Exception as e:
            logger.error(f"TonCenter check failed: {e}")
            return False


async def verify_ton_payment(
    wallet: str,
    amount_ton: float,
    payment_code: str,
    since_minutes: int = 30
) -> bool:
    """
    Удобная функция для проверки платежа.
    
    Args:
        wallet: Адрес кошелька получателя
        amount_ton: Сумма в TON
        payment_code: Код платежа (комментарий)
        since_minutes: За какой период искать
        
    Returns:
        True если платёж найден
    """
    checker = TONPaymentChecker(wallet)
    return await checker.check_payment(amount_ton, payment_code, since_minutes)
