"""
Collecteur de métriques pour le monitoring
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from core.database.connections import db_manager
import structlog

logger = structlog.get_logger()

# Métriques Prometheus
conversation_counter = Counter(
    'coris_conversations_total',
    'Nombre total de conversations',
    ['filiale_id', 'application', 'channel']
)

response_time_histogram = Histogram(
    'coris_response_time_seconds',
    'Temps de réponse des agents',
    ['agent_name', 'filiale_id'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

escalation_counter = Counter(
    'coris_escalations_total',
    'Nombre d\'escalades vers agents humains',
    ['filiale_id', 'reason', 'priority']
)

active_conversations_gauge = Gauge(
    'coris_active_conversations',
    'Nombre de conversations actives',
    ['filiale_id']
)

tokens_consumed_counter = Counter(
    'coris_openai_tokens_total',
    'Tokens OpenAI consommés',
    ['model', 'type']  # type: input/output
)

error_counter = Counter(
    'coris_errors_total',
    'Erreurs système',
    ['error_type', 'component']
)

class MetricsCollector:
    def __init__(self):
        self.start_time = time.time()
    
    async def initialize(self):
        """Initialise le collecteur de métriques"""
        logger.info("MetricsCollector initialized")
    
    async def record_conversation_metrics(self, filiale_id: str, agent_used: str, 
                                        escalation_needed: bool, channel: str = "mobile"):
        """Enregistre les métriques d'une conversation"""
        
        # Incrémenter le compteur de conversations
        conversation_counter.labels(
            filiale_id=filiale_id,
            application="coris_money",
            channel=channel
        ).inc()
        
        # Enregistrer l'escalade si nécessaire
        if escalation_needed:
            escalation_counter.labels(
                filiale_id=filiale_id,
                reason="automatic_detection",
                priority="medium"
            ).inc()
    
    async def record_response_time(self, agent_name: str, filiale_id: str, 
                                 response_time: float):
        """Enregistre le temps de réponse d'un agent"""
        response_time_histogram.labels(
            agent_name=agent_name,
            filiale_id=filiale_id
        ).observe(response_time)
    
    async def record_token_usage(self, model: str, input_tokens: int, 
                               output_tokens: int):
        """Enregistre l'utilisation des tokens OpenAI"""
        tokens_consumed_counter.labels(
            model=model,
            type="input"
        ).inc(input_tokens)
        
        tokens_consumed_counter.labels(
            model=model,
            type="output"
        ).inc(output_tokens)
    
    async def record_error(self, error_type: str, component: str):
        """Enregistre une erreur système"""
        error_counter.labels(
            error_type=error_type,
            component=component
        ).inc()
    
    async def update_active_conversations(self):
        """Met à jour le nombre de conversations actives"""
        try:
            async with db_manager.get_conversations_connection() as conn:
                query = """
                SELECT filiale_id, COUNT(*) as active_count
                FROM conversations 
                WHERE status = 'active' 
                AND updated_at > NOW() - INTERVAL '30 minutes'
                GROUP BY filiale_id
                """
                
                rows = await conn.fetch(query)
                
                # Reset et mise à jour des gauges
                active_conversations_gauge.clear()
                for row in rows:
                    active_conversations_gauge.labels(
                        filiale_id=row['filiale_id']
                    ).set(row['active_count'])
        
        except Exception as e:
            logger.error("Failed to update active conversations metrics", error=str(e))
    
    async def get_system_metrics(self) -> Dict:
        """Récupère les métriques système pour l'API"""
        
        # Métriques de base
        uptime = time.time() - self.start_time
        
        # Métriques des conversations (dernières 24h)
        async with db_manager.get_conversations_connection() as conn:
            # Conversations par filiale
            conv_query = """
            SELECT 
                filiale_id,
                COUNT(*) as total_conversations,
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_duration
            FROM conversations 
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY filiale_id
            """
            
            conv_rows = await conn.fetch(conv_query)
            
            # Escalades par type
            esc_query = """
            SELECT 
                escalation_reason,
                COUNT(*) as escalation_count
            FROM escalations 
            WHERE escalated_at > NOW() - INTERVAL '24 hours'
            GROUP BY escalation_reason
            """
            
            esc_rows = await conn.fetch(esc_query)
            
            # Métriques de performance
            perf_query = """
            SELECT 
                AVG(tokens_consumed) as avg_tokens,
                COUNT(*) as total_messages,
                COUNT(DISTINCT conversation_id) as unique_conversations
            FROM messages 
            WHERE timestamp > NOW() - INTERVAL '24 hours'
            """
            
            perf_row = await conn.fetchrow(perf_query)
        
        return {
            "system": {
                "uptime_seconds": uptime,
                "status": "healthy",
                "version": "1.0.0"
            },
            "conversations": {
                "by_filiale": [dict(row) for row in conv_rows],
                "total_24h": sum(row['total_conversations'] for row in conv_rows),
                "avg_duration_seconds": sum(row['avg_duration'] or 0 for row in conv_rows) / max(len(conv_rows), 1)
            },
            "escalations": {
                "by_reason": [dict(row) for row in esc_rows],
                "total_24h": sum(row['escalation_count'] for row in esc_rows)
            },
            "performance": {
                "avg_tokens_per_message": float(perf_row['avg_tokens'] or 0),
                "total_messages_24h": perf_row['total_messages'],
                "unique_conversations_24h": perf_row['unique_conversations']
            },
            "prometheus_metrics": generate_latest().decode('utf-8')
        }
    
    async def cleanup(self):
        """Nettoyage des ressources"""
        logger.info("MetricsCollector cleanup completed")