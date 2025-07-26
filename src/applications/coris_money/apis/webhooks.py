### **Étape 16.2 : Webhook pour notifications**

"""
Webhooks pour notifier l'application mobile des événements
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional
import httpx
import asyncio
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

class WebhookEvent(BaseModel):
    event_type: str
    conversation_id: str
    user_id: str
    filiale_id: str
    data: Dict
    timestamp: str

class NotificationPayload(BaseModel):
    user_id: str
    title: str
    message: str
    data: Dict = {}

async def send_push_notification(payload: NotificationPayload):
    """Envoie une notification push via Firebase/OneSignal"""
    # Configuration à adapter selon votre service de push
    push_service_url = "https://api.onesignal.com/notifications"
    
    notification_data = {
        "app_id": "your-onesignal-app-id",
        "filters": [{"field": "tag", "key": "user_id", "relation": "=", "value": payload.user_id}],
        "headings": {"en": payload.title, "fr": payload.title},
        "contents": {"en": payload.message, "fr": payload.message},
        "data": payload.data
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                push_service_url,
                json=notification_data,
                headers={"Authorization": "Basic your-onesignal-api-key"}
            )
            logger.info("Push notification sent", user_id=payload.user_id, status=response.status_code)
        except Exception as e:
            logger.error("Failed to send push notification", error=str(e))

@router.post("/escalation-assigned")
async def handle_escalation_assigned(
    event: WebhookEvent,
    background_tasks: BackgroundTasks
):
    """Webhook appelé quand une escalade est assignée à un agent humain"""
    
    # Notifier l'utilisateur mobile
    notification = NotificationPayload(
        user_id=event.user_id,
        title="Agent disponible",
        message="Un conseiller va vous contacter dans quelques instants",
        data={
            "conversation_id": event.conversation_id,
            "event_type": "escalation_assigned",
            "agent_id": event.data.get("assigned_agent")
        }
    )
    
    background_tasks.add_task(send_push_notification, notification)
    
    return {"status": "processed"}

@router.post("/conversation-resolved")
async def handle_conversation_resolved(
    event: WebhookEvent,
    background_tasks: BackgroundTasks
):
    """Webhook appelé quand une conversation est résolue"""
    
    notification = NotificationPayload(
        user_id=event.user_id,
        title="Conversation résolue",
        message="Votre demande a été traitée avec succès",
        data={
            "conversation_id": event.conversation_id,
            "event_type": "conversation_resolved",
            "resolution": event.data.get("resolution")
        }
    )
    
    background_tasks.add_task(send_push_notification, notification)
    
    return {"status": "processed"}

@router.post("/system-maintenance")
async def handle_system_maintenance(
    event: WebhookEvent,
    background_tasks: BackgroundTasks
):
    """Webhook pour notifier les maintenances système"""
    
    # Notifier tous les utilisateurs de la filiale
    notification = NotificationPayload(
        user_id="all",  # Broadcast
        title="Maintenance programmée",
        message=event.data.get("maintenance_message", "Une maintenance est programmée"),
        data={
            "event_type": "system_maintenance",
            "maintenance_window": event.data.get("maintenance_window")
        }
    )
    
    background_tasks.add_task(send_push_notification, notification)
    
    return {"status": "processed"}