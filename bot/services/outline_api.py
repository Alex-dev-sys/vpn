"""
Outline Server Management API Client

Документация API: https://github.com/Jigsaw-Code/outline-server/blob/master/src/shadowbox/server/api.yml
"""
import aiohttp
import ssl
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OutlineKey:
    """Структура ключа Outline"""
    id: str
    name: str
    access_url: str
    port: int
    method: str
    password: str


class OutlineAPI:
    """Клиент для Outline Server Management API"""
    
    def __init__(self, api_url: str):
        """
        Args:
            api_url: URL API в формате https://IP:PORT/SECRET
        """
        self.api_url = api_url.rstrip("/")
        # Outline использует self-signed сертификаты
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
    
    async def _request(self, method: str, endpoint: str, json_data: dict = None) -> dict:
        """Выполнить запрос к API"""
        url = f"{self.api_url}{endpoint}"
        connector = aiohttp.TCPConnector(ssl=self._ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.request(method, url, json=json_data) as response:
                if response.status >= 400:
                    text = await response.text()
                    logger.error(f"Outline API error: {response.status} - {text}")
                    raise Exception(f"Outline API error: {response.status}")
                
                if response.status == 204:  # No Content
                    return {}
                    
                return await response.json()
    
    async def create_key(self, name: Optional[str] = None) -> OutlineKey:
        """
        Создать новый ключ доступа
        
        POST /access-keys
        """
        data = await self._request("POST", "/access-keys")
        
        key = OutlineKey(
            id=str(data["id"]),
            name=data.get("name", ""),
            access_url=data["accessUrl"],
            port=data.get("port", 0),
            method=data.get("method", ""),
            password=data.get("password", "")
        )
        
        # Устанавливаем имя, если указано
        if name:
            await self.rename_key(key.id, name)
            key.name = name
        
        logger.info(f"Created Outline key: {key.id}")
        return key
    
    async def delete_key(self, key_id: str) -> bool:
        """
        Удалить ключ доступа
        
        DELETE /access-keys/{id}
        """
        try:
            await self._request("DELETE", f"/access-keys/{key_id}")
            logger.info(f"Deleted Outline key: {key_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete key {key_id}: {e}")
            return False
    
    async def rename_key(self, key_id: str, name: str) -> bool:
        """
        Переименовать ключ
        
        PUT /access-keys/{id}/name
        """
        try:
            await self._request("PUT", f"/access-keys/{key_id}/name", {"name": name})
            return True
        except Exception:
            return False
    
    async def list_keys(self) -> list[OutlineKey]:
        """
        Получить список всех ключей
        
        GET /access-keys
        """
        data = await self._request("GET", "/access-keys")
        keys = []
        
        for item in data.get("accessKeys", []):
            keys.append(OutlineKey(
                id=str(item["id"]),
                name=item.get("name", ""),
                access_url=item["accessUrl"],
                port=item.get("port", 0),
                method=item.get("method", ""),
                password=item.get("password", "")
            ))
        
        return keys
    
    async def get_server_info(self) -> dict:
        """
        Получить информацию о сервере
        
        GET /server
        """
        return await self._request("GET", "/server")
