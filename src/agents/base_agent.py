"""
Classe de base pour tous les agents Coris
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from crewai import Agent
import structlog

logger = structlog.get_logger()

class BaseCorisAgent(ABC):
    """Classe de base pour tous les agents Coris"""
    
    def __init__(self, filiale_id: str, pack_level: str):
        self.filiale_id = filiale_id
        self.pack_level = pack_level
        self.context = {}
        self.tools = []
        
    @abstractmethod
    def get_role(self) -> str:
        """Retourne le rôle de l'agent"""
        pass
    
    @abstractmethod
    def get_goal(self) -> str:
        """Retourne l'objectif de l'agent"""
        pass
    
    @abstractmethod
    def get_backstory(self) -> str:
        """Retourne l'histoire de l'agent"""
        pass
    
    def get_required_tools(self) -> List[str]:
        """Retourne la liste des outils requis pour cet agent"""
        return []
    
    def can_handle_request(self, request_context: Dict) -> bool:
        """Détermine si cet agent peut traiter la requête"""
        return True
    
    def validate_pack_access(self, required_features: List[str]) -> bool:
        """Valide l'accès selon le pack de la filiale"""
        from core.packs.manager import MultiAppPackManager
        
        pack_manager = MultiAppPackManager()
        
        for feature in required_features:
            if not pack_manager.can_access_feature(
                self.filiale_id, "coris_money", feature
            ):
                logger.warning(f"Feature {feature} not available for pack {self.pack_level}")
                return False
        
        return True
    
    def create_crewai_agent(self, tools: List[Any]) -> Agent:
        """Crée l'agent CrewAI correspondant"""
        return Agent(
            role=self.get_role(),
            goal=self.get_goal(),
            backstory=self.get_backstory(),
            tools=tools,
            memory=True,
            verbose=False
        )
    
    def log_action(self, action: str, details: Dict = None):
        """Log une action de l'agent"""
        logger.info(f"Agent action: {action}",
                   agent_type=self.__class__.__name__,
                   filiale_id=self.filiale_id,
                   details=details or {})

class CorisCustomerServiceAgent(BaseCorisAgent):
    """Agent de service client Coris"""
    
    def get_role(self) -> str:
        return "Agent de Service Client Coris Money"
    
    def get_goal(self) -> str:
        return "Accueillir et orienter les clients avec professionnalisme"
    
    def get_backstory(self) -> str:
        return f"""Vous êtes un agent de service client expérimenté de Coris Money 
        pour la filiale {self.filiale_id}. Vous connaissez parfaitement les 
        produits et services locaux, et vous savez orienter les clients vers 
        les bonnes ressources."""
    
    def get_required_tools(self) -> List[str]:
        return ["intent_classifier", "language_detector", "coris_faq_search"]

class CorisBankingAgent(BaseCorisAgent):
    """Agent bancaire spécialisé Coris Money"""
    
    def get_role(self) -> str:
        return "Assistant Bancaire Coris Money"
    
    def get_goal(self) -> str:
        return "Aider les clients avec leurs opérations bancaires quotidiennes"
    
    def get_backstory(self) -> str:
        return f"""Spécialiste des services bancaires Coris Money pour {self.filiale_id}, 
        vous maîtrisez tous les aspects des transferts, consultations de compte 
        et opérations courantes."""
    
    def get_required_tools(self) -> List[str]:
        tools = ["coris_faq_search", "get_account_balance", "query_transaction_history"]
        
        # Ajouter des outils selon le pack
        if self.pack_level in ["coris_advanced", "coris_premium"]:
            tools.extend(["check_transfer_limits", "get_transfer_fees"])
        
        return tools
    
    def can_handle_request(self, request_context: Dict) -> bool:
        """Vérifie si peut traiter la requête selon le pack"""
        message = request_context.get('message', '').lower()
        
        # Opérations de base (pack basic)
        basic_operations = ['solde', 'consultation', 'historique']
        if any(op in message for op in basic_operations):
            return True
        
        # Opérations avancées (pack advanced+)
        advanced_operations = ['transfert', 'annulation', 'limite']
        if any(op in message for op in advanced_operations):
            return self.pack_level in ["coris_advanced", "coris_premium"]
        
        return True

class CorisComplaintAgent(BaseCorisAgent):
    """Agent de gestion des réclamations"""
    
    def get_role(self) -> str:
        return "Gestionnaire de Réclamations Coris Money"
    
    def get_goal(self) -> str:
        return "Traiter efficacement les réclamations clients"
    
    def get_backstory(self) -> str:
        return f"""Expert en résolution de problèmes pour Coris Money {self.filiale_id}, 
        vous gérez les réclamations avec empathie et efficacité, en appliquant 
        les procédures appropriées."""
    
    def get_required_tools(self) -> List[str]:
        return ["create_complaint", "get_complaint_status", "sentiment_analyzer"]