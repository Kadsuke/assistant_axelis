"""
Outils spécifiques pour les APIs Coris Money
"""
import asyncio
import httpx
from typing import Dict, List, Optional
from core.packs.manager import MultiAppPackManager
import structlog

logger = structlog.get_logger()
pack_manager = MultiAppPackManager()

class CorisMoneyAPIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
    
    async def get_user_profile(self, user_id: str) -> Dict:
        """Récupère le profil utilisateur via API Coris Money"""
        try:
            response = await self.client.get(f"{self.base_url}/users/{user_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to get user profile", error=str(e))
            return {"error": "Profile not found"}
    
    async def initiate_transfer(self, user_id: str, transfer_data: Dict) -> Dict:
        """Initie un transfert via API Coris Money"""
        try:
            response = await self.client.post(
                f"{self.base_url}/transfers", 
                json={
                    "user_id": user_id,
                    **transfer_data
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to initiate transfer", error=str(e))
            return {"error": "Transfer failed"}
    
    async def cancel_transfer(self, transfer_id: str, user_id: str) -> Dict:
        """Annule un transfert via API Coris Money"""
        try:
            response = await self.client.post(
                f"{self.base_url}/transfers/{transfer_id}/cancel",
                json={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to cancel transfer", error=str(e))
            return {"error": "Cancellation failed"}

# Fonctions MCP Tools pour CrewAI
async def coris_faq_search(query: str, filiale_id: str, category: str = None) -> List[Dict]:
    """
    Recherche dans la FAQ Coris Money spécifique à la filiale
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_faq_system"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Basic ou supérieur")
    
    # Import local pour éviter les imports circulaires
    from core.knowledge_base.chroma_manager import MultiTenantChromaManager
    
    chroma_manager = MultiTenantChromaManager()
    
    # Recherche dans ChromaDB
    results = await chroma_manager.query_documents(
        application="coris_money",
        filiale_id=filiale_id,
        query=query,
        n_results=5
    )
    
    # Filtrer par catégorie si spécifiée
    if category and results.get('documents'):
        filtered_results = []
        for i, metadata in enumerate(results['metadatas'][0]):
            if metadata.get('category') == category:
                filtered_results.append({
                    'content': results['documents'][0][i],
                    'metadata': metadata,
                    'relevance': 1 - results['distances'][0][i]
                })
        return filtered_results
    
    # Retourner tous les résultats
    if results.get('documents'):
        return [{
            'content': doc,
            'metadata': metadata,
            'relevance': 1 - distance
        } for doc, metadata, distance in zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )]
    
    return []

async def get_transfer_fees(amount: float, destination: str, filiale_id: str) -> Dict:
    """
    Calcule les frais de transfert Coris Money
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_account_info"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Basic ou supérieur")
    
    # Logique de calcul des frais selon vos règles métier
    base_fee = 500  # FCFA
    percentage_fee = amount * 0.02  # 2%
    
    total_fee = base_fee + percentage_fee
    
    # Frais maximum selon destination
    max_fees = {
        "domestic": 2000,    # National
        "regional": 5000,    # UEMOA
        "international": 10000  # International
    }
    
    destination_type = "domestic"  # Logique à adapter selon votre classification
    final_fee = min(total_fee, max_fees.get(destination_type, 10000))
    
    return {
        "amount": amount,
        "destination": destination,
        "base_fee": base_fee,
        "percentage_fee": percentage_fee,
        "total_fee": final_fee,
        "currency": "XOF"
    }

async def check_transfer_limits(user_id: str, amount: float, filiale_id: str) -> Dict:
    """
    Vérifie les limites de transfert pour un utilisateur
    """
    if not pack_manager.can_access_feature(filiale_id, "coris_money", "coris_account_operations"):
        raise PermissionError("Cette fonctionnalité nécessite Pack Advanced ou supérieur")
    
    # Récupérer les limites depuis votre système
    # Ceci est un exemple - adaptez selon votre logique métier
    user_limits = {
        "daily_limit": 1000000,    # 1M FCFA par jour
        "monthly_limit": 5000000,  # 5M FCFA par mois
        "single_transfer_limit": 500000  # 500K FCFA par transfert
    }
    
    # Vérifier les limites
    checks = {
        "single_transfer_ok": amount <= user_limits["single_transfer_limit"],
        "daily_limit_ok": True,  # À calculer avec l'historique du jour
        "monthly_limit_ok": True,  # À calculer avec l'historique du mois
        "user_limits": user_limits,
        "requested_amount": amount
    }
    
    checks["all_checks_passed"] = all([
        checks["single_transfer_ok"],
        checks["daily_limit_ok"], 
        checks["monthly_limit_ok"]
    ])
    
    return checks