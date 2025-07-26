"""
Configuration globale pour les tests
"""
import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Ajouter src au path
sys.path.append(str(Path(__file__).parent.parent / "src"))

# Configuration des variables d'environnement pour les tests
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("CHROMADB_PERSIST_DIRECTORY", "./test_data/chroma")

@pytest.fixture(scope="session")
def event_loop():
    """Crée une boucle d'événements pour la session de test"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_db_connection():
    """Mock pour les connexions de base de données"""
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock()
    mock_conn.fetch = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchval = AsyncMock()
    return mock_conn

@pytest.fixture
def mock_chroma_manager():
    """Mock pour le gestionnaire ChromaDB"""
    mock_manager = MagicMock()
    mock_manager.get_or_create_collection = MagicMock()
    mock_manager.add_documents = AsyncMock()
    mock_manager.query_documents = AsyncMock()
    mock_manager.get_collection_stats = MagicMock()
    return mock_manager

@pytest.fixture
def sample_conversation_context():
    """Contexte de conversation d'exemple pour les tests"""
    return {
        "conversation_info": {
            "id": "test-conv-001",
            "user_id": "test-user-001",
            "filiale_id": "coris_ci",
            "application_id": "coris_money",
            "pack_level": "coris_basic",
            "channel": "mobile",
            "status": "active"
        },
        "messages": [
            {
                "role": "user",
                "content": "Bonjour, j'ai un problème avec mon transfert",
                "timestamp": "2024-01-01T10:00:00Z"
            },
            {
                "role": "assistant", 
                "content": "Bonjour ! Je vais vous aider avec votre transfert.",
                "agent_used": "coris_banking_assistant",
                "timestamp": "2024-01-01T10:00:05Z"
            }
        ],
        "agent_actions": [
            {
                "agent_name": "coris_banking_assistant",
                "action_type": "query_transfer_status",
                "success": True,
                "execution_time_ms": 1500,
               "timestamp": "2024-01-01T10:00:05Z"
           }
       ],
       "failed_attempts": 0,
       "total_messages": 2
   }

@pytest.fixture
def sample_filiale_config():
   """Configuration de filiale d'exemple"""
   return {
       "filiale": {
           "id": "coris_ci",
           "name": "Coris Bank Côte d'Ivoire",
           "applications": {
               "coris_money": {
                   "active": True,
                   "pack_souscrit": "coris_basic",
                   "knowledge_base": {
                       "chroma_collection": "coris_money_coris_ci",
                       "languages": ["fr", "en"]
                   },
                   "databases": {
                       "datawarehouse": {"schema": "coris_ci"},
                       "reclamations": {"schema": "coris_ci_complaints"}
                   }
               }
           }
       }
   }

@pytest.fixture
def sample_escalation_context():
   """Contexte d'escalade d'exemple"""
   return {
       "conversation_id": "test-conv-001",
       "reason": "complex_technical_issue",
       "priority": "high",
       "user_language": "fr",
       "user_message": "Mon transfert urgent ne fonctionne pas depuis 2 heures",
       "failed_attempts": 3,
       "sentiment": "negative",
       "technical_error": True
   }

@pytest.fixture(autouse=True)
def clean_test_environment():
   """Nettoie l'environnement de test avant chaque test"""
   # Nettoyer les données de test si nécessaire
   test_data_dir = Path("./test_data")
   if test_data_dir.exists():
       import shutil
       shutil.rmtree(test_data_dir)
   
   yield
   
   # Nettoyer après le test
   if test_data_dir.exists():
       shutil.rmtree(test_data_dir)

class AsyncContextManager:
   """Helper pour mocker les context managers async"""
   def __init__(self, mock_obj):
       self.mock_obj = mock_obj
   
   async def __aenter__(self):
       return self.mock_obj
   
   async def __aexit__(self, exc_type, exc_val, exc_tb):
       pass

@pytest.fixture
def async_context_manager():
   """Factory pour créer des context managers async"""
   return AsyncContextManager