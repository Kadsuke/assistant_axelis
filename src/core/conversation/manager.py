"""
Gestionnaire des conversations et de l'historique
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from core.database.connections import db_manager
import structlog

logger = structlog.get_logger()

class ConversationManager:
    def __init__(self):
        self.active_conversations = {}
    
    async def initialize(self):
        """Initialise le gestionnaire de conversations"""
        logger.info("ConversationManager initialized")
    
    async def get_or_create_conversation(self, user_id: str, filiale_id: str, 
                                        application_id: str, channel: str) -> str:
        """Récupère une conversation active ou en crée une nouvelle"""
        
        async with db_manager.get_conversations_connection() as conn:
            # Chercher une conversation active récente (moins de 30 minutes)
            query = """
            SELECT id FROM conversations 
            WHERE user_id = $1 AND filiale_id = $2 AND application_id = $3 
            AND status = 'active' 
            AND created_at > NOW() - INTERVAL '30 minutes'
            ORDER BY created_at DESC 
            LIMIT 1
            """
            
            row = await conn.fetchrow(query, user_id, filiale_id, application_id)
            
            if row:
                conversation_id = str(row['id'])
                logger.info("Retrieved existing conversation", conversation_id=conversation_id)
                return conversation_id
            
            # Créer une nouvelle conversation
            conversation_id = str(uuid.uuid4())
            insert_query = """
            INSERT INTO conversations (
                id, user_id, filiale_id, application_id, 
                pack_level, channel, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            
            await conn.execute(
                insert_query,
                conversation_id, user_id, filiale_id, application_id,
                "unknown", channel, "active", datetime.now()
            )
            
            logger.info("Created new conversation", conversation_id=conversation_id)
            return conversation_id
    
    async def add_message(self, conversation_id: str, role: str, content: str, 
                         agent_used: str = None, tools_used: List = None, 
                         tokens_consumed: int = None) -> str:
        """Ajoute un message à la conversation"""
        
        message_id = str(uuid.uuid4())
        
        async with db_manager.get_conversations_connection() as conn:
            query = """
            INSERT INTO messages (
                id, conversation_id, role, content, agent_used, 
                tools_used, tokens_consumed, timestamp
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            
            await conn.execute(
                query,
                message_id, conversation_id, role, content, agent_used,
                tools_used, tokens_consumed, datetime.now()
            )
            
            # Mettre à jour le timestamp de la conversation
            update_query = """
            UPDATE conversations 
            SET updated_at = $1 
            WHERE id = $2
            """
            await conn.execute(update_query, datetime.now(), conversation_id)
        
        logger.info("Message added", 
                   conversation_id=conversation_id, 
                   role=role, 
                   agent_used=agent_used)
        
        return message_id
    
    async def get_conversation_history(self, conversation_id: str, 
                                     limit: int = 50) -> List[Dict]:
        """Récupère l'historique d'une conversation"""
        
        async with db_manager.get_conversations_connection() as conn:
            query = """
            SELECT 
                role, content, agent_used, timestamp,
                tools_used, tokens_consumed
            FROM messages 
            WHERE conversation_id = $1 
            ORDER BY timestamp ASC 
            LIMIT $2
            """
            
            rows = await conn.fetch(query, conversation_id, limit)
            
            return [dict(row) for row in rows]
    
    async def create_escalation(self, conversation_id: str, reason: str, 
                               priority: str, assigned_to: str = None) -> str:
        """Crée une escalade pour la conversation"""
        
        escalation_id = str(uuid.uuid4())
        
        async with db_manager.get_conversations_connection() as conn:
            # Créer l'escalade
            query = """
            INSERT INTO escalations (
                id, conversation_id, escalation_reason, escalation_type,
                priority, assigned_to, status, escalated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            
            await conn.execute(
                query,
                escalation_id, conversation_id, reason, "human_agent",
                priority, assigned_to, "pending", datetime.now()
            )
            
            # Mettre à jour le statut de la conversation
            update_query = """
            UPDATE conversations 
            SET status = 'escalated' 
            WHERE id = $1
            """
            await conn.execute(update_query, conversation_id)
        
        logger.info("Escalation created", 
                   escalation_id=escalation_id,
                   conversation_id=conversation_id,
                   assigned_to=assigned_to)
        
        return escalation_id
    
    async def get_conversation_context(self, conversation_id: str) -> Dict:
        """Récupère le contexte complet d'une conversation pour escalade"""
        
        async with db_manager.get_conversations_connection() as conn:
            # Récupérer les infos de la conversation
            conv_query = """
            SELECT 
                user_id, filiale_id, application_id, pack_level,
                channel, created_at, status
            FROM conversations 
            WHERE id = $1
            """
            
            conv_row = await conn.fetchrow(conv_query, conversation_id)
            
            if not conv_row:
                return {}
            
            # Récupérer l'historique des messages
            messages = await self.get_conversation_history(conversation_id)
            
            # Récupérer les actions des agents
            actions_query = """
            SELECT 
                agent_name, action_type, action_data, success,
                execution_time_ms, timestamp
            FROM agent_actions 
            WHERE conversation_id = $1 
            ORDER BY timestamp ASC
            """
            
            actions_rows = await conn.fetch(actions_query, conversation_id)
            
            return {
                "conversation_info": dict(conv_row),
                "messages": messages,
                "agent_actions": [dict(row) for row in actions_rows],
                "total_messages": len(messages),
                "conversation_duration": "calculated_duration",  # À calculer
                "failed_attempts": len([a for a in actions_rows if not a['success']])
            }
    
    async def cleanup(self):
        """Nettoyage des ressources"""
        logger.info("ConversationManager cleanup completed")