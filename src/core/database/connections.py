"""
Gestionnaire de connexions aux bases de données - Version corrigée
"""
import os
import asyncpg
from typing import Optional
import structlog
from contextlib import asynccontextmanager

logger = structlog.get_logger()

class DatabaseManager:
    def __init__(self):
        self._datawarehouse_pool: Optional[asyncpg.Pool] = None
        self._reclamations_pool: Optional[asyncpg.Pool] = None
        self._conversations_pool: Optional[asyncpg.Pool] = None
    
    async def init_datawarehouse_pool(self):
        """Initialise le pool de connexions DataWarehouse"""
        if self._datawarehouse_pool is None:
            try:
                self._datawarehouse_pool = await asyncpg.create_pool(
                    host=os.getenv("DATAWAREHOUSE_HOST"),
                    port=int(os.getenv("DATAWAREHOUSE_PORT", "5432")),
                    database=os.getenv("DATAWAREHOUSE_DB"),
                    user=os.getenv("DATAWAREHOUSE_USER"),
                    password=os.getenv("DATAWAREHOUSE_PASSWORD"),
                    min_size=2,
                    max_size=10
                )
                logger.info("DataWarehouse pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize DataWarehouse pool: {e}")
                raise
    
    async def init_reclamations_pool(self):
        """Initialise le pool de connexions Réclamations"""
        if self._reclamations_pool is None:
            try:
                self._reclamations_pool = await asyncpg.create_pool(
                    host=os.getenv("RECLAMATIONS_HOST"),
                    port=int(os.getenv("RECLAMATIONS_PORT", "5432")),
                    database=os.getenv("RECLAMATIONS_DB"),
                    user=os.getenv("RECLAMATIONS_USER"),
                    password=os.getenv("RECLAMATIONS_PASSWORD"),
                    min_size=2,
                    max_size=10
                )
                logger.info("Reclamations pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Reclamations pool: {e}")
                raise
    
    async def init_conversations_pool(self):
        """Initialise le pool de connexions Conversations"""
        if self._conversations_pool is None:
            try:
                self._conversations_pool = await asyncpg.create_pool(
                    host=os.getenv("CONVERSATIONS_HOST", "localhost"),
                    port=int(os.getenv("CONVERSATIONS_PORT", "5432")),
                    database=os.getenv("CONVERSATIONS_DB", "coris_conversations"),
                    user=os.getenv("CONVERSATIONS_USER", "coris_user"),
                    password=os.getenv("CONVERSATIONS_PASSWORD", "coris_password"),
                    min_size=2,
                    max_size=10
                )
                logger.info("Conversations pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Conversations pool: {e}")
                raise
    
    @asynccontextmanager
    async def get_datawarehouse_connection(self):
        """Retourne une connexion DataWarehouse avec context manager"""
        if self._datawarehouse_pool is None:
            await self.init_datawarehouse_pool()
        
        async with self._datawarehouse_pool.acquire() as conn:
            yield conn
    
    @asynccontextmanager
    async def get_reclamations_connection(self):
        """Retourne une connexion Réclamations avec context manager"""
        if self._reclamations_pool is None:
            await self.init_reclamations_pool()
        
        async with self._reclamations_pool.acquire() as conn:
            yield conn
    
    @asynccontextmanager
    async def get_conversations_connection(self):
        """Retourne une connexion Conversations avec context manager"""
        if self._conversations_pool is None:
            await self.init_conversations_pool()
        
        async with self._conversations_pool.acquire() as conn:
            yield conn
    
    async def close_all_pools(self):
        """Ferme tous les pools de connexions"""
        if self._datawarehouse_pool:
            await self._datawarehouse_pool.close()
            self._datawarehouse_pool = None
            logger.info("DataWarehouse pool closed")
        
        if self._reclamations_pool:
            await self._reclamations_pool.close()
            self._reclamations_pool = None
            logger.info("Reclamations pool closed")
        
        if self._conversations_pool:
            await self._conversations_pool.close()
            self._conversations_pool = None
            logger.info("Conversations pool closed")
    
    async def health_check(self):
        """Vérifie la santé des connexions"""
        health_status = {
            "datawarehouse": False,
            "reclamations": False,
            "conversations": False
        }
        
        # Test connexion conversations (obligatoire)
        try:
            async with self.get_conversations_connection() as conn:
                await conn.fetchval("SELECT 1")
                health_status["conversations"] = True
        except Exception as e:
            logger.error(f"Conversations DB health check failed: {e}")
        
        # Test autres connexions (optionnel)
        try:
            async with self.get_datawarehouse_connection() as conn:
                await conn.fetchval("SELECT 1")
                health_status["datawarehouse"] = True
        except Exception:
            logger.warning("DataWarehouse not available")
        
        try:
            async with self.get_reclamations_connection() as conn:
                await conn.fetchval("SELECT 1")
                health_status["reclamations"] = True
        except Exception:
            logger.warning("Reclamations DB not available")
        
        return health_status

# Instance globale
db_manager = DatabaseManager()