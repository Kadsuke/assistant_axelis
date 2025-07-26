"""
Tests unitaires pour le gestionnaire de packs
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Ajouter src au path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from core.packs.manager import MultiAppPackManager

class TestMultiAppPackManager:
    
    @pytest.fixture
    def pack_manager(self):
        """Fixture pour le gestionnaire de packs"""
        with patch.object(MultiAppPackManager, '_load_base_packs') as mock_base, \
             patch.object(MultiAppPackManager, '_load_all_app_packs') as mock_apps:
            
            # Mock des packs de base
            mock_base.return_value = {
                'base_packs': {
                    'infrastructure_pack': {
                        'features': ['mcp_server', 'vector_database'],
                        'agents': ['core_customer_service'],
                        'tools': ['database_connection']
                    }
                }
            }
            
            # Mock des packs d'applications
            mock_apps.return_value = {
                'coris_money': {
                    'coris_basic': {
                        'inherits_base': ['infrastructure_pack'],
                        'features': ['coris_faq_system'],
                        'agents': ['coris_banking_assistant'],
                        'automation_level': 70
                    }
                }
            }
            
            return MultiAppPackManager()
    
    def test_initialization(self, pack_manager):
        """Test de l'initialisation du gestionnaire"""
        assert pack_manager.base_packs is not None
        assert pack_manager.app_packs is not None
        assert 'coris_money' in pack_manager.app_packs
    
    def test_pack_inheritance_resolution(self, pack_manager):
        """Test de la résolution d'héritage des packs"""
        capabilities = pack_manager._resolve_pack_inheritance('coris_money', 'coris_basic')
        
        # Vérifier que les features sont héritées
        assert 'mcp_server' in capabilities['features']  # Du pack de base
        assert 'coris_faq_system' in capabilities['features']  # Du pack app
        
        # Vérifier les agents
        assert 'core_customer_service' in capabilities['agents']
        assert 'coris_banking_assistant' in capabilities['agents']
        
        # Vérifier l'automation level
        assert capabilities['automation_level'] == 70
    
    @patch.object(MultiAppPackManager, '_load_filiale_config')
    def test_can_access_feature(self, mock_load_config, pack_manager):
        """Test de vérification d'accès aux fonctionnalités"""
        # Mock de la configuration filiale
        mock_load_config.return_value = {
            'filiale': {
                'applications': {
                    'coris_money': {
                        'pack_souscrit': 'coris_basic'
                    }
                }
            }
        }
        
        # Test d'accès autorisé
        assert pack_manager.can_access_feature('test_filiale', 'coris_money', 'coris_faq_system')
        assert pack_manager.can_access_feature('test_filiale', 'coris_money', 'mcp_server')
        
        # Test d'accès refusé
        assert not pack_manager.can_access_feature('test_filiale', 'coris_money', 'premium_feature')
    
    def test_merge_capabilities(self, pack_manager):
        """Test de fusion des capacités"""
        base = {
            'features': ['feature1', 'feature2'],
            'agents': ['agent1'],
            'automation_level': 50
        }
        
        addition = {
            'features': ['feature2', 'feature3'],  # feature2 en doublon
            'agents': ['agent2'],
            'automation_level': 70
        }
        
        result = pack_manager._merge_capabilities(base, addition)
        
        # Vérifier la déduplication
        assert len(result['features']) == 3
        assert 'feature1' in result['features']
        assert 'feature2' in result['features']
        assert 'feature3' in result['features']
        
        # Vérifier la fusion des agents
        assert 'agent1' in result['agents']
        assert 'agent2' in result['agents']
        
        # Vérifier l'écrasement de l'automation level
        assert result['automation_level'] == 70

@pytest.mark.asyncio
class TestPackManagerAsync:
    
    @pytest.fixture
    async def pack_manager(self):
        """Fixture async pour le gestionnaire de packs"""
        return MultiAppPackManager()
    
    @patch.object(MultiAppPackManager, '_load_filiale_config')
    async def test_get_filiale_capabilities_empty_config(self, mock_load_config, pack_manager):
        """Test avec configuration filiale vide"""
        mock_load_config.return_value = {}
        
        capabilities = pack_manager.get_filiale_capabilities('unknown_filiale', 'coris_money')
        assert capabilities == {}
    
    @patch.object(MultiAppPackManager, '_load_filiale_config')
    async def test_get_filiale_capabilities_missing_pack(self, mock_load_config, pack_manager):
        """Test avec pack manquant"""
        mock_load_config.return_value = {
            'filiale': {
                'applications': {
                    'coris_money': {}  # Pas de pack_souscrit
                }
            }
        }
        
        capabilities = pack_manager.get_filiale_capabilities('test_filiale', 'coris_money')
        assert capabilities == {}

if __name__ == "__main__":
    pytest.main([__file__])