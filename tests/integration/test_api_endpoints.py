"""
Tests d'intégration pour les endpoints API
"""
import pytest
import httpx
import asyncio
from unittest.mock import patch, AsyncMock
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from applications.coris_money.apis.chat import app

@pytest.mark.asyncio
class TestChatAPI:
    
    @pytest.fixture
    async def client(self):
        """Client HTTP pour les tests"""
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    def auth_headers(self):
        """Headers d'authentification"""
        return {"X-API-Key": "test-key"}
    
    async def test_health_endpoint(self, client):
        """Test de l'endpoint de santé"""
        response = await client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data
    
    @patch('applications.coris_money.apis.chat.crew_manager')
    @patch('applications.coris_money.apis.chat.conversation_manager')
    async def test_chat_endpoint_success(self, mock_conv_manager, mock_crew_manager, client, auth_headers):
        """Test de succès de l'endpoint chat"""
        # Mock du gestionnaire de conversations
        mock_conv_manager.get_or_create_conversation = AsyncMock(return_value="test-conv-001")
        mock_conv_manager.add_message = AsyncMock(return_value="test-msg-001")
        
        # Mock du gestionnaire CrewAI
        mock_crew_manager.process_user_query = AsyncMock(return_value={
            "success": True,
            "result": "Bonjour ! Comment puis-je vous aider ?",
            "crew_agents": ["coris_banking_assistant"],
            "tasks_executed": 2
        })
        
        # Mock du détecteur d'escalade
        with patch('applications.coris_money.apis.chat.escalation_detector') as mock_escalation:
            mock_escalation.should_escalate.return_value = (False, "no_escalation_needed")
            
            payload = {
                "user_id": "test_user",
                "filiale_id": "coris_ci",
                "message": "Bonjour, comment consulter mon solde ?",
                "channel": "mobile"
            }
            
            response = await client.post("/api/v1/chat", json=payload, headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert "conversation_id" in data
            assert "response" in data
            assert "agent_used" in data
            assert data["escalation_needed"] is False
            assert data["conversation_id"] == "test-conv-001"
    
    @patch('applications.coris_money.apis.chat.crew_manager')
    async def test_chat_endpoint_crew_failure(self, mock_crew_manager, client, auth_headers):
        """Test d'échec du système CrewAI"""
        mock_crew_manager.process_user_query = AsyncMock(return_value={
            "success": False,
            "error": "OpenAI API error"
        })
        
        payload = {
            "user_id": "test_user",
            "filiale_id": "coris_ci", 
            "message": "Test message",
            "channel": "mobile"
        }
        
        response = await client.post("/api/v1/chat", json=payload, headers=auth_headers)
        
        assert response.status_code == 500
    
    async def test_chat_endpoint_unauthorized(self, client):
        """Test sans authentification"""
        payload = {
            "user_id": "test_user",
            "filiale_id": "coris_ci",
            "message": "Test message"
        }
        
        response = await client.post("/api/v1/chat", json=payload)
        
        assert response.status_code == 403  # Forbidden - pas d'API key
    
    @patch('applications.coris_money.apis.chat.conversation_manager')
    async def test_escalate_endpoint(self, mock_conv_manager, client, auth_headers):
        """Test de l'endpoint d'escalade"""
        with patch('applications.coris_money.apis.chat.EscalationRouter') as mock_router_class, \
             patch('applications.coris_money.apis.chat.ContextBuilder') as mock_context_class:
            
            # Mock du routeur
            mock_router = mock_router_class.return_value
            mock_router.find_best_agent = AsyncMock(return_value="agent_001")
            
            # Mock du context builder
            mock_context = mock_context_class.return_value
            mock_context.prepare_escalation_context = AsyncMock(return_value={
                "summary": "Test escalation context"
            })
            
            # Mock du gestionnaire de conversations
            mock_conv_manager.create_escalation = AsyncMock(return_value="esc-001")
            
            payload = {
                "conversation_id": "test-conv-001",
                "reason": "complex_issue",
                "priority": "high"
            }
            
            response = await client.post("/api/v1/escalate", json=payload, headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            
            assert "escalation_id" in data
            assert "assigned_agent" in data
            assert data["assigned_agent"] == "agent_001"
            assert "estimated_response_time" in data
    
    @patch('applications.coris_money.apis.chat.conversation_manager')
    async def test_conversation_history_endpoint(self, mock_conv_manager, client, auth_headers):
        """Test de récupération d'historique"""
        mock_conv_manager.get_conversation_history = AsyncMock(return_value=[
            {
                "role": "user",
                "content": "Bonjour",
                "timestamp": "2024-01-01T10:00:00Z"
            },
            {
                "role": "assistant",
                "content": "Bonjour ! Comment puis-je vous aider ?",
                "agent_used": "coris_banking_assistant",
                "timestamp": "2024-01-01T10:00:05Z"
            }
        ])
        
        response = await client.get("/api/v1/conversation/test-conv-001/history", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "conversation_id" in data
        assert "history" in data
        assert len(data["history"]) == 2
        assert data["history"][0]["role"] == "user"
        assert data["history"][1]["role"] == "assistant"
    
    @patch('applications.coris_money.apis.chat.metrics_collector')
    async def test_metrics_endpoint(self, mock_metrics, client, auth_headers):
        """Test de l'endpoint de métriques"""
        mock_metrics.get_system_metrics = AsyncMock(return_value={
            "system": {
                "uptime_seconds": 3600,
                "status": "healthy",
                "version": "1.0.0"
            },
            "conversations": {
                "total_24h": 150,
                "by_filiale": []
            },
            "performance": {
                "avg_tokens_per_message": 25.5,
                "total_messages_24h": 300
            }
        })
        
        response = await client.get("/api/v1/metrics", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "system" in data
        assert "conversations" in data
        assert "performance" in data
        assert data["system"]["status"] == "healthy"

@pytest.mark.asyncio 
class TestAPIValidation:
    
    @pytest.fixture
    async def client(self):
        """Client HTTP pour les tests de validation"""
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    def auth_headers(self):
        return {"X-API-Key": "test-key"}
    
    async def test_chat_missing_fields(self, client, auth_headers):
        """Test avec champs manquants"""
        # Payload incomplet
        payload = {
            "user_id": "test_user"
            # Manque filiale_id et message
        }
        
        response = await client.post("/api/v1/chat", json=payload, headers=auth_headers)
        
        assert response.status_code == 422  # Validation error
    
    async def test_chat_invalid_field_types(self, client, auth_headers):
        """Test avec types de champs invalides"""
        payload = {
            "user_id": 123,  # Devrait être string
            "filiale_id": "coris_ci",
            "message": "Test message"
        }
        
        response = await client.post("/api/v1/chat", json=payload, headers=auth_headers)
        
        assert response.status_code == 422
    
    async def test_escalate_missing_conversation_id(self, client, auth_headers):
        """Test d'escalade sans conversation_id"""
        payload = {
            "reason": "test_reason"
            # Manque conversation_id
        }
        
        response = await client.post("/api/v1/escalate", json=payload, headers=auth_headers)
        
        assert response.status_code == 422

if __name__ == "__main__":
    pytest.main([__file__])