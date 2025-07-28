"""
Middleware d'authentification et autorisation - Version corrigée
"""
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
import os
import jwt
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

security = HTTPBearer(auto_error=False)

class AuthMiddleware:
    def __init__(self):
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-this")
        self.algorithm = "HS256"
        self.api_keys = self._load_api_keys()
        logger.info(f"Loaded {len(self.api_keys)} API keys")
    
    def _load_api_keys(self) -> Dict[str, str]:
        """Charge les clés API autorisées"""
        api_keys_str = os.getenv("API_KEYS", "test-key:basic,admin-key:admin")
        
        api_keys = {}
        for key_pair in api_keys_str.split(","):
            key_pair = key_pair.strip()
            if ":" in key_pair:
                key, role = key_pair.split(":", 1)
                api_keys[key.strip()] = role.strip()
            else:
                # Si pas de rôle spécifié, utiliser 'basic'
                api_keys[key_pair.strip()] = "basic"
        
        logger.info(f"API keys configured: {list(api_keys.keys())}")
        return api_keys
    
    def verify_api_key(self, api_key: str) -> str:
        """
        Vérifie une clé API
        
        Returns:
            Role de l'utilisateur
        """
        if not api_key:
            raise HTTPException(status_code=401, detail="API key required")
            
        if api_key in self.api_keys:
            role = self.api_keys[api_key]
            logger.debug("API key verified", role=role, key_prefix=api_key[:8])
            return role
        else:
            logger.warning("Invalid API key attempted", key_prefix=api_key[:8] if api_key else "None")
            raise HTTPException(status_code=401, detail="Invalid API key")

# Instance globale
auth_middleware = AuthMiddleware()

async def verify_api_key(request: Request) -> str:
    """Dependency pour vérifier les clés API depuis header ou query"""
    
    # Essayer depuis le header X-API-Key
    api_key = request.headers.get("X-API-Key")
    
    # Fallback: essayer depuis Authorization Bearer
    if not api_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:]  # Enlever "Bearer "
    
    # Fallback: essayer depuis les query params (pour tests rapides)
    if not api_key:
        api_key = request.query_params.get("api_key")
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Use X-API-Key header or Authorization Bearer token"
        )
    
    return auth_middleware.verify_api_key(api_key)

async def verify_admin_access(role: str = None) -> str:
    """Dependency pour vérifier l'accès admin"""
    if not role:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    if role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return role

# Fonction utilitaire pour vérifier rapidement une clé
def quick_verify_key(api_key: str) -> bool:
    """Vérification rapide d'une clé API"""
    try:
        auth_middleware.verify_api_key(api_key)
        return True
    except HTTPException:
        return False