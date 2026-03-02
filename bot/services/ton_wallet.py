"""
TON Wallet service for sending transactions
Uses pytoniq library for blockchain interaction
"""
import logging
import os
import re
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WalletInfo:
    """Wallet information"""
    address: str
    balance: float  # in TON


@dataclass
class TransactionResult:
    """Transaction result"""
    success: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None


class TONWallet:
    """TON Wallet for sending transactions"""
    
    def __init__(
        self,
        mnemonics: str,
        wallet_version: str = "v4r2",
        network_global_id: int = -239,
    ):
        """
        Initialize wallet from seed phrase
        
        Args:
            mnemonics: 24 words separated by spaces
            wallet_version: wallet version (v4r2 or w5/v5)
            network_global_id: TON network global id (-239 for mainnet)
        """
        self._mnemonics = mnemonics.split()
        self._wallet_version = (wallet_version or "v4r2").lower()
        self._network_global_id = network_global_id
        self._wallet = None
        self._address = None
        self._initialized = False
    
    async def init(self):
        """Initialize wallet (lazy loading)"""
        if self._initialized:
            return
        
        try:
            from pytoniq import WalletV4R2, WalletV5R1, LiteBalancer
            
            # Connect to mainnet
            provider = LiteBalancer.from_mainnet_config(trust_level=2)
            await provider.start_up()
            
            # Create wallet from mnemonics (version-aware)
            if self._wallet_version in {"w5", "v5", "v5r1", "walletv5"}:
                self._wallet = await WalletV5R1.from_mnemonic(
                    provider,
                    self._mnemonics,
                    network_global_id=self._network_global_id,
                )
            else:
                self._wallet = await WalletV4R2.from_mnemonic(provider, self._mnemonics)

            self._address = self._wallet.address.to_str()
            self._initialized = True
            
            logger.info(f"TON wallet initialized ({self._wallet_version}): {self._address[:20]}...")
            
        except ImportError:
            logger.error("pytoniq not installed! Run: pip install pytoniq")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize wallet: {e}")
            raise
    
    @property
    def address(self) -> Optional[str]:
        """Get wallet address"""
        return self._address
    
    async def get_balance(self) -> float:
        """Get wallet balance in TON"""
        if not self._initialized:
            await self.init()
        
        try:
            balance_nano = await self._wallet.get_balance()
            return balance_nano / 1_000_000_000
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0
    
    async def send_ton(self, to_address: str, amount: float, memo: str = "") -> TransactionResult:
        """
        Send TON to address
        
        Args:
            to_address: Recipient address
            amount: Amount in TON
            memo: Optional transaction comment
            
        Returns:
            TransactionResult with success status and tx_hash
        """
        if not self._initialized:
            await self.init()
        
        try:
            # Convert to nanoTON
            amount_nano = int(amount * 1_000_000_000)
            
            # Send transaction
            tx_hash = await self._wallet.transfer(
                destination=to_address,
                amount=amount_nano,
                body=memo if memo else None
            )
            
            # Convert hash to hex string
            if isinstance(tx_hash, bytes):
                tx_hash = tx_hash.hex()
            
            logger.info(f"Sent {amount} TON to {to_address[:20]}... tx: {tx_hash}")
            
            return TransactionResult(success=True, tx_hash=tx_hash)
            
        except Exception as e:
            logger.error(f"Failed to send TON: {e}")
            return TransactionResult(success=False, error=str(e))
    
    async def close(self):
        """Close wallet connection"""
        if self._wallet and hasattr(self._wallet.provider, 'close_all'):
            await self._wallet.provider.close_all()


def validate_ton_address(address: str) -> Tuple[bool, str]:
    """
    Validate TON address format
    
    Args:
        address: Address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not address:
        return False, "Адрес не может быть пустым"
    
    # Remove any whitespace
    address = address.strip()
    
    # Check length (48 chars for base64 format)
    if len(address) != 48:
        return False, f"Неверная длина адреса ({len(address)} символов, ожидается 48)"
    
    # Check prefix (UQ for user-friendly bounceable, EQ for non-bounceable)
    if not address.startswith(('UQ', 'EQ', 'kQ', 'Ef', '0:')):
        return False, "Неверный префикс адреса"
    
    # Check for valid base64 characters
    if address.startswith(('UQ', 'EQ', 'kQ', 'Ef')):
        base64_pattern = re.compile(r'^[A-Za-z0-9_-]+$')
        if not base64_pattern.match(address):
            return False, "Адрес содержит недопустимые символы"
    
    return True, ""


# Global wallet instance (initialized on first use)
_wallet_instance: Optional[TONWallet] = None


async def get_wallet(mnemonics: str) -> TONWallet:
    """Get or create wallet instance"""
    global _wallet_instance
    
    if _wallet_instance is None:
        wallet_version = os.getenv("HOT_WALLET_VERSION", "v4r2")
        network_global_id = int(os.getenv("TON_NETWORK_GLOBAL_ID", "-239"))
        _wallet_instance = TONWallet(
            mnemonics,
            wallet_version=wallet_version,
            network_global_id=network_global_id,
        )
        await _wallet_instance.init()
    
    return _wallet_instance
