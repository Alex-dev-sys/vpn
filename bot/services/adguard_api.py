"""
AdGuard Home API Client

Документация API: https://github.com/AdguardTeam/AdGuardHome/tree/master/openapi
"""
import aiohttp
import logging
from typing import Optional
from base64 import b64encode

logger = logging.getLogger(__name__)


class AdGuardAPI:
    """Клиент для AdGuard Home API"""
    
    def __init__(self, api_url: str, username: str, password: str):
        """
        Args:
            api_url: URL API в формате http://IP:3000 (или :80)
            username: Логин администратора
            password: Пароль администратора
        """
        self.api_url = api_url.rstrip("/")
        self._auth_header = self._create_auth_header(username, password)
    
    def _create_auth_header(self, username: str, password: str) -> str:
        """Создать Basic Auth заголовок"""
        credentials = f"{username}:{password}"
        encoded = b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    async def _request(self, method: str, endpoint: str, json_data: dict = None) -> Optional[dict]:
        """Выполнить запрос к API"""
        url = f"{self.api_url}{endpoint}"
        headers = {"Authorization": self._auth_header}
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=json_data, headers=headers) as response:
                if response.status >= 400:
                    text = await response.text()
                    logger.error(f"AdGuard API error: {response.status} - {text}")
                    raise Exception(f"AdGuard API error: {response.status}")
                
                # Некоторые endpoints возвращают пустой ответ
                if response.content_length == 0:
                    return None
                    
                try:
                    return await response.json()
                except:
                    return None
    
    async def get_access_list(self) -> dict:
        """
        Получить текущий список доступа
        
        GET /control/access/list
        
        Returns:
            {
                "allowed_clients": ["1.2.3.4", "5.6.7.8"],
                "disallowed_clients": [],
                "blocked_hosts": []
            }
        """
        return await self._request("GET", "/control/access/list")
    
    async def set_access_list(
        self, 
        allowed_clients: list[str] = None,
        disallowed_clients: list[str] = None,
        blocked_hosts: list[str] = None
    ) -> bool:
        """
        Установить список доступа
        
        POST /control/access/set
        """
        # Получаем текущие настройки
        current = await self.get_access_list()
        
        data = {
            "allowed_clients": allowed_clients if allowed_clients is not None else current.get("allowed_clients", []),
            "disallowed_clients": disallowed_clients if disallowed_clients is not None else current.get("disallowed_clients", []),
            "blocked_hosts": blocked_hosts if blocked_hosts is not None else current.get("blocked_hosts", [])
        }
        
        try:
            await self._request("POST", "/control/access/set", data)
            return True
        except Exception as e:
            logger.error(f"Failed to set access list: {e}")
            return False
    
    async def add_allowed_client(self, ip: str) -> bool:
        """
        Добавить IP в список разрешенных клиентов
        
        Args:
            ip: IP адрес клиента
        """
        current = await self.get_access_list()
        allowed = current.get("allowed_clients", [])
        
        if ip in allowed:
            logger.info(f"IP {ip} already in allowed list")
            return True
        
        allowed.append(ip)
        success = await self.set_access_list(allowed_clients=allowed)
        
        if success:
            logger.info(f"Added IP {ip} to allowed clients")
        
        return success
    
    async def remove_allowed_client(self, ip: str) -> bool:
        """
        Удалить IP из списка разрешенных клиентов
        
        Args:
            ip: IP адрес клиента
        """
        current = await self.get_access_list()
        allowed = current.get("allowed_clients", [])
        
        if ip not in allowed:
            logger.info(f"IP {ip} not in allowed list")
            return True
        
        allowed.remove(ip)
        success = await self.set_access_list(allowed_clients=allowed)
        
        if success:
            logger.info(f"Removed IP {ip} from allowed clients")
        
        return success
    
    async def get_status(self) -> dict:
        """
        Получить статус сервера
        
        GET /control/status
        """
        return await self._request("GET", "/control/status")
