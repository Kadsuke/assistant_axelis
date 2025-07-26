"""
Middleware d'authentification et autorisation
"""
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os
import jwt
from datetime import datetime, timedelta
import structlog
from fastapi import Request


logger = structlog.get_logger()

security = HTTPBearer()

class AuthMiddleware:
    def __init__(self):
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-this")
        self.algorithm = "HS256"
        self.api_keys = self._load_api_keys()
    
    def _load_api_keys(self) -> dict:
        """Charge les clés API autorisées"""
        api_keys_str = os.getenv("API_KEYS", "test-key:basic,admin-key:admin")
        
        api_keys = {}
        for key_pair in api_keys_str.split(","):
            if ":" in key_pair:
                key, role = key_pair.strip().split(":", 1)
                api_keys[key] = role
        
        return api_keys
    
    def verify_api_key(self, api_key: str) -> str:
        """
        Vérifie une clé API
        
        Returns:
            Role de l'utilisateur
        """
        if api_key in self.api_keys:
            role = self.api_keys[api_key]
            logger.info("API key verified", role=role)
            return role
        else:
            logger.warning("Invalid API key used", api_key=api_key[:8] + "...")
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Crée un token JWT"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=30)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
        return encoded_jwt
    
    def verify_token(self, token: str) -> dict:
        """Vérifie un token JWT"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

# Instance globale
auth_middleware = AuthMiddleware()

async def verify_api_key(api_key: str = Security(security)) -> str:
    """Dependency pour vérifier les clés API"""
    if api_key is None:
        # Fallback pour les headers X-API-Key
        # Cette partie sera gérée dans l'endpoint directement
        raise HTTPException(status_code=401, detail="API key required")
    
    return auth_middleware.verify_api_key(api_key.credentials)

async def verify_admin_access(role: str = Depends(verify_api_key)) -> str:
    """Dependency pour vérifier l'accès admin"""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return role