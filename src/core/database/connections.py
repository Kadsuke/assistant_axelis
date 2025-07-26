"""
Gestionnaire de connexions aux bases de données
"""
import os
import asyncpg
from typing import Optional
import structlog

logger = structlog.get_logger()

class DatabaseManager:
    def __init__(self):
        self._datawarehouse_pool: Optional[asyncpg.Pool] = None
        self._reclamations_pool: Optional[asyncpg.Pool] = None
        self._conversations_pool: Optional[asyncpg.Pool] = None
    
    async def init_datawarehouse_pool(self):
        """Initialise le pool de connexions DataWarehouse"""
        self._datawarehouse_pool = await asyncpg.create_pool(
            host=os.getenv("DATAWAREHOUSE_HOST"),
            port=os.getenv("DATAWAREHOUSE_PORT"),
            database=os.getenv("DATAWAREHOUSE_DB"),
            user=os.getenv("DATAWAREHOUSE_USER"),
            password=os.getenv("DATAWAREHOUSE_PASSWORD"),
            min_size=2,
            max_size=10
        )
        logger.info("DataWarehouse pool initialized")
    
    async def init_reclamations_pool(self):
        """Initialise le pool de connexions Réclamations"""
        self._reclamations_pool = await asyncpg.create_pool(
            host=os.getenv("RECLAMATIONS_HOST"),
            port=os.getenv("RECLAMATIONS_PORT"),
            database=os.getenv("RECLAMATIONS_DB"),
            user=os.getenv("RECLAMATIONS_USER"),
            password=os.getenv("RECLAMATIONS_PASSWORD"),
            min_size=2,
            max_size=10
        )
        logger.info("Reclamations pool initialized")
    
    async def init_conversations_pool(self):
        """Initialise le pool de connexions Conversations"""
        self._conversations_pool = await asyncpg.create_pool(
            host=os.getenv("CONVERSATIONS_HOST"),
            port=os.getenv("CONVERSATIONS_PORT"),
            database=os.getenv("CONVERSATIONS_DB"),
            user=os.getenv("CONVERSATIONS_USER"),
            password=os.getenv("CONVERSATIONS_PASSWORD"),
            min_size=2,
            max_size=10
        )
        logger.info("Conversations pool initialized")
    
    async def get_datawarehouse_connection(self):
        """Retourne une connexion DataWarehouse"""
        if not self._datawarehouse_pool:
            await self.init_datawarehouse_pool()
        return self._datawarehouse_pool.acquire()
    
    async def get_reclamations_connection(self):
        """Retourne une connexion Réclamations"""
        if not self._reclamations_pool:
            await self.init_reclamations_pool()
        return self._reclamations_pool.acquire()
    
    async def get_conversations_connection(self):
        """Retourne une connexion Conversations"""
        if not self._conversations_pool:
            await self.init_conversations_pool()
        return self._conversations_pool.acquire()

# Instance globale
db_manager = DatabaseManager()