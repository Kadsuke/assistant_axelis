"""
Gestionnaire des conversations et de l'historique
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from core.database.connections import db_manager
from core.packs.manager import pack_manager
import structlog
import json

logger = structlog.get_logger()

class ConversationManager:
    def __init__(self):
        self.active_conversations = {}
        self._conversation_cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def initialize(self):
        """Initialise le gestionnaire de conversations"""
        await self._create_tables_if_not_exist()
        logger.info("ConversationManager initialized")
    
    async def _create_tables_if_not_exist(self):
        """Crée les tables si elles n'existent pas"""
        async with db_manager.get_conversations_connection() as conn:
            # Table des conversations
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR(255) NOT NULL,
                    filiale_id VARCHAR(100) NOT NULL,
                    application_id VARCHAR(100) NOT NULL,
                    pack_level VARCHAR(50) NOT NULL,
                    channel VARCHAR(50) NOT NULL DEFAULT 'mobile',
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    language VARCHAR(10) DEFAULT 'fr',
                    context JSONB DEFAULT '{}',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    closed_at TIMESTAMP WITH TIME ZONE NULL,
                    
                    INDEX idx_conversations_user_filiale (user_id, filiale_id),
                    INDEX idx_conversations_status (status),
                    INDEX idx_conversations_created (created_at)
                )
            """)
            
            # Table des messages
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    agent_used VARCHAR(100),
                    tools_used JSONB DEFAULT '[]',
                    tokens_consumed INTEGER DEFAULT 0,
                    confidence_score DECIMAL(3,2),
                    processing_time DECIMAL(8,3),
                    metadata JSONB DEFAULT '{}',
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    
                    INDEX idx_messages_conversation (conversation_id),
                    INDEX idx_messages_timestamp (timestamp),
                    INDEX idx_messages_role (role)
                )
            """)
            
            # Table des escalades
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS escalations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    escalation_reason VARCHAR(100) NOT NULL,
                    escalation_type VARCHAR(50) NOT NULL DEFAULT 'human_agent',
                    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                    assigned_to VARCHAR(255),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    context JSONB DEFAULT '{}',
                    escalated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    resolved_at TIMESTAMP WITH TIME ZONE NULL,
                    resolution_notes TEXT,
                    
                    INDEX idx_escalations_conversation (conversation_id),
                    INDEX idx_escalations_status (status),
                    INDEX idx_escalations_priority (priority)
                )
            """)
    
    async def get_or_create_conversation(self, user_id: str, filiale_id: str, 
                                        application_id: str, channel: str = "mobile",
                                        language: str = "fr") -> str:
        """Récupère une conversation active ou en crée une nouvelle"""
        
        # Vérifier le pack de la filiale
        pack_level = pack_manager.get_pack_for_filiale(filiale_id, application_id)
        
        async with db_manager.get_conversations_connection() as conn:
            # Chercher une conversation active récente (moins de 30 minutes)
            query = """
            SELECT id, context, metadata FROM conversations 
            WHERE user_id = $1 AND filiale_id = $2 AND application_id = $3 
            AND status = 'active' 
            AND updated_at > NOW() - INTERVAL '30 minutes'
            ORDER BY updated_at DESC 
            LIMIT 1
            """
            
            row = await conn.fetchrow(query, user_id, filiale_id, application_id)
            
            if row:
                conversation_id = str(row['id'])
                logger.info("Retrieved existing conversation", 
                           conversation_id=conversation_id,
                           user_id=user_id,
                           filiale_id=filiale_id)
                return conversation_id
            
            # Créer une nouvelle conversation
            conversation_id = str(uuid.uuid4())
            
            # Contexte initial
            initial_context = {
                "user_preferences": {},
                "session_start": datetime.now().isoformat(),
                "channel": channel,
                "language": language
            }
            
            # Métadonnées
            metadata = {
                "pack_level": pack_level,
                "features_available": list(pack_manager.get_pack_features(pack_level, application_id)),
                "agents_available": pack_manager.get_pack_agents(pack_level, application_id),
                "limits": pack_manager.get_pack_limits(pack_level, application_id)
            }
            
            insert_query = """
            INSERT INTO conversations (
                id, user_id, filiale_id, application_id, 
                pack_level, channel, status, language, context, metadata, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """
            
            now = datetime.now()
            await conn.execute(
                insert_query,
                conversation_id, user_id, filiale_id, application_id,
                pack_level, channel, "active", language, 
                json.dumps(initial_context), json.dumps(metadata), now, now
            )
            
            logger.info("Created new conversation", 
                       conversation_id=conversation_id,
                       user_id=user_id,
                       filiale_id=filiale_id,
                       pack_level=pack_level)
            return conversation_id
    
    async def add_message(self, conversation_id: str, role: str, content: str, 
                         agent_used: str = None, tools_used: List = None, 
                         tokens_consumed: int = None, confidence_score: float = None,
                         processing_time: float = None, metadata: Dict = None) -> str:
        """Ajoute un message à la conversation"""
        
        message_id = str(uuid.uuid4())
        
        async with db_manager.get_conversations_connection() as conn:
            query = """
            INSERT INTO messages (
                id, conversation_id, role, content, agent_used, 
                tools_used, tokens_consumed, confidence_score, 
                processing_time, metadata, timestamp
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """
            
            await conn.execute(
                query,
                message_id, conversation_id, role, content, agent_used,
                json.dumps(tools_used or []), tokens_consumed, confidence_score,
                processing_time, json.dumps(metadata or {}), datetime.now()
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
                   message_id=message_id,
                   role=role, 
                   agent_used=agent_used,
                   tokens_consumed=tokens_consumed)
        
        return message_id
    
    async def get_conversation_history(self, conversation_id: str, 
                                     limit: int = 50, 
                                     include_system: bool = False) -> List[Dict]:
        """Récupère l'historique d'une conversation"""
        
        async with db_manager.get_conversations_connection() as conn:
            where_clause = "WHERE conversation_id = $1"
            params = [conversation_id]
            
            if not include_system:
                where_clause += " AND role != 'system'"
            
            query = f"""
            SELECT 
                id, role, content, agent_used, timestamp,
                tools_used, tokens_consumed, confidence_score,
                processing_time, metadata
            FROM messages 
            {where_clause}
            ORDER BY timestamp ASC 
            LIMIT $2
            """
            
            params.append(limit)
            rows = await conn.fetch(query, *params)
            
            messages = []
            for row in rows:
                message = dict(row)
                # Décoder les JSONB
                message['tools_used'] = json.loads(message['tools_used'] or '[]')
                message['metadata'] = json.loads(message['metadata'] or '{}')
                message['timestamp'] = message['timestamp'].isoformat()
                messages.append(message)
            
            return messages
    
    async def get_conversation_context(self, conversation_id: str) -> Optional[Dict]:
        """Récupère le contexte complet d'une conversation"""
        
        # Vérifier le cache
        cache_key = f"context_{conversation_id}"
        if cache_key in self._conversation_cache:
            cached_data, timestamp = self._conversation_cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self._cache_ttl):
                return cached_data
        
        async with db_manager.get_conversations_connection() as conn:
            # Récupérer les infos de conversation
            conv_query = """
            SELECT * FROM conversations WHERE id = $1
            """
            conv_row = await conn.fetchrow(conv_query, conversation_id)
            
            if not conv_row:
                return None
            
            conversation = dict(conv_row)
            conversation['context'] = json.loads(conversation['context'] or '{}')
            conversation['metadata'] = json.loads(conversation['metadata'] or '{}')
            
            # Récupérer les messages récents
            messages = await self.get_conversation_history(conversation_id, limit=20)
            
            # Récupérer les escalades actives
            escalation_query = """
            SELECT * FROM escalations 
            WHERE conversation_id = $1 AND status IN ('pending', 'in_progress')
            ORDER BY escalated_at DESC
            LIMIT 5
            """
            escalation_rows = await conn.fetch(escalation_query, conversation_id)
            escalations = [dict(row) for row in escalation_rows]
            
            context = {
                "conversation_info": conversation,
                "messages": messages,
                "active_escalations": escalations,
                "statistics": await self._get_conversation_stats(conversation_id, conn)
            }
            
            # Mettre en cache
            self._conversation_cache[cache_key] = (context, datetime.now())
            
            return context
    
    async def _get_conversation_stats(self, conversation_id: str, conn) -> Dict:
        """Calcule les statistiques d'une conversation"""
        
        stats_query = """
        SELECT 
            COUNT(*) as total_messages,
            COUNT(*) FILTER (WHERE role = 'user') as user_messages,
            COUNT(*) FILTER (WHERE role = 'assistant') as assistant_messages,
            AVG(tokens_consumed) FILTER (WHERE tokens_consumed > 0) as avg_tokens,
            SUM(tokens_consumed) FILTER (WHERE tokens_consumed > 0) as total_tokens,
            AVG(confidence_score) FILTER (WHERE confidence_score IS NOT NULL) as avg_confidence,
            AVG(processing_time) FILTER (WHERE processing_time IS NOT NULL) as avg_response_time,
            MIN(timestamp) as first_message,
            MAX(timestamp) as last_message
        FROM messages 
        WHERE conversation_id = $1
        """
        
        stats_row = await conn.fetchrow(stats_query, conversation_id)
        
        return {
            "total_messages": stats_row['total_messages'] or 0,
            "user_messages": stats_row['user_messages'] or 0,
            "assistant_messages": stats_row['assistant_messages'] or 0,
            "avg_tokens_per_message": float(stats_row['avg_tokens'] or 0),
            "total_tokens_consumed": stats_row['total_tokens'] or 0,
            "avg_confidence_score": float(stats_row['avg_confidence'] or 0),
            "avg_response_time": float(stats_row['avg_response_time'] or 0),
            "duration_minutes": self._calculate_duration(stats_row['first_message'], stats_row['last_message'])
        }
    
    def _calculate_duration(self, start_time, end_time) -> float:
        """Calcule la durée d'une conversation en minutes"""
        if not start_time or not end_time:
            return 0.0
        
        duration = end_time - start_time
        return duration.total_seconds() / 60.0
    
    async def create_escalation(self, conversation_id: str, reason: str, 
                               priority: str = "medium", escalation_type: str = "human_agent",
                               assigned_to: str = None, context: Dict = None) -> str:
        """Crée une escalade pour la conversation"""
        
        escalation_id = str(uuid.uuid4())
        
        async with db_manager.get_conversations_connection() as conn:
            # Créer l'escalade
            query = """
            INSERT INTO escalations (
                id, conversation_id, escalation_reason, escalation_type,
                priority, assigned_to, status, context, escalated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """
            
            await conn.execute(
                query,
                escalation_id, conversation_id, reason, escalation_type,
                priority, assigned_to, "pending", json.dumps(context or {}), datetime.now()
            )
            
            # Mettre à jour le statut de la conversation
            update_query = """
            UPDATE conversations 
            SET status = 'escalated', updated_at = $1
            WHERE id = $2
            """
            await conn.execute(update_query, datetime.now(), conversation_id)
        
        logger.info("Escalation created", 
                   escalation_id=escalation_id,
                   conversation_id=conversation_id,
                   reason=reason,
                   priority=priority)
        
        return escalation_id
    
    async def close_conversation(self, conversation_id: str, reason: str = "completed") -> bool:
        """Ferme une conversation"""
        
        async with db_manager.get_conversations_connection() as conn:
            query = """
            UPDATE conversations 
            SET status = 'closed', closed_at = $1, updated_at = $1
            WHERE id = $2 AND status != 'closed'
            """
            
            result = await conn.execute(query, datetime.now(), conversation_id)
            
            # Nettoyer le cache
            cache_key = f"context_{conversation_id}"
            if cache_key in self._conversation_cache:
                del self._conversation_cache[cache_key]
            
            success = result != "UPDATE 0"
            
            if success:
                logger.info("Conversation closed", 
                           conversation_id=conversation_id,
                           reason=reason)
            
            return success
    
    async def update_conversation_context(self, conversation_id: str, 
                                        context_updates: Dict) -> bool:
        """Met à jour le contexte d'une conversation"""
        
        async with db_manager.get_conversations_connection() as conn:
            # Récupérer le contexte actuel
            query = "SELECT context FROM conversations WHERE id = $1"
            row = await conn.fetchrow(query, conversation_id)
            
            if not row:
                return False
            
            current_context = json.loads(row['context'] or '{}')
            current_context.update(context_updates)
            
            # Mettre à jour
            update_query = """
            UPDATE conversations 
            SET context = $1, updated_at = $2
            WHERE id = $3
            """
            
            await conn.execute(update_query, 
                             json.dumps(current_context), 
                             datetime.now(), 
                             conversation_id)
            
            # Invalider le cache
            cache_key = f"context_{conversation_id}"
            if cache_key in self._conversation_cache:
                del self._conversation_cache[cache_key]
            
            return True
    
    async def get_user_conversations(self, user_id: str, filiale_id: str,
                                   application_id: str, limit: int = 10,
                                   status: str = None) -> List[Dict]:
        """Récupère les conversations d'un utilisateur"""
        
        async with db_manager.get_conversations_connection() as conn:
            where_clause = "WHERE user_id = $1 AND filiale_id = $2 AND application_id = $3"
            params = [user_id, filiale_id, application_id]
            
            if status:
                where_clause += " AND status = $4"
                params.append(status)
            
            query = f"""
            SELECT 
                id, status, channel, language, pack_level,
                created_at, updated_at, closed_at,
                (SELECT COUNT(*) FROM messages WHERE conversation_id = conversations.id) as message_count
            FROM conversations 
            {where_clause}
            ORDER BY updated_at DESC 
            LIMIT ${len(params) + 1}
            """
            
            params.append(limit)
            rows = await conn.fetch(query, *params)
            
            conversations = []
            for row in rows:
                conv = dict(row)
                conv['created_at'] = conv['created_at'].isoformat()
                conv['updated_at'] = conv['updated_at'].isoformat()
                if conv['closed_at']:
                    conv['closed_at'] = conv['closed_at'].isoformat()
                conversations.append(conv)
            
            return conversations
    
    async def cleanup_old_conversations(self, days: int = 90) -> int:
        """Nettoie les anciennes conversations fermées"""
        
        async with db_manager.get_conversations_connection() as conn:
            query = """
            DELETE FROM conversations 
            WHERE status = 'closed' 
            AND closed_at < NOW() - INTERVAL '%s days'
            """ % days
            
            result = await conn.execute(query)
            
            # Nettoyer le cache
            self._conversation_cache.clear()
            
            deleted_count = int(result.split()[-1]) if result else 0
            
            logger.info("Cleaned up old conversations", 
                       deleted_count=deleted_count,
                       older_than_days=days)
            
            return deleted_count
    
    async def get_statistics(self, filiale_id: str = None, 
                           application_id: str = None,
                           hours: int = 24) -> Dict:
        """Récupère des statistiques sur les conversations"""
        
        async with db_manager.get_conversations_connection() as conn:
            where_clause = "WHERE created_at > NOW() - INTERVAL '%s hours'" % hours
            params = []
            
            if filiale_id:
                where_clause += " AND filiale_id = $1"
                params.append(filiale_id)
                
            if application_id:
                next_param = len(params) + 1
                where_clause += f" AND application_id = ${next_param}"
                params.append(application_id)
            
            query = f"""
            SELECT 
                COUNT(*) as total_conversations,
                COUNT(*) FILTER (WHERE status = 'active') as active_conversations,
                COUNT(*) FILTER (WHERE status = 'closed') as closed_conversations,
                COUNT(*) FILTER (WHERE status = 'escalated') as escalated_conversations,
                AVG(EXTRACT(EPOCH FROM (COALESCE(closed_at, NOW()) - created_at))/60) as avg_duration_minutes,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT filiale_id) as unique_filiales
            FROM conversations 
            {where_clause}
            """
            
            stats_row = await conn.fetchrow(query, *params)
            
            return {
                "period_hours": hours,
                "total_conversations": stats_row['total_conversations'] or 0,
                "active_conversations": stats_row['active_conversations'] or 0,
                "closed_conversations": stats_row['closed_conversations'] or 0,
                "escalated_conversations": stats_row['escalated_conversations'] or 0,
                "avg_duration_minutes": float(stats_row['avg_duration_minutes'] or 0),
                "unique_users": stats_row['unique_users'] or 0,
                "unique_filiales": stats_row['unique_filiales'] or 0
            }
    
    async def cleanup(self):
        """Nettoyage des ressources"""
        self._conversation_cache.clear()
        logger.info("ConversationManager cleaned up")

# Instance globale
conversation_manager = ConversationManager()