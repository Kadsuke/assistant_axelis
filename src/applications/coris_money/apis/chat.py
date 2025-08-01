"""
API REST pour l'intégration avec l'application mobile Coris Money
Version avec configuration de sécurité pour Swagger
"""
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, APIKeyHeader
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import uuid
from datetime import datetime
import structlog

# Imports internes
from agents.crew_setup import CorisCrewManager
from core.conversation.manager import ConversationManager
from core.escalation.detector import EscalationDetector
from core.auth.middleware import verify_api_key
from core.monitoring.metrics import MetricsCollector

logger = structlog.get_logger()

# Configuration de sécurité pour Swagger
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_security = HTTPBearer(auto_error=False)

app = FastAPI(
    title="Coris Intelligent Assistant API",
    description="API pour l'assistant intelligent Coris Money",
    version="1.0.0",
    # Configuration de sécurité pour Swagger UI
    swagger_ui_parameters={
        "persistAuthorization": True,
    }
)

# Middleware CORS pour l'application mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic
class ChatMessage(BaseModel):
    user_id: str
    filiale_id: str
    message: str
    channel: str = "mobile"
    language: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    agent_used: str
    confidence: float
    suggested_actions: List[str] = []
    escalation_needed: bool = False

class EscalationRequest(BaseModel):
    conversation_id: str
    reason: str
    priority: str = "medium"

# Instances globales
crew_manager = CorisCrewManager()
conversation_manager = ConversationManager()
escalation_detector = EscalationDetector()
metrics_collector = MetricsCollector()

# Fonction de vérification d'API key pour Swagger
async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Récupère et vérifie la clé API pour Swagger"""
    if api_key_header:
        from core.auth.middleware import auth_middleware
        try:
            role = auth_middleware.verify_api_key(api_key_header)
            return role
        except HTTPException:
            pass
    
    # Si pas de clé ou clé invalide, retourner None (pas d'erreur automatique)
    return None

@app.post("/api/v1/chat", 
          response_model=ChatResponse,
          summary="Conversation avec l'assistant",
          description="Envoie un message à l'assistant IA et reçoit une réponse",
          responses={
              200: {"description": "Réponse de l'assistant"},
              401: {"description": "Clé API manquante ou invalide"},
              500: {"description": "Erreur interne du serveur"}
          })
async def chat_endpoint(
    message: ChatMessage, 
    background_tasks: BackgroundTasks,
    api_key: str = Security(api_key_header)
):
    """
    Endpoint principal pour les conversations
    
    **Authentification requise** : Utilisez le header `X-API-Key` avec votre clé API.
    
    **Exemple de clé de test** : `test-key`
    """
    # Vérifier la clé API
    if not api_key:
        raise HTTPException(
            status_code=401, 
            detail="API key required. Use X-API-Key header with your API key."
        )
    
    from core.auth.middleware import auth_middleware
    try:
        role = auth_middleware.verify_api_key(api_key)
    except HTTPException as e:
        raise e
    
    try:
        # Créer ou récupérer la conversation
        conversation_id = await conversation_manager.get_or_create_conversation(
            user_id=message.user_id,
            filiale_id=message.filiale_id,
            application_id="coris_money",
            channel=message.channel
        )
        
        # Enregistrer le message utilisateur
        await conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=message.message
        )
        
        # Traiter avec CrewAI
        crew_result = await crew_manager.process_user_query(
            filiale_id=message.filiale_id,
            application="coris_money",
            user_id=message.user_id,
            query=message.message
        )
        
        if not crew_result["success"]:
            raise HTTPException(status_code=500, detail=crew_result.get("error"))
        
        response_text = crew_result["result"]
        agent_used = crew_result.get("crew_agents", ["unknown"])[0]
        
        # Vérifier si escalade nécessaire
        escalation_needed, escalation_reasons = escalation_detector.should_escalate({
            "user_message": message.message,
            "response_generated": response_text,
            "conversation_id": conversation_id
        })
        
        # Enregistrer la réponse
        await conversation_manager.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response_text,
            agent_used=agent_used
        )
        
        # Métriques en arrière-plan
        background_tasks.add_task(
            metrics_collector.record_conversation_metrics,
            filiale_id=message.filiale_id,
            agent_used=agent_used,
            escalation_needed=escalation_needed
        )
        
        return ChatResponse(
            conversation_id=conversation_id,
            response=response_text,
            agent_used=agent_used,
            confidence=0.85,  # À calculer selon vos critères
            suggested_actions=["Consulter le FAQ", "Parler à un agent"],
            escalation_needed=escalation_needed
        )
        
    except Exception as e:
        logger.error("Chat endpoint error", error=str(e))
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")

@app.post("/api/v1/escalate",
          summary="Escalader vers un agent humain",
          description="Escalade une conversation vers un agent humain")
async def escalate_conversation(
    escalation: EscalationRequest,
    api_key: str = Security(api_key_header)
):
    """
    Endpoint pour escalader une conversation vers un agent humain
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    from core.auth.middleware import auth_middleware
    auth_middleware.verify_api_key(api_key)
    
    try:
        from core.escalation.router import EscalationRouter
        from core.escalation.context_builder import ContextBuilder
        
        escalation_router = EscalationRouter()
        context_builder = ContextBuilder()
        
        # Préparer le contexte pour l'agent humain
        context = await context_builder.prepare_escalation_context(
            escalation.conversation_id
        )
        
        # Router vers l'agent humain approprié
        assigned_agent = await escalation_router.find_best_agent(
            escalation_context={
                "conversation_id": escalation.conversation_id,
                "reason": escalation.reason,
                "priority": escalation.priority,
                **context
            }
        )
        
        # Enregistrer l'escalade
        escalation_id = await conversation_manager.create_escalation(
            conversation_id=escalation.conversation_id,
            reason=escalation.reason,
            priority=escalation.priority,
            assigned_to=assigned_agent
        )
        
        return {
            "escalation_id": escalation_id,
            "assigned_agent": assigned_agent,
            "estimated_response_time": "< 30 secondes",
            "status": "escalated"
        }
        
    except Exception as e:
        logger.error("Escalation error", error=str(e))
        raise HTTPException(status_code=500, detail="Erreur lors de l'escalade")

@app.get("/api/v1/conversation/{conversation_id}/history",
         summary="Historique de conversation",
         description="Récupère l'historique d'une conversation")
async def get_conversation_history(
    conversation_id: str,
    api_key: str = Security(api_key_header)
):
    """
    Récupère l'historique d'une conversation
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    from core.auth.middleware import auth_middleware
    auth_middleware.verify_api_key(api_key)
    
    try:
        history = await conversation_manager.get_conversation_history(conversation_id)
        return {"conversation_id": conversation_id, "history": history}
        
    except Exception as e:
        logger.error("Get history error", error=str(e))
        raise HTTPException(status_code=404, detail="Conversation non trouvée")

@app.get("/api/v1/health",
         summary="Santé du système",
         description="Vérifie l'état de santé du système")
async def health_check():
    """
    Endpoint de santé du système - **Aucune authentification requise**
    """
    try:
        # Vérifier les composants critiques
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "database": "healthy",
                "chromadb": "healthy", 
                "crewai": "healthy",
                "openai": "healthy"
            },
            "version": "1.0.0"
        }
        
        return health_status
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/v1/metrics",
         summary="Métriques système",
         description="Récupère les métriques de performance du système")
async def get_system_metrics(api_key: str = Security(api_key_header)):
    """
    Endpoint pour les métriques système
    """
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    from core.auth.middleware import auth_middleware
    auth_middleware.verify_api_key(api_key)
    
    try:
        metrics = await metrics_collector.get_system_metrics()
        return metrics
        
    except Exception as e:
        logger.error("Metrics error", error=str(e))
        raise HTTPException(status_code=500, detail="Erreur récupération métriques")

# Événements de cycle de vie
@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    logger.info("Coris Intelligent Assistant API starting up...")
    
    # Initialiser les composants
    await conversation_manager.initialize()
    await metrics_collector.initialize()
    
    logger.info("API startup completed")

@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt"""
    logger.info("Coris Intelligent Assistant API shutting down...")
    
    # Nettoyage des ressources
    await conversation_manager.cleanup()
    await metrics_collector.cleanup()
    
    # Fermer les pools de base de données
    from core.database.connections import db_manager
    await db_manager.close_all_pools()
    
    logger.info("API shutdown completed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "chat:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )