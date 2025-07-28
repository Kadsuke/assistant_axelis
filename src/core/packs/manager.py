"""
Gestionnaire de packs multi-applications - Version corrigée
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
        """Charge les packs de base avec gestion d'erreur"""
        base_packs_path = Path("src/core/packs/config/base_packs.yaml")
        
        try:
            if base_packs_path.exists():
                with open(base_packs_path, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)
                    if content and isinstance(content, dict):
                        logger.info(f"Loaded base packs: {list(content.get('base_packs', {}).keys())}")
                        return content
                    else:
                        logger.warning("Base packs file is empty or invalid")
            else:
                logger.warning(f"Base packs file not found: {base_packs_path}")
        except Exception as e:
            logger.error(f"Error loading base packs: {e}")
        
        # Configuration par défaut si le fichier n'existe pas
        return {
            "base_packs": {
                "coris_basic": {
                    "name": "Coris Basic",
                    "description": "Pack de base",
                    "features": ["basic_chat", "faq_search"],
                    "agents": ["general_assistant"],
                    "limits": {"tokens_per_day": 10000}
                },
                "coris_advanced": {
                    "name": "Coris Advanced", 
                    "description": "Pack avancé",
                    "features": ["basic_chat", "faq_search", "advanced_analytics"],
                    "agents": ["general_assistant", "business_specialist"],
                    "limits": {"tokens_per_day": 50000}
                }
            }
        }
    
    def _load_all_app_packs(self) -> Dict:
        """Charge tous les packs d'applications avec gestion d'erreur robuste"""
        app_packs = {}
        apps_dir = Path("src/applications")
        
        if not apps_dir.exists():
            logger.warning(f"Applications directory not found: {apps_dir}")
            return {}
        
        for app_dir in apps_dir.iterdir():
            if not app_dir.is_dir():
                continue
                
            app_name = app_dir.name
            app_packs_path = app_dir / "config" / "app_packs.yaml"
            
            try:
                if app_packs_path.exists():
                    with open(app_packs_path, 'r', encoding='utf-8') as f:
                        app_data = yaml.safe_load(f)
                        
                    # Vérification robuste du contenu
                    if app_data is None:
                        logger.warning(f"Empty YAML file: {app_packs_path}")
                        app_packs[app_name] = {}
                    elif isinstance(app_data, dict):
                        # Chercher les packs avec plusieurs clés possibles
                        packs_key = f"{app_name}_packs"
                        if packs_key in app_data:
                            app_packs[app_name] = app_data[packs_key]
                        elif "packs" in app_data:
                            app_packs[app_name] = app_data["packs"]
                        elif len(app_data) == 1 and isinstance(list(app_data.values())[0], dict):
                            # Si il n'y a qu'une clé et que c'est un dict, l'utiliser
                            app_packs[app_name] = list(app_data.values())[0]
                        else:
                            logger.warning(f"No packs found in {app_packs_path}, keys: {list(app_data.keys())}")
                            app_packs[app_name] = {}
                    else:
                        logger.warning(f"Invalid YAML structure in {app_packs_path}")
                        app_packs[app_name] = {}
                        
                    logger.info(f"Loaded app packs for {app_name}: {list(app_packs[app_name].keys())}")
                else:
                    logger.info(f"No app packs file found for {app_name}")
                    app_packs[app_name] = {}
                    
            except Exception as e:
                logger.error(f"Error loading app packs for {app_name}: {e}")
                app_packs[app_name] = {}
        
        return app_packs
    
    def _load_filiale_config(self, filiale_id: str, application: str) -> Dict:
        """Charge la configuration d'une filiale avec gestion d'erreur"""
        cache_key = f"{application}_{filiale_id}"
        
        if cache_key in self._filiale_configs:
            return self._filiale_configs[cache_key]
        
        config_path = Path(f"src/applications/{application}/config/filiales/{filiale_id}.yaml")
        
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    
                if config and isinstance(config, dict):
                    self._filiale_configs[cache_key] = config
                    return config
                else:
                    logger.warning(f"Empty or invalid filiale config: {config_path}")
            else:
                logger.info(f"Filiale config not found: {config_path}")
        except Exception as e:
            logger.error(f"Error loading filiale config: {e}")
        
        # Configuration par défaut
        default_config = {
            "filiale": {
                "id": filiale_id,
                "name": f"Filiale {filiale_id}"
            },
            "applications": {
                application: {
                    "active": True,
                    "pack_souscrit": "coris_basic"
                }
            }
        }
        
        self._filiale_configs[cache_key] = default_config
        return default_config
    
    def get_pack_for_filiale(self, filiale_id: str, application: str) -> str:
        """
        Retourne le pack souscrit par une filiale pour une application
        """
        try:
            filiale_config = self._load_filiale_config(filiale_id, application)
            
            if filiale_config and "applications" in filiale_config:
                app_config = filiale_config["applications"].get(application, {})
                pack = app_config.get("pack_souscrit", "coris_basic")
                logger.debug(f"Pack for {filiale_id}/{application}: {pack}")
                return pack
        except Exception as e:
            logger.error(f"Error getting pack for filiale: {e}")
        
        # Pack par défaut
        return "coris_basic"
    
    def get_pack_features(self, pack_name: str, application: str) -> Set[str]:
        """
        Retourne les fonctionnalités incluses dans un pack
        """
        features = set()
        
        try:
            # Ajouter les fonctionnalités de base
            if "base_packs" in self.base_packs and pack_name in self.base_packs["base_packs"]:
                base_features = self.base_packs["base_packs"][pack_name].get("features", [])
                features.update(base_features)
            
            # Ajouter les fonctionnalités spécifiques à l'application
            if application in self.app_packs and pack_name in self.app_packs[application]:
                app_features = self.app_packs[application][pack_name].get("features", [])
                features.update(app_features)
        except Exception as e:
            logger.error(f"Error getting pack features: {e}")
        
        return features
    
    def get_pack_agents(self, pack_name: str, application: str) -> List[str]:
        """
        Retourne les agents disponibles pour un pack
        """
        agents = []
        
        try:
            # Agents de base
            if "base_packs" in self.base_packs and pack_name in self.base_packs["base_packs"]:
                base_agents = self.base_packs["base_packs"][pack_name].get("agents", [])
                agents.extend(base_agents)
            
            # Agents spécifiques à l'application
            if application in self.app_packs and pack_name in self.app_packs[application]:
                app_agents = self.app_packs[application][pack_name].get("agents", [])
                agents.extend(app_agents)
        except Exception as e:
            logger.error(f"Error getting pack agents: {e}")
        
        return list(set(agents))  # Supprimer les doublons
    
    def get_pack_limits(self, pack_name: str, application: str) -> Dict:
        """
        Retourne les limites d'utilisation d'un pack
        """
        limits = {}
        
        try:
            # Limites de base
            if "base_packs" in self.base_packs and pack_name in self.base_packs["base_packs"]:
                base_limits = self.base_packs["base_packs"][pack_name].get("limits", {})
                limits.update(base_limits)
            
            # Limites spécifiques à l'application
            if application in self.app_packs and pack_name in self.app_packs[application]:
                app_limits = self.app_packs[application][pack_name].get("limits", {})
                limits.update(app_limits)
        except Exception as e:
            logger.error(f"Error getting pack limits: {e}")
        
        return limits
    
    def can_use_feature(self, filiale_id: str, application: str, feature: str) -> bool:
        """
        Vérifie si une filiale peut utiliser une fonctionnalité
        """
        try:
            pack_name = self.get_pack_for_filiale(filiale_id, application)
            features = self.get_pack_features(pack_name, application)
            
            return feature in features
        except Exception as e:
            logger.error(f"Error checking feature access: {e}")
            return True  # Accès par défaut en cas d'erreur
    
    def can_use_agent(self, filiale_id: str, application: str, agent_name: str) -> bool:
        """
        Vérifie si une filiale peut utiliser un agent
        """
        try:
            pack_name = self.get_pack_for_filiale(filiale_id, application)
            agents = self.get_pack_agents(pack_name, application)
            
            return agent_name in agents
        except Exception as e:
            logger.error(f"Error checking agent access: {e}")
            return True  # Accès par défaut en cas d'erreur
    
    def get_filiale_capabilities(self, filiale_id: str, application: str) -> Dict:
        """
        Retourne les capacités complètes d'une filiale
        """
        try:
            pack_name = self.get_pack_for_filiale(filiale_id, application)
            
            return {
                "filiale_id": filiale_id,
                "application": application,
                "pack_name": pack_name,
                "features": list(self.get_pack_features(pack_name, application)),
                "agents": self.get_pack_agents(pack_name, application),
                "limits": self.get_pack_limits(pack_name, application),
                "automation_level": self._calculate_automation_level(pack_name)
            }
        except Exception as e:
            logger.error(f"Error getting filiale capabilities: {e}")
            return {
                "filiale_id": filiale_id,
                "application": application,
                "pack_name": "coris_basic",
                "features": ["basic_chat"],
                "agents": ["general_assistant"],
                "limits": {"tokens_per_day": 1000},
                "automation_level": 30
            }
    
    def _calculate_automation_level(self, pack_name: str) -> int:
        """Calcule le niveau d'automatisation d'un pack"""
        levels = {
            "coris_basic": 30,
            "coris_advanced": 70,
            "coris_premium": 95
        }
        return levels.get(pack_name, 30)
    
    def validate_usage(self, filiale_id: str, application: str, 
                      resource_type: str, current_usage: int) -> bool:
        """
        Valide si l'utilisation actuelle respecte les limites du pack
        """
        try:
            pack_name = self.get_pack_for_filiale(filiale_id, application)
            limits = self.get_pack_limits(pack_name, application)
            
            if resource_type not in limits:
                return True  # Pas de limite définie
            
            limit = limits[resource_type]
            return current_usage <= limit
        except Exception as e:
            logger.error(f"Error validating usage: {e}")
            return True  # Permettre par défaut en cas d'erreur
    
    def reload_configs(self):
        """Recharge toutes les configurations"""
        try:
            logger.info("Reloading pack configurations...")
            
            self.base_packs = self._load_base_packs()
            self.app_packs = self._load_all_app_packs()
            self._filiale_configs.clear()
            
            logger.info("Pack configurations reloaded successfully")
        except Exception as e:
            logger.error(f"Error reloading configs: {e}")
    
    def get_statistics(self) -> Dict:
        """Retourne des statistiques sur les packs configurés"""
        try:
            stats = {
                "base_packs_count": len(self.base_packs.get("base_packs", {})),
                "applications_count": len(self.app_packs),
                "total_app_packs": sum(len(packs) for packs in self.app_packs.values()),
                "cached_filiales": len(self._filiale_configs),
                "applications": list(self.app_packs.keys())
            }
            
            return stats
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e)}

# Instance globale avec gestion d'erreur
try:
    pack_manager = MultiAppPackManager()
    logger.info("Pack manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize pack manager: {e}")
    # Créer une instance minimale en cas d'erreur
    pack_manager = None