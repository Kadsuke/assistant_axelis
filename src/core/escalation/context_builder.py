"""
Constructeur de contexte pour les escalades
"""
import asyncio
from typing import Dict, List
from datetime import datetime
from core.conversation.manager import ConversationManager
from core.database.connections import db_manager
import structlog

logger = structlog.get_logger()

class ContextBuilder:
    def __init__(self):
        self.conversation_manager = ConversationManager()
    
    async def prepare_escalation_context(self, conversation_id: str) -> Dict:
        """
        Prépare le contexte complet pour une escalade
        
        Args:
            conversation_id: ID de la conversation
            
        Returns:
            Contexte structuré pour l'agent humain
        """
        try:
            # Récupérer le contexte de conversation
            conversation_context = await self.conversation_manager.get_conversation_context(conversation_id)
            
            if not conversation_context:
                logger.warning("No context found for conversation", conversation_id=conversation_id)
                return {}
            
            # Construire le contexte enrichi
            context = {
                "conversation_summary": await self._build_conversation_summary(conversation_context),
                "user_profile": await self._build_user_profile(conversation_context),
                "technical_context": await self._build_technical_context(conversation_context),
                "business_context": await self._build_business_context(conversation_context),
                "recommended_actions": await self._suggest_actions(conversation_context),
                "escalation_metadata": self._build_escalation_metadata(conversation_context)
            }
            
            logger.info("Escalation context prepared", 
                       conversation_id=conversation_id,
                       context_sections=list(context.keys()))
            
            return context
            
        except Exception as e:
            logger.error("Error preparing escalation context", 
                        error=str(e), 
                        conversation_id=conversation_id)
            return {}
    
    async def _build_conversation_summary(self, context: Dict) -> Dict:
        """Construit un résumé de la conversation"""
        
        messages = context.get('messages', [])
        conversation_info = context.get('conversation_info', {})
        
        # Analyser les messages
        user_messages = [msg for msg in messages if msg['role'] == 'user']
        assistant_messages = [msg for msg in messages if msg['role'] == 'assistant']
        
        # Identifier le problème principal
        first_user_message = user_messages[0]['content'] if user_messages else ""
        last_user_message = user_messages[-1]['content'] if user_messages else ""
        
        # Calculer la durée
        if messages:
            start_time = messages[0]['timestamp']
            end_time = messages[-1]['timestamp']
            duration = self._calculate_duration(start_time, end_time)
        else:
            duration = "Inconnue"
        
        return {
            "main_issue": first_user_message[:200] + "..." if len(first_user_message) > 200 else first_user_message,
            "latest_message": last_user_message[:200] + "..." if len(last_user_message) > 200 else last_user_message,
            "total_messages": len(messages),
            "user_messages_count": len(user_messages),
            "assistant_messages_count": len(assistant_messages),
            "conversation_duration": duration,
            "channel": conversation_info.get('channel', 'unknown'),
            "created_at": conversation_info.get('created_at'),
            "last_activity": conversation_info.get('updated_at')
        }
    
    async def _build_user_profile(self, context: Dict) -> Dict:
        """Construit le profil utilisateur"""
        
        conversation_info = context.get('conversation_info', {})
        user_id = conversation_info.get('user_id')
        filiale_id = conversation_info.get('filiale_id')
        
        # Récupérer l'historique utilisateur (derniers 30 jours)
        async with db_manager.get_conversations_connection() as conn:
            user_history_query = """
            SELECT 
                COUNT(*) as total_conversations,
                COUNT(CASE WHEN status = 'escalated' THEN 1 END) as escalated_conversations,
                MAX(created_at) as last_conversation,
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_conversation_duration
            FROM conversations 
            WHERE user_id = $1 
            AND created_at > NOW() - INTERVAL '30 days'
            """
            
            user_stats = await conn.fetchrow(user_history_query, user_id)
        
        return {
            "user_id": user_id,
            "filiale_id": filiale_id,
            "pack_level": conversation_info.get('pack_level', 'unknown'),
            "historical_stats": dict(user_stats) if user_stats else {},
            "is_frequent_user": user_stats['total_conversations'] > 5 if user_stats else False,
            "escalation_history": user_stats['escalated_conversations'] if user_stats else 0
        }
    
    async def _build_technical_context(self, context: Dict) -> Dict:
        """Construit le contexte technique"""
        
        agent_actions = context.get('agent_actions', [])
        failed_attempts = context.get('failed_attempts', 0)
        
        # Analyser les actions des agents
        agents_used = list(set([action['agent_name'] for action in agent_actions]))
        failed_actions = [action for action in agent_actions if not action.get('success', True)]
        
        # Calculer les temps de réponse
        response_times = [action.get('execution_time_ms', 0) for action in agent_actions]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "agents_involved": agents_used,
            "total_agent_actions": len(agent_actions),
            "failed_actions": len(failed_actions),
            "failed_attempts": failed_attempts,
            "average_response_time_ms": avg_response_time,
            "error_details": [action.get('error_message') for action in failed_actions if action.get('error_message')],
            "last_successful_action": next((action for action in reversed(agent_actions) if action.get('success')), None)
        }
    
    async def _build_business_context(self, context: Dict) -> Dict:
        """Construit le contexte métier"""
        
        conversation_info = context.get('conversation_info', {})
        filiale_id = conversation_info.get('filiale_id')
        
        # Récupérer les informations de la filiale
        from core.packs.manager import MultiAppPackManager
        pack_manager = MultiAppPackManager()
        
        filiale_capabilities = pack_manager.get_filiale_capabilities(filiale_id, "coris_money")
        
        return {
            "filiale_id": filiale_id,
            "pack_subscribed": filiale_capabilities.get('pack_name', 'unknown'),
            "available_features": filiale_capabilities.get('features', []),
            "automation_level": filiale_capabilities.get('automation_level', 0),
            "available_channels": filiale_capabilities.get('channels', []),
            "business_hours": self._get_business_hours(filiale_id),
            "escalation_sla": self._get_escalation_sla(filiale_capabilities.get('pack_name'))
        }
    
    async def _suggest_actions(self, context: Dict) -> List[str]:
        """Suggère des actions pour l'agent humain"""
        
        actions = []
        
        conversation_summary = await self._build_conversation_summary(context)
        technical_context = await self._build_technical_context(context)
        
        # Suggestions basées sur l'historique
        if technical_context['failed_attempts'] > 2:
            actions.append("Vérifier les autorisations du compte utilisateur")
            actions.append("Valider les paramètres de la transaction")
        
        # Suggestions basées sur les erreurs
        if technical_context['error_details']:
            actions.append("Examiner les erreurs techniques détectées")
            actions.append("Vérifier la connectivité aux systèmes backend")
        
        # Suggestions basées sur le type de conversation
        main_issue = conversation_summary.get('main_issue', '').lower()
        if 'transfert' in main_issue:
            actions.append("Vérifier le statut du transfert dans le système")
            actions.append("Confirmer les détails du bénéficiaire")
        elif 'solde' in main_issue:
            actions.append("Consulter le solde en temps réel")
            actions.append("Vérifier les dernières transactions")
        elif 'réclamation' in main_issue or 'problème' in main_issue:
            actions.append("Créer un ticket de réclamation formelle")
            actions.append("Escalader vers le service qualité si nécessaire")
        
        # Actions génériques
        actions.extend([
            "Confirmer l'identité du client",
            "Expliquer les prochaines étapes clairement",
            "Fournir un délai de résolution réaliste"
        ])
        
        return actions[:10]  # Limiter à 10 suggestions
    
    def _build_escalation_metadata(self, context: Dict) -> Dict:
        """Construit les métadonnées d'escalade"""
        
        return {
            "escalation_timestamp": datetime.now().isoformat(),
            "context_version": "1.0",
            "priority_score": self._calculate_priority_score(context),
            "complexity_score": self._calculate_complexity_score(context),
            "estimated_resolution_time": self._estimate_resolution_time(context)
        }
    
    def _calculate_duration(self, start_time, end_time) -> str:
        """Calcule la durée entre deux timestamps"""
        try:
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            duration = end_time - start_time
            minutes = int(duration.total_seconds() / 60)
            
            if minutes < 1:
                return "< 1 minute"
            elif minutes < 60:
                return f"{minutes} minutes"
            else:
                hours = minutes // 60
                remaining_minutes = minutes % 60
                return f"{hours}h {remaining_minutes}m"
                
        except Exception:
            return "Durée inconnue"
    
    def _get_business_hours(self, filiale_id: str) -> str:
        """Récupère les heures d'ouverture de la filiale"""
        # À adapter selon vos données
        business_hours_map = {
            'coris_ci': '8h00 - 17h00 (GMT)',
            'coris_bf': '8h00 - 17h00 (GMT)',
            'coris_ml': '8h00 - 17h00 (GMT)',
            'coris_sn': '8h00 - 17h00 (GMT)'
        }
        return business_hours_map.get(filiale_id, '8h00 - 17h00 (GMT)')
    
    def _get_escalation_sla(self, pack_name: str) -> str:
        """Récupère le SLA d'escalade selon le pack"""
        sla_map = {
            'coris_basic': '2 heures',
            'coris_advanced': '1 heure',
            'coris_premium': '30 minutes'
        }
        return sla_map.get(pack_name, '2 heures')
    
    def _calculate_priority_score(self, context: Dict) -> int:
        """Calcule un score de priorité (1-10)"""
        score = 5  # Score de base
        
        # Ajuster selon les échecs
        failed_attempts = context.get('failed_attempts', 0)
        score += min(failed_attempts, 3)
        
        # Ajuster selon la durée
        conversation_duration = len(context.get('messages', []))
        if conversation_duration > 10:
            score += 2
        
        return min(score, 10)
    
    def _calculate_complexity_score(self, context: Dict) -> int:
        """Calcule un score de complexité (1-10)"""
        score = 5  # Score de base
        
        # Ajuster selon le nombre d'agents impliqués
        agents_used = len(set([action['agent_name'] for action in context.get('agent_actions', [])]))
        score += min(agents_used - 1, 3)
        
        # Ajuster selon les erreurs techniques
        failed_actions = len([action for action in context.get('agent_actions', []) if not action.get('success', True)])
        score += min(failed_actions, 2)
        
        return min(score, 10)
    
    def _estimate_resolution_time(self, context: Dict) -> str:
        """Estime le temps de résolution"""
        complexity = self._calculate_complexity_score(context)
        priority = self._calculate_priority_score(context)
        
        if priority >= 8 or complexity >= 8:
            return "30-60 minutes"
        elif priority >= 6 or complexity >= 6:
            return "1-2 heures"
        else:
            return "15-30 minutes"