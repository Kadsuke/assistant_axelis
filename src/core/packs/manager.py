"""
Gestionnaire de packs multi-applications
"""
import yaml
from typing import Dict, List, Optional
from pathlib import Path
import structlog

logger = structlog.get_logger()

class MultiAppPackManager:
    def __init__(self):
        self.base_packs = self._load_base_packs()
        self.app_packs = self._load_all_app_packs()
        self._filiale_configs = {}
        
    def _load_base_packs(self) -> Dict:
        """Charge les packs de base"""
        base_packs_path = Path("src/core/packs/config/base_packs.yaml")
        if base_packs_path.exists():
            with open(base_packs_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}
    
    def _load_all_app_packs(self) -> Dict:
        """Charge tous les packs d'applications"""
        app_packs = {}
        apps_dir = Path("src/applications")
        
        for app_dir in apps_dir.iterdir():
            if app_dir.is_dir():
                app_packs_path = app_dir / "config" / "app_packs.yaml"
                if app_packs_path.exists():
                    with open(app_packs_path, 'r', encoding='utf-8') as f:
                        app_data = yaml.safe_load(f)
                        app_name = app_dir.name
                        app_packs[app_name] = app_data.get(f"{app_name}_packs", {})
        
        return app_packs
    
    def _load_filiale_config(self, filiale_id: str, application: str) -> Dict:
        """Charge la configuration d'une filiale"""
        cache_key = f"{application}_{filiale_id}"
        
        if cache_key not in self._filiale_configs:
            config_path = Path(f"src/applications/{application}/config/filiales/{filiale_id}.yaml")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._filiale_configs[cache_key] = yaml.safe_load(f)
            else:
                logger.warning(f"Configuration not found for {cache_key}")
                self._filiale_configs[cache_key] = {}
        
        return self._filiale_configs[cache_key]
    
    def get_filiale_capabilities(self, filiale_id: str, application: str) -> Dict:
        """Retourne les capacités basées sur le pack souscrit"""
        filiale_config = self._load_filiale_config(filiale_id, application)
        
        if not filiale_config:
            return {}
            
        app_config = filiale_config.get('filiale', {}).get('applications', {}).get(application, {})
        pack_souscrit = app_config.get('pack_souscrit')
        
        if not pack_souscrit:
            logger.warning(f"No pack subscription found for {filiale_id} - {application}")
            return {}
        
        capabilities = self._resolve_pack_inheritance(application, pack_souscrit)
        return capabilities
    
    def can_access_feature(self, filiale_id: str, application: str, feature: str) -> bool:
        """Vérifie l'accès à une fonctionnalité"""
        capabilities = self.get_filiale_capabilities(filiale_id, application)
        return feature in capabilities.get('features', [])
    
    def _resolve_pack_inheritance(self, application: str, pack_name: str) -> Dict:
        """Résout l'héritage des packs"""
        if application not in self.app_packs or pack_name not in self.app_packs[application]:
            return {}
        
        app_pack = self.app_packs[application][pack_name]
        capabilities = {
            'features': [],
            'agents': [],
            'tools': [],
            'channels': ['mobile'],
            'automation_level': 50
        }
        
        # Héritage des packs de base
        for base_pack_name in app_pack.get('inherits_base', []):
            if base_pack_name in self.base_packs.get('base_packs', {}):
                base_pack = self.base_packs['base_packs'][base_pack_name]
                capabilities = self._merge_capabilities(capabilities, base_pack)
        
        # Ajout des capacités du pack actuel
        capabilities = self._merge_capabilities(capabilities, app_pack)
        
        return capabilities
    
    def _merge_capabilities(self, base: Dict, addition: Dict) -> Dict:
        """Fusionne les capacités de deux packs"""
        result = base.copy()
        
        for key in ['features', 'agents', 'tools']:
            if key in addition:
                result[key] = list(set(result.get(key, []) + addition[key]))
        
        for key in ['channels']:
            if key in addition:
                result[key] = addition[key]
        
        if 'automation_level' in addition:
            result['automation_level'] = addition['automation_level']
        
        return result