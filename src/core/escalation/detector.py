"""
Détecteur d'escalade intelligent
"""
from typing import Dict, Tuple, List
import structlog

logger = structlog.get_logger()

class EscalationDetector:
    def __init__(self):
        self.escalation_rules = self._load_escalation_rules()
    
    def _load_escalation_rules(self) -> Dict:
        """Charge les règles d'escalade"""
        return {
            "failed_attempts_threshold": 3,
            "urgent_keywords": ["urgent", "immédiat", "emergency", "bloqué", "problème grave"],
            "negative_sentiment_threshold": 0.3,
            "complex_query_indicators": ["plusieurs", "complexe", "ne comprends pas", "confusion"],
            "timeout_minutes": 5
        }
    
    def should_escalate(self, context: Dict) -> Tuple[bool, str]:
        """
        Détermine si une escalade est nécessaire
        
        Args:
            context: Contexte de la conversation
            
        Returns:
            Tuple (should_escalate: bool, reasons: str)
        """
        reasons = []
        
        # Vérifier les tentatives échouées
        failed_attempts = context.get('failed_attempts', 0)
        if failed_attempts >= self.escalation_rules["failed_attempts_threshold"]:
            reasons.append(f"multiple_failures({failed_attempts})")
        
        # Vérifier les mots-clés urgents
        user_message = context.get('user_message', '').lower()
        urgent_keywords_found = [kw for kw in self.escalation_rules["urgent_keywords"] 
                               if kw in user_message]
        if urgent_keywords_found:
            reasons.append(f"urgent_keywords({','.join(urgent_keywords_found)})")
        
        # Vérifier le sentiment négatif
        sentiment = context.get('sentiment', 'neutre')
        if sentiment == 'negative' or sentiment == 'urgent':
            reasons.append("negative_sentiment")
        
        # Vérifier la complexité de la requête
        complex_indicators = [ind for ind in self.escalation_rules["complex_query_indicators"]
                            if ind in user_message]
        if complex_indicators:
            reasons.append(f"complex_query({','.join(complex_indicators)})")
        
        # Vérifier la priorité de réclamation
        complaint_priority = context.get('complaint_priority')
        if complaint_priority == 'URGENT':
            reasons.append("urgent_complaint")
        
        # Demande explicite du client
        explicit_requests = ["agent humain", "conseiller", "responsable", "manager", "supervisor"]
        if any(req in user_message for req in explicit_requests):
            reasons.append("explicit_human_request")
        
        # Problème technique détecté
        if context.get('technical_error', False):
            reasons.append("technical_error")
        
        should_escalate = len(reasons) > 0
        reasons_str = " | ".join(reasons) if reasons else "no_escalation_needed"
        
        if should_escalate:
            logger.info("Escalation detected", reasons=reasons_str, context_keys=list(context.keys()))
        
        return should_escalate, reasons_str
    
    def assess_priority(self, escalation_reasons: str) -> str:
        """
        Évalue la priorité de l'escalade
        
        Args:
            escalation_reasons: Raisons de l'escalade
            
        Returns:
            Priorité: 'low', 'medium', 'high', 'urgent'
        """
        if any(term in escalation_reasons for term in ['urgent_complaint', 'urgent_keywords', 'technical_error']):
            return 'urgent'
        elif any(term in escalation_reasons for term in ['multiple_failures', 'negative_sentiment']):
            return 'high'
        elif 'explicit_human_request' in escalation_reasons:
            return 'medium'
        else:
            return 'low'