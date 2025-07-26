"""
MCP Tools pour accéder au DataWarehouse existant
"""
import asyncio
from typing import Dict, List, Optional
from core.database.connections import db_manager
from core.packs.manager import MultiAppPackManager
import structlog

logger = structlog.get_logger()
pack_manager = MultiAppPackManager()

async def query_transaction_history(user_id: str, filiale_id: str, limit: int = 10) -> List[Dict]:
    """
    Récupère l'historique des transactions depuis le DataWarehouse
    Nécessite pack_basic ou supérieur
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_account_info"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Basic ou supérieur")
    
    async with db_manager.get_datawarehouse_connection() as conn:
        # ADAPTEZ cette requête selon votre schéma DataWarehouse
        query = """
        SELECT 
            transaction_id,
            amount,
            transaction_type,
            destination,
            created_at,
            status
        FROM transactions 
        WHERE user_id = $1 
        ORDER BY created_at DESC 
        LIMIT $2
        """
        
        rows = await conn.fetch(query, user_id, limit)
        
        return [dict(row) for row in rows]

async def get_account_balance(user_id: str, filiale_id: str) -> Dict:
    """
    Récupère le solde du compte
    Nécessite pack_basic ou supérieur  
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_account_info"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Basic ou supérieur")
    
    async with db_manager.get_datawarehouse_connection() as conn:
        # ADAPTEZ selon votre schéma
        query = """
        SELECT 
            account_balance,
            currency,
            last_updated
        FROM accounts 
        WHERE user_id = $1
        """
        
        row = await conn.fetchrow(query, user_id)
        
        if row:
            return dict(row)
        else:
            return {"error": "Account not found"}

async def check_transfer_eligibility(user_id: str, amount: float, filiale_id: str) -> Dict:
    """
    Vérifie si un transfert est possible
    Nécessite pack_advanced pour les vérifications avancées
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_account_operations"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Advanced ou supérieur")
    
    # Logique de vérification selon vos règles métier
    balance_info = await get_account_balance(user_id, filiale_id)
    
    if "error" in balance_info:
        return {"eligible": False, "reason": "Account not found"}
    
    current_balance = float(balance_info.get("account_balance", 0))
    
    return {
        "eligible": current_balance >= amount,
        "current_balance": current_balance,
        "requested_amount": amount,
        "remaining_balance": current_balance - amount if current_balance >= amount else None
    }