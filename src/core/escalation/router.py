"""
Routeur d'escalade vers agents humains
"""
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from core.database.connections import db_manager
import structlog

logger = structlog.get_logger()

class EscalationRouter:
    def __init__(self):
        self.routing_algorithms = {
            'expertise_based': self._route_by_expertise,
            'load_balanced': self._route_by_load,
            'language_based': self._route_by_language,
            'hybrid': self._route_hybrid
        }
    
    async def find_best_agent(self, escalation_context: Dict) -> Optional[str]:
        """
        Trouve le meilleur agent humain pour l'escalade
        
        Args:
            escalation_context: Contexte de l'escalade
            
        Returns:
            ID de l'agent sélectionné ou None
        """
        try:
            # Utiliser l'algorithme hybride par défaut
            agent_id = await self._route_hybrid(escalation_context)
            
            if agent_id:
                # Mettre à jour la charge de l'agent
                await self._update_agent_load(agent_id, increment=1)
                logger.info("Agent assigned for escalation", 
                           agent_id=agent_id, 
                           reason=escalation_context.get('reason'))
                return agent_id
            else:
                logger.warning("No available agent found for escalation")
                return None
                
        except Exception as e:
            logger.error("Error in agent routing", error=str(e))
            return None
    
    async def _route_hybrid(self, context: Dict) -> Optional[str]:
        """Algorithme de routage hybride (expertise + charge + langue)"""
        
        # Extraire les critères
        required_expertise = self._extract_required_expertise(context)
        user_language = context.get('user_language', 'fr')
        priority = context.get('priority', 'medium')
        
        async with db_manager.get_conversations_connection() as conn:
            # Requête pour trouver les agents appropriés
            query = """
            SELECT 
                id, name, specialties, languages, current_load, max_concurrent,
                CASE 
                    WHEN current_load = 0 THEN 1.0
                    ELSE (max_concurrent - current_load)::float / max_concurrent
                END as availability_score
            FROM human_agents 
            WHERE status = 'available' 
            AND current_load < max_concurrent
            AND ($1 = ANY(languages) OR languages @> '["fr"]'::jsonb)
            ORDER BY 
                CASE WHEN $2 = ANY(array(SELECT jsonb_array_elements_text(specialties))) THEN 1 ELSE 0 END DESC,
                availability_score DESC,
                last_activity DESC
            LIMIT 5
            """
            
            rows = await conn.fetch(query, user_language, required_expertise)
            
            if not rows:
                return None
            
            # Sélectionner le meilleur agent selon les critères
            for row in rows:
                agent_specialties = row['specialties'] if row['specialties'] else []
                
                # Vérifier l'expertise
                if required_expertise in agent_specialties or not required_expertise:
                    # Vérifier la langue
                    agent_languages = row['languages'] if row['languages'] else ['fr']
                    if user_language in agent_languages:
                        return row['id']
            
            # Fallback : prendre le premier agent disponible
            return rows[0]['id'] if rows else None
    
    def _extract_required_expertise(self, context: Dict) -> str:
        """Extrait l'expertise requise du contexte"""
        
        reason = context.get('reason', '').lower()
        user_message = context.get('user_message', '').lower()
        
        # Mapping des mots-clés vers expertises
        expertise_keywords = {
            'reclamations': ['réclamation', 'complaint', 'problème', 'insatisfait', 'erreur'],
            'operations': ['transfert', 'annulation', 'transaction', 'solde', 'compte'],
            'technique': ['bug', 'erreur', 'ne fonctionne pas', 'problème technique', 'app'],
            'commercial': ['tarif', 'prix', 'nouveau service', 'information produit']
        }
        
        for expertise, keywords in expertise_keywords.items():
            if any(keyword in reason or keyword in user_message for keyword in keywords):
                return expertise
        
        return 'general'  # Expertise par défaut
    
    async def _update_agent_load(self, agent_id: str, increment: int = 1):
        """Met à jour la charge de travail d'un agent"""
        
        async with db_manager.get_conversations_connection() as conn:
            query = """
            UPDATE human_agents 
            SET current_load = current_load + $1,
                last_activity = $2
            WHERE id = $3
            """
            
            await conn.execute(query, increment, datetime.now(), agent_id)
    
    async def release_agent(self, agent_id: str):
        """Libère un agent (diminue sa charge)"""
        await self._update_agent_load(agent_id, increment=-1)
        
        # S'assurer que la charge ne devienne pas négative
        async with db_manager.get_conversations_connection() as conn:
            await conn.execute(
                "UPDATE human_agents SET current_load = GREATEST(0, current_load) WHERE id = $1",
                agent_id
            )
        
        logger.info("Agent released", agent_id=agent_id)
    
    async def get_agent_status(self, agent_id: str) -> Dict:
        """Récupère le statut d'un agent"""
        
        async with db_manager.get_conversations_connection() as conn:
            query = """
            SELECT name, status, current_load, max_concurrent, specialties, languages
            FROM human_agents 
            WHERE id = $1
            """
            
            row = await conn.fetchrow(query, agent_id)
            
            if row:
                return dict(row)
            else:
                return {}
    
    async def list_available_agents(self) -> List[Dict]:
        """Liste tous les agents disponibles"""
        
        async with db_manager.get_conversations_connection() as conn:
            query = """
            SELECT id, name, status, current_load, max_concurrent, specialties
            FROM human_agents 
            WHERE status = 'available'
            ORDER BY current_load ASC, name ASC
            """
            
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]