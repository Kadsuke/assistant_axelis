"""
Gestionnaire de packs multi-applications
"""
import yaml
from typing import Dict, List, Optional, Set
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
        
        if cache_key in self._filiale_configs:
            return self._filiale_configs[cache_key]
        
        config_path = Path(f"src/applications/{application}/config/filiales/{filiale_id}.yaml")
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self._filiale_configs[cache_key] = config
                return config
        
        logger.warning("Filiale config not found", 
                      filiale_id=filiale_id, 
                      application=application)
        return {}
    
    def get_pack_for_filiale(self, filiale_id: str, application: str) -> str:
        """
        Retourne le pack souscrit par une filiale pour une application
        
        Args:
            filiale_id: ID de la filiale (ex: "coris_ci", "coris_bf")
            application: Nom de l'application (ex: "coris_money")
            
        Returns:
            Nom du pack souscrit (ex: "coris_basic", "coris_advanced")
        """
        filiale_config = self._load_filiale_config(filiale_id, application)
        
        if filiale_config and "applications" in filiale_config:
            app_config = filiale_config["applications"].get(application, {})
            return app_config.get("pack_souscrit", "coris_basic")
        
        # Pack par défaut
        return "coris_basic"
    
    def get_pack_features(self, pack_name: str, application: str) -> Set[str]:
        """
        Retourne les fonctionnalités incluses dans un pack
        
        Args:
            pack_name: Nom du pack (ex: "coris_basic")
            application: Nom de l'application
            
        Returns:
            Set des fonctionnalités disponibles
        """
        features = set()
        
        # Ajouter les fonctionnalités de base
        if pack_name in self.base_packs.get("base_packs", {}):
            base_features = self.base_packs["base_packs"][pack_name].get("features", [])
            features.update(base_features)
        
        # Ajouter les fonctionnalités spécifiques à l'application
        if application in self.app_packs and pack_name in self.app_packs[application]:
            app_features = self.app_packs[application][pack_name].get("features", [])
            features.update(app_features)
        
        return features
    
    def get_pack_agents(self, pack_name: str, application: str) -> List[str]:
        """
        Retourne les agents disponibles pour un pack
        
        Args:
            pack_name: Nom du pack
            application: Nom de l'application
            
        Returns:
            Liste des agents disponibles
        """
        agents = []
        
        # Agents de base
        if pack_name in self.base_packs.get("base_packs", {}):
            base_agents = self.base_packs["base_packs"][pack_name].get("agents", [])
            agents.extend(base_agents)
        
        # Agents spécifiques à l'application
        if application in self.app_packs and pack_name in self.app_packs[application]:
            app_agents = self.app_packs[application][pack_name].get("agents", [])
            agents.extend(app_agents)
        
        return list(set(agents))  # Supprimer les doublons
    
    def get_pack_limits(self, pack_name: str, application: str) -> Dict:
        """
        Retourne les limites d'utilisation d'un pack
        
        Args:
            pack_name: Nom du pack
            application: Nom de l'application
            
        Returns:
            Dictionnaire des limites (tokens, conversations, etc.)
        """
        limits = {}
        
        # Limites de base
        if pack_name in self.base_packs.get("base_packs", {}):
            base_limits = self.base_packs["base_packs"][pack_name].get("limits", {})
            limits.update(base_limits)
        
        # Limites spécifiques à l'application
        if application in self.app_packs and pack_name in self.app_packs[application]:
            app_limits = self.app_packs[application][pack_name].get("limits", {})
            limits.update(app_limits)
        
        return limits
    
    def can_use_feature(self, filiale_id: str, application: str, feature: str) -> bool:
        """
        Vérifie si une filiale peut utiliser une fonctionnalité
        
        Args:
            filiale_id: ID de la filiale
            application: Nom de l'application
            feature: Nom de la fonctionnalité
            
        Returns:
            True si la fonctionnalité est disponible
        """
        pack_name = self.get_pack_for_filiale(filiale_id, application)
        features = self.get_pack_features(pack_name, application)
        
        return feature in features
    
    def can_use_agent(self, filiale_id: str, application: str, agent_name: str) -> bool:
        """
        Vérifie si une filiale peut utiliser un agent
        
        Args:
            filiale_id: ID de la filiale
            application: Nom de l'application
            agent_name: Nom de l'agent
            
        Returns:
            True si l'agent est disponible
        """
        pack_name = self.get_pack_for_filiale(filiale_id, application)
        agents = self.get_pack_agents(pack_name, application)
        
        return agent_name in agents
    
    def get_filiale_info(self, filiale_id: str, application: str) -> Dict:
        """
        Retourne les informations complètes d'une filiale
        
        Args:
            filiale_id: ID de la filiale
            application: Nom de l'application
            
        Returns:
            Dictionnaire avec toutes les informations de la filiale
        """
        filiale_config = self._load_filiale_config(filiale_id, application)
        pack_name = self.get_pack_for_filiale(filiale_id, application)
        
        return {
            "filiale_id": filiale_id,
            "application": application,
            "pack_souscrit": pack_name,
            "features_disponibles": list(self.get_pack_features(pack_name, application)),
            "agents_disponibles": self.get_pack_agents(pack_name, application),
            "limites": self.get_pack_limits(pack_name, application),
            "config": filiale_config.get("filiale", {}),
            "knowledge_base": filiale_config.get("applications", {}).get(application, {}).get("knowledge_base", {}),
            "databases": filiale_config.get("applications", {}).get(application, {}).get("databases", {})
        }
    
    def validate_usage(self, filiale_id: str, application: str, 
                      resource_type: str, current_usage: int) -> bool:
        """
        Valide si l'utilisation actuelle respecte les limites du pack
        
        Args:
            filiale_id: ID de la filiale
            application: Nom de l'application
            resource_type: Type de ressource (ex: "tokens_per_day", "conversations_per_hour")
            current_usage: Utilisation actuelle
            
        Returns:
            True si l'utilisation est dans les limites
        """
        pack_name = self.get_pack_for_filiale(filiale_id, application)
        limits = self.get_pack_limits(pack_name, application)
        
        if resource_type not in limits:
            return True  # Pas de limite définie
        
        limit = limits[resource_type]
        return current_usage <= limit
    
    def get_available_packs(self, application: str) -> List[Dict]:
        """
        Retourne la liste des packs disponibles pour une application
        
        Args:
            application: Nom de l'application
            
        Returns:
            Liste des packs avec leurs caractéristiques
        """
        packs = []
        
        # Packs de base
        for pack_name, pack_config in self.base_packs.get("base_packs", {}).items():
            pack_info = {
                "name": pack_name,
                "type": "base",
                "description": pack_config.get("description", ""),
                "features": pack_config.get("features", []),
                "agents": pack_config.get("agents", []),
                "limits": pack_config.get("limits", {}),
                "price": pack_config.get("price", {})
            }
            packs.append(pack_info)
        
        # Packs spécifiques à l'application
        if application in self.app_packs:
            for pack_name, pack_config in self.app_packs[application].items():
                pack_info = {
                    "name": pack_name,
                    "type": "application",
                    "application": application,
                    "description": pack_config.get("description", ""),
                    "features": pack_config.get("features", []),
                    "agents": pack_config.get("agents", []),
                    "limits": pack_config.get("limits", {}),
                    "price": pack_config.get("price", {})
                }
                packs.append(pack_info)
        
        return packs
    
    def reload_configs(self):
        """Recharge toutes les configurations"""
        logger.info("Reloading pack configurations...")
        
        self.base_packs = self._load_base_packs()
        self.app_packs = self._load_all_app_packs()
        self._filiale_configs.clear()
        
        logger.info("Pack configurations reloaded")
    
    def get_statistics(self) -> Dict:
        """Retourne des statistiques sur les packs configurés"""
        stats = {
            "base_packs_count": len(self.base_packs.get("base_packs", {})),
            "applications_count": len(self.app_packs),
            "total_app_packs": sum(len(packs) for packs in self.app_packs.values()),
            "cached_filiales": len(self._filiale_configs),
            "applications": list(self.app_packs.keys())
        }
        
        return stats

# Instance globale
pack_manager = MultiAppPackManager()