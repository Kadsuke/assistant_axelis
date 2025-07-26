"""
MCP Tools pour la base de réclamations existante
"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from core.database.connections import db_manager
from core.packs.manager import MultiAppPackManager
import structlog

logger = structlog.get_logger()
pack_manager = MultiAppPackManager()

async def create_complaint(user_id: str, filiale_id: str, complaint_type: str, 
                          description: str, priority: str = "medium") -> Dict:
    """
    Crée une nouvelle réclamation
    Nécessite pack_basic ou supérieur
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_complaint_creation"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Basic ou supérieur")
    
    async with db_manager.get_reclamations_connection() as conn:
        # ADAPTEZ selon votre schéma de réclamations
        query = """
        INSERT INTO complaints (
            user_id, filiale_id, complaint_type, description, 
            priority, status, created_at
        ) 
        VALUES ($1, $2, $3, $4, $5, 'open', $6)
        RETURNING complaint_id, created_at
        """
        
        row = await conn.fetchrow(
            query, user_id, filiale_id, complaint_type, 
            description, priority, datetime.now()
        )
        
        complaint_id = row['complaint_id']
        
        logger.info(f"Complaint created", 
                   complaint_id=complaint_id, 
                   user_id=user_id, 
                   filiale_id=filiale_id)
        
        return {
            "complaint_id": complaint_id,
            "status": "created",
            "created_at": row['created_at'].isoformat(),
            "estimated_resolution": "72 heures"
        }

async def get_complaint_status(complaint_id: str, filiale_id: str) -> Dict:
    """
    Récupère le statut d'une réclamation
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_complaint_creation"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Basic ou supérieur")
    
    async with db_manager.get_reclamations_connection() as conn:
        # ADAPTEZ selon votre schéma
        query = """
        SELECT 
            complaint_id,
            complaint_type,
            description,
            status,
            priority,
            created_at,
            updated_at,
            resolution_notes
        FROM complaints 
        WHERE complaint_id = $1
        """
        
        row = await conn.fetchrow(query, complaint_id)
        
        if row:
            return dict(row)
        else:
            return {"error": "Complaint not found"}

async def list_user_complaints(user_id: str, filiale_id: str, limit: int = 10) -> List[Dict]:
    """
    Liste les réclamations d'un utilisateur
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_complaint_creation"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Basic ou supérieur")
    
    async with db_manager.get_reclamations_connection() as conn:
        query = """
        SELECT 
            complaint_id,
            complaint_type,
            status,
            priority,
            created_at,
            LEFT(description, 100) as description_preview
        FROM complaints 
        WHERE user_id = $1 AND filiale_id = $2
        ORDER BY created_at DESC 
        LIMIT $3
        """
        
        rows = await conn.fetch(query, user_id, filiale_id, limit)
        
        return [dict(row) for row in rows]