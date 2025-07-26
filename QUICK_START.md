# 🚀 Quick Start - Coris Intelligent Assistant

## Installation Rapide (5 minutes)

### 1. Prérequis

```bash
# Installer Docker et Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Installer UV (gestionnaire Python)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Cloner et Configurer
   bash# Si vous avez le code
   cd coris_intelligent_assistant

# Configurer l'environnement

cp .env.template .env

# Éditer .env avec vos vraies credentials

3. Démarrage Development
   bash# Démarrage rapide pour développement
   docker-compose up -d
4. Démarrage Production
   bash# Déploiement production complet
   chmod +x deployment/deploy_production.sh
   ./deployment/deploy_production.sh
   Test Rapide
   API Test
   bashcurl -X POST "http://localhost/api/v1/chat" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: test-key" \
    -d '{
   "user_id": "test_user",
   "filiale_id": "coris_ci",
   "message": "Bonjour, comment consulter mon solde ?"
   }'
   Test Complet du Système
   bashuv run python scripts/final_system_test.py
   Endpoints Principaux

API Documentation: http://localhost/docs
Health Check: http://localhost/api/v1/health
Metrics: http://localhost/api/v1/metrics
Grafana: http://localhost:3000 (admin/admin123)

Intégration Mobile
Configuration App Mobile
javascriptconst API_CONFIG = {
baseUrl: "http://your-server/api/v1",
apiKey: "your-api-key",
timeout: 30000
};
Exemple d'Usage
javascriptconst response = await fetch(`${API_CONFIG.baseUrl}/chat`, {
method: 'POST',
headers: {
'Content-Type': 'application/json',
'X-API-Key': API_CONFIG.apiKey
},
body: JSON.stringify({
user_id: userId,
filiale_id: filialeId,
message: userMessage,
channel: 'mobile'
})
});
Gestion des Packs
Configuration Filiale
yaml# src/applications/coris_money/config/filiales/your_filiale.yaml
filiale:
id: "your_filiale"
applications:
coris_money:
pack_souscrit: "coris_basic" # ou coris_advanced, coris_premium
Vérification Pack
bash# Via API
curl "http://localhost/api/v1/filiale/your_filiale/capabilities"
Maintenance
Commandes Essentielles
bash# Status du système
./deployment/scripts/maintenance.sh status

# Sauvegarde

./deployment/scripts/maintenance.sh backup

# Logs en temps réel

./deployment/scripts/maintenance.sh logs

# Monitoring

./deployment/scripts/maintenance.sh monitor
Mise à Jour
bash# Mise à jour complète
./deployment/scripts/maintenance.sh update
Troubleshooting
Problèmes Courants
API ne répond pas
bash# Vérifier les services
docker-compose ps

# Consulter les logs

docker-compose logs coris-assistant

# Redémarrer

docker-compose restart coris-assistant
Base de données inaccessible
bash# Vérifier PostgreSQL
docker exec coris-postgres-conversations pg_isready

# Réinitialiser

uv run python scripts/init_databases.py
ChromaDB vide
bash# Réinitialiser les knowledge bases
uv run python scripts/init_knowledge_bases.py
Problème de permissions de pack
bash# Vérifier la configuration
cat src/applications/coris_money/config/filiales/your_filiale.yaml

# Recharger la configuration

docker-compose restart coris-assistant
Support

Documentation: /docs/
Architecture: /docs/architecture/
API: /docs/api/
Logs: /opt/coris/logs/

Prochaines Étapes

Personnaliser les knowledge bases pour vos filiales
Configurer les packs selon vos besoins
Intégrer avec votre application mobile
Déployer en production avec SSL
Monitorer les performances et ajuster

## 🎯 **COMMANDES FINALES POUR DÉMARRER**

```bash
# 1. Test complet du système
uv run python scripts/final_system_test.py

# 2. Démarrage développement
docker-compose up -d

# 3. Test de l'API
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "user_id": "demo_user",
    "filiale_id": "coris_ci",
    "message": "Bonjour, comment puis-je vous aider aujourd''hui ?"
  }'

# 4. Déploiement production (quand prêt)
chmod +x deployment/deploy_production.sh
./deployment/deploy_production.sh
```
