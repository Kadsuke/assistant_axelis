"""
Modèles d'authentification
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    user_id: str
    filiale_id: str
    role: str = "user"
    permissions: List[str] = []
    created_at: datetime
    last_login: Optional[datetime] = None

class APIKey(BaseModel):
    key_id: str
    key_hash: str
    role: str
    permissions: List[str]
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True

class LoginRequest(BaseModel):
    user_id: str
    filiale_id: str
    app_version: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: User

class PermissionCheck(BaseModel):
    resource: str
    action: str
    context: dict = {}