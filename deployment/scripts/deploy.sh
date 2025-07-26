#!/bin/bash

# Script de déploiement Coris Intelligent Assistant
set -e

echo "🚀 Déploiement Coris Intelligent Assistant"
echo "=========================================="

# Variables
ENVIRONMENT=${1:-production}
VERSION=${2:-latest}
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"

echo "📋 Configuration:"
echo "   Environment: $ENVIRONMENT"
echo "   Version: $VERSION"
echo "   Backup dir: $BACKUP_DIR"

# 1. Vérifications pré-déploiement
echo "🔍 Vérifications pré-déploiement..."

if [ ! -f ".env" ]; then
    echo "❌ Fichier .env manquant"
    exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Fichier docker-compose.yml manquant"
    exit 1
fi

# Vérifier que Docker est en marche
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker n'est pas en marche"
    exit 1
fi

echo "✅ Vérifications OK"

# 2. Sauvegarde des données
echo "💾 Sauvegarde des données..."
mkdir -p "$BACKUP_DIR"

# Sauvegarde base conversations
if docker ps | grep -q coris-postgres-conversations; then
    echo "   📄 Sauvegarde base conversations..."
    docker exec coris-postgres-conversations pg_dump -U coris_conv_user coris_conversations > "$BACKUP_DIR/conversations.sql"
fi

# Sauvegarde ChromaDB
if [ -d "./data/chroma_data" ]; then
    echo "   📚 Sauvegarde ChromaDB..."
    cp -r ./data/chroma_data "$BACKUP_DIR/"
fi

echo "✅ Sauvegarde terminée"

# 3. Arrêt des services existants
echo "🛑 Arrêt des services existants..."
docker-compose down --remove-orphans

# 4. Mise à jour des images
echo "🔄 Mise à jour des images..."
docker-compose pull

# 5. Construction des nouvelles images
echo "🏗️ Construction des images..."
docker-compose build --no-cache

# 6. Démarrage des services
echo "🚀 Démarrage des services..."
docker-compose up -d

# 7. Vérification de santé
echo "🏥 Vérification de santé..."
sleep 30

# Vérifier l'API
if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "✅ API démarrée avec succès"
else
    echo "❌ Échec du démarrage de l'API"
    echo "📋 Logs de l'API:"
    docker-compose logs coris-assistant
    exit 1
fi

# Vérifier Nginx
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ Nginx démarré avec succès"
else
    echo "❌ Échec du démarrage de Nginx"
    docker-compose logs nginx
    exit 1
fi

# 8. Tests post-déploiement
echo "🧪 Tests post-déploiement..."

# Test de conversation simple
RESPONSE=$(curl -s -X POST "http://localhost/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key" \
  -d '{
    "user_id": "test_deploy",
    "filiale_id": "coris_ci",
    "message": "Test de déploiement"
  }')

if echo "$RESPONSE" | grep -q "conversation_id"; then
    echo "✅ Test de conversation réussi"
else
    echo "❌ Échec du test de conversation"
    echo "Response: $RESPONSE"
fi

# 9. Nettoyage
echo "🧹 Nettoyage..."
docker system prune -f

echo "🎉 Déploiement terminé avec succès!"
echo "📊 Services disponibles:"
echo "   - API: http://localhost/api/v1/docs"
echo "   - Monitoring: http://localhost:3000 (admin/admin123)"
echo "   - Métriques: http://localhost:9090"
echo ""
echo "📋 Commandes utiles:"
echo "   - Logs: docker-compose logs -f"
echo "   - Status: docker-compose ps"
echo "   - Redémarrage: docker-compose restart"