"""
Rate service for fetching TON/RUB exchange rate
"""
import logging
import aiohttp
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# CoinGecko API (free, no key needed)
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Binance API (fallback)
BINANCE_API = "https://api.binance.com/api/v3"


class RateService:
    """Service for fetching and caching TON/RUB rate"""
    
    _instance = None
    _rate: Optional[float] = None
    _last_update: Optional[datetime] = None
    _cache_duration = timedelta(seconds=60)
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def rate(self) -> Optional[float]:
        """Current cached rate"""
        return self._rate
    
    @property
    def is_stale(self) -> bool:
        """Check if rate is stale and needs update"""
        if self._last_update is None:
            return True
        return datetime.now() - self._last_update > self._cache_duration
    
    async def update_rate(self) -> Optional[float]:
        """Fetch fresh rate from API"""
        rate = await self._fetch_from_coingecko()
        if rate is None:
            rate = await self._fetch_from_binance()
        
        if rate is not None:
            self._rate = rate
            self._last_update = datetime.now()
            logger.info(f"TON/RUB rate updated: {rate:.2f}")
        
        return rate
    
    async def get_rate(self) -> Optional[float]:
        """Get current rate, updating if stale"""
        if self.is_stale:
            await self.update_rate()
        return self._rate
    
    async def _fetch_from_coingecko(self) -> Optional[float]:
        """Fetch rate from CoinGecko"""
        try:
            url = f"{COINGECKO_API}/simple/price"
            params = {
                "ids": "the-open-network",
                "vs_currencies": "rub"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        logger.warning(f"CoinGecko returned {resp.status}")
                        return None
                    
                    data = await resp.json()
                    rate = data.get("the-open-network", {}).get("rub")
                    
                    if rate:
                        return float(rate)
                    return None
                    
        except Exception as e:
            logger.warning(f"CoinGecko fetch failed: {e}")
            return None
    
    async def _fetch_from_binance(self) -> Optional[float]:
        """Fetch rate from Binance (TON/USDT * USDT/RUB)"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get TON/USDT
                async with session.get(
                    f"{BINANCE_API}/ticker/price",
                    params={"symbol": "TONUSDT"},
                    timeout=10
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    ton_usdt = float(data.get("price", 0))
                
                # Get USDT/RUB
                async with session.get(
                    f"{BINANCE_API}/ticker/price",
                    params={"symbol": "USDTRUB"},
                    timeout=10
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    usdt_rub = float(data.get("price", 0))
                
                if ton_usdt and usdt_rub:
                    return ton_usdt * usdt_rub
                return None
                
        except Exception as e:
            logger.warning(f"Binance fetch failed: {e}")
            return None


# Singleton instance
rate_service = RateService()


async def get_ton_rub_rate() -> Optional[float]:
    """Get current TON/RUB rate"""
    return await rate_service.get_rate()


def get_cached_rate() -> Optional[float]:
    """Get cached rate without updating"""
    return rate_service.rate
