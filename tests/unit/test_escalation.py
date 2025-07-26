"""
Tests unitaires pour le système d'escalade
"""
import pytest
from unittest.mock import patch, AsyncMock
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from core.escalation.detector import EscalationDetector
from core.escalation.router import EscalationRouter

class TestEscalationDetector:
    
    @pytest.fixture
    def detector(self):
        """Fixture pour le détecteur d'escalade"""
        return EscalationDetector()
    
    def test_should_escalate_multiple_failures(self, detector):
        """Test d'escalade pour échecs multiples"""
        context = {
            'failed_attempts': 3,
            'user_message': 'je ne comprends pas',
            'sentiment': 'neutre'
        }
        
        should_escalate, reasons = detector.should_escalate(context)
        
        assert should_escalate is True
        assert 'multiple_failures(3)' in reasons
    
    def test_should_escalate_urgent_keywords(self, detector):
        """Test d'escalade pour mots-clés urgents"""
        context = {
            'failed_attempts': 0,
            'user_message': 'c\'est très urgent j\'ai besoin d\'aide immédiatement',
            'sentiment': 'neutre'
        }
        
        should_escalate, reasons = detector.should_escalate(context)
        
        assert should_escalate is True
        assert 'urgent_keywords' in reasons
        assert 'urgent' in reasons
        assert 'immédiat' in reasons
    
    def test_should_escalate_negative_sentiment(self, detector):
        """Test d'escalade pour sentiment négatif"""
        context = {
            'failed_attempts': 0,
            'user_message': 'je suis mécontent',
            'sentiment': 'negative'
        }
        
        should_escalate, reasons = detector.should_escalate(context)
        
        assert should_escalate is True
        assert 'negative_sentiment' in reasons
    
    def test_should_escalate_explicit_request(self, detector):
        """Test d'escalade pour demande explicite"""
        context = {
            'failed_attempts': 0,
            'user_message': 'je veux parler à un agent humain',
            'sentiment': 'neutre'
        }
        
        should_escalate, reasons = detector.should_escalate(context)
        
        assert should_escalate is True
        assert 'explicit_human_request' in reasons
    
    def test_should_not_escalate_normal_case(self, detector):
        """Test de non-escalade pour cas normal"""
        context = {
            'failed_attempts': 0,
            'user_message': 'bonjour comment consulter mon solde',
            'sentiment': 'neutre'
        }
        
        should_escalate, reasons = detector.should_escalate(context)
        
        assert should_escalate is False
        assert reasons == 'no_escalation_needed'
    
    def test_assess_priority(self, detector):
        """Test d'évaluation de priorité"""
        # Priorité urgente
        urgent_priority = detector.assess_priority('urgent_complaint|technical_error')
        assert urgent_priority == 'urgent'
        
        # Priorité haute
        high_priority = detector.assess_priority('multiple_failures|negative_sentiment')
        assert high_priority == 'high'
        
        # Priorité moyenne
        medium_priority = detector.assess_priority('explicit_human_request')
        assert medium_priority == 'medium'
        
        # Priorité basse
        low_priority = detector.assess_priority('other_reason')
        assert low_priority == 'low'

@pytest.mark.asyncio
class TestEscalationRouter:
    
    @pytest.fixture
    def router(self):
        """Fixture pour le routeur d'escalade"""
        return EscalationRouter()
    
    @patch('core.escalation.router.db_manager')
    async def test_find_best_agent_success(self, mock_db_manager, router):
        """Test de sélection d'agent réussie"""
        # Mock de la connexion database
        mock_conn = AsyncMock()
        mock_db_manager.get_conversations_connection.return_value.__aenter__.return_value = mock_conn
        
        # Mock des agents disponibles
        mock_conn.fetch.return_value = [
            {
                'id': 'agent_001',
                'name': 'Agent Test',
                'specialties': ['reclamations'],
                'languages': ['fr'],
                'current_load': 1,
                'max_concurrent': 5
            }
        ]
        
        # Mock de la mise à jour de charge
        mock_conn.execute = AsyncMock()
        
        context = {
            'reason': 'réclamation urgente',
            'user_language': 'fr',
            'priority': 'high'
        }
        
        agent_id = await router.find_best_agent(context)
        
        assert agent_id == 'agent_001'
        mock_conn.execute.assert_called()  # Vérifier que la charge a été mise à jour
    
    @patch('core.escalation.router.db_manager')
    async def test_find_best_agent_no_agents(self, mock_db_manager, router):
        """Test quand aucun agent n'est disponible"""
        mock_conn = AsyncMock()
        mock_db_manager.get_conversations_connection.return_value.__aenter__.return_value = mock_conn
        
        # Aucun agent disponible
        mock_conn.fetch.return_value = []
        
        context = {
            'reason': 'test',
            'user_language': 'fr',
            'priority': 'medium'
        }
        
        agent_id = await router.find_best_agent(context)
        
        assert agent_id is None
    
    def test_extract_required_expertise(self, router):
        """Test d'extraction d'expertise requise"""
        # Test réclamations
        context = {'reason': 'réclamation client', 'user_message': 'je suis insatisfait'}
        expertise = router._extract_required_expertise(context)
        assert expertise == 'reclamations'
        
        # Test opérations
        context = {'reason': 'problème transfert', 'user_message': 'mon transfert est bloqué'}
        expertise = router._extract_required_expertise(context)
        assert expertise == 'operations'
        
        # Test technique
        context = {'reason': 'bug application', 'user_message': 'l\'app ne fonctionne pas'}
        expertise = router._extract_required_expertise(context)
        assert expertise == 'technique'
        
        # Test général
        context = {'reason': 'question générale', 'user_message': 'bonjour'}
        expertise = router._extract_required_expertise(context)
        assert expertise == 'general'
    
    @patch('core.escalation.router.db_manager')
    async def test_release_agent(self, mock_db_manager, router):
        """Test de libération d'agent"""
        mock_conn = AsyncMock()
        mock_db_manager.get_conversations_connection.return_value.__aenter__.return_value = mock_conn
        
        await router.release_agent('agent_001')
        
        # Vérifier que deux requêtes ont été exécutées
        assert mock_conn.execute.call_count == 2

if __name__ == "__main__":
    pytest.main([__file__])