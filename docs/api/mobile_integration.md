# Guide d'Intégration Mobile - Coris Intelligent Assistant

## Endpoints Principaux

### 1. Authentification

http
POST /api/v1/auth/login
Content-Type: application/json
{
"user_id": "string",
"filiale_id": "string",
"app_version": "string"
}

### 2. Chat

POST /api/v1/chat
Content-Type: application/json
X-API-Key: your-api-key
{
"user_id": "user123",
"filiale_id": "coris_ci",
"message": "Bonjour, comment consulter mon solde ?",
"channel": "mobile",
"language": "fr"
}

### 3. Reponse

{
"conversation_id": "uuid",
"response": "Pour consulter votre solde...",
"agent_used": "coris_banking_assistant",
"confidence": 0.95,
"suggested_actions": [
"Consulter le solde",
"Voir l'historique"
],
"escalation_needed": false
}

### 4. Escalade vers un agent humain

POST /api/v1/escalate
Content-Type: application/json
X-API-Key: your-api-key
{
"conversation_id": "uuid",
"reason": "complex_query",
"priority": "medium"
}

### 5. historique des echanges

GET /api/v1/conversation/{conversation_id}/history
X-API-Key: your-api-key

### 6. Codes d'Erreur

400 - Requête invalide
401 - Non autorisé (API key invalide)
403 - Accès refusé (pack insuffisant)
429 - Trop de requêtes
500 - Erreur serveur
