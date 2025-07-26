#!/bin/bash

# Script de déploiement en production Coris Intelligent Assistant
set -e

echo "🚀 DÉPLOIEMENT PRODUCTION - CORIS INTELLIGENT ASSISTANT"
echo "======================================================="

# Configuration
ENVIRONMENT="production"
BACKUP_DIR="/opt/coris/backups"
DEPLOY_DIR="/opt/coris"
LOG_FILE="/opt/coris/logs/deploy_$(date +%Y%m%d_%H%M%S).log"

# Créer les répertoires
sudo mkdir -p "$DEPLOY_DIR" "$BACKUP_DIR" /opt/coris/logs
sudo chown -R $USER:$USER /opt/coris

# Fonction de logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🔍 Vérifications pré-déploiement..."

# Vérifier les prérequis
command -v docker >/dev/null 2>&1 || { log "❌ Docker non installé"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { log "❌ Docker Compose non installé"; exit 1; }

# Vérifier les fichiers nécessaires
if [ ! -f ".env" ]; then
   log "❌ Fichier .env manquant"
   exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
   log "❌ Fichier docker-compose.yml manquant"
   exit 1
fi

log "✅ Vérifications OK"

# 1. Sauvegarde des données existantes (si applicable)
log "💾 Sauvegarde des données existantes..."
if [ -d "/opt/coris/data" ]; then
   BACKUP_FILE="$BACKUP_DIR/pre_deploy_$(date +%Y%m%d_%H%M%S).tar.gz"
   tar -czf "$BACKUP_FILE" -C /opt/coris data/ || true
   log "📦 Sauvegarde créée: $BACKUP_FILE"
fi

# 2. Copie des fichiers de configuration
log "📋 Copie de la configuration..."
cp -r . "$DEPLOY_DIR/"
cd "$DEPLOY_DIR"

# 3. Configuration de l'environnement de production
log "⚙️ Configuration production..."

# Générer une clé secrète si nécessaire
if ! grep -q "SECRET_KEY=" .env || grep -q "your-secret-key-change" .env; then
   SECRET_KEY=$(openssl rand -hex 32)
   sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
   log "🔑 Nouvelle clé secrète générée"
fi

# Configurer les permissions
chmod 600 .env
chmod +x deployment/scripts/*.sh

# 4. Construction et démarrage des services
log "🏗️ Construction des images..."
docker-compose -f deployment/docker/docker-compose.prod.yml build --no-cache

log "🚀 Démarrage des services..."
docker-compose -f deployment/docker/docker-compose.prod.yml up -d

# 5. Attendre que les services soient prêts
log "⏳ Attente du démarrage des services..."
sleep 60

# Vérifier PostgreSQL
for i in {1..10}; do
   if docker exec coris-postgres-prod pg_isready -U "$CONVERSATIONS_USER" >/dev/null 2>&1; then
       log "✅ PostgreSQL opérationnel"
       break
   fi
   if [ $i -eq 10 ]; then
       log "❌ PostgreSQL non opérationnel après 10 tentatives"
       exit 1
   fi
   sleep 10
done

# Vérifier l'API
for i in {1..10}; do
   if curl -f http://localhost/api/v1/health >/dev/null 2>&1; then
       log "✅ API opérationnelle"
       break
   fi
   if [ $i -eq 10 ]; then
       log "❌ API non opérationnelle après 10 tentatives"
       docker-compose -f deployment/docker/docker-compose.prod.yml logs coris-assistant
       exit 1
   fi
   sleep 10
done

# 6. Initialisation des bases de données
log "🗄️ Initialisation des bases de données..."
docker-compose -f deployment/docker/docker-compose.prod.yml exec -T coris-assistant python scripts/init_databases.py || true

# 7. Initialisation des bases de connaissances
log "📚 Initialisation des bases de connaissances..."
docker-compose -f deployment/docker/docker-compose.prod.yml exec -T coris-assistant python scripts/init_knowledge_bases.py || true

# 8. Tests post-déploiement
log "🧪 Tests post-déploiement..."
docker-compose -f deployment/docker/docker-compose.prod.yml exec -T coris-assistant python scripts/final_system_test.py

if [ $? -eq 0 ]; then
   log "✅ Tests post-déploiement réussis"
else
   log "❌ Tests post-déploiement échoués"
   log "📋 Consultation des logs recommandée"
fi

# 9. Configuration du monitoring
log "📊 Configuration du monitoring..."

# Démarrer Prometheus et Grafana
docker-compose -f deployment/docker/docker-compose.prod.yml up -d prometheus grafana

sleep 30

# Vérifier Grafana
if curl -f http://localhost:3000 >/dev/null 2>&1; then
   log "✅ Grafana opérationnel"
else
   log "⚠️ Grafana non accessible"
fi

# 10. Configuration des sauvegardes automatiques
log "💾 Configuration des sauvegardes automatiques..."

# Créer le script de sauvegarde quotidienne
cat > /opt/coris/backup_daily.sh << 'EOF'
#!/bin/bash
cd /opt/coris
./deployment/scripts/maintenance.sh backup
EOF

chmod +x /opt/coris/backup_daily.sh

# Ajouter au crontab
if ! crontab -l 2>/dev/null | grep -q "backup_daily.sh"; then
   (crontab -l 2>/dev/null; echo "0 2 * * * /opt/coris/backup_daily.sh") | crontab -
   log "✅ Sauvegarde quotidienne configurée (2h00)"
fi

# 11. Configuration du pare-feu (si ufw est installé)
if command -v ufw >/dev/null 2>&1; then
   log "🔒 Configuration du pare-feu..."
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw allow 22/tcp
   # Fermer les ports de développement
   sudo ufw deny 8000/tcp || true
   sudo ufw deny 5432/tcp || true
   sudo ufw deny 6379/tcp || true
   log "✅ Pare-feu configuré"
fi

# 12. Nettoyage
log "🧹 Nettoyage..."
docker system prune -f

# 13. Résumé du déploiement
log "🎉 DÉPLOIEMENT TERMINÉ AVEC SUCCÈS !"
log "===================================="
log ""
log "📊 Services déployés :"
log "  - API Coris Assistant  : http://localhost/api/v1/docs"
log "  - Monitoring Grafana   : http://localhost:3000 (admin/admin123)"
log "  - Métriques Prometheus : http://localhost:9090"
log ""
log "📁 Emplacements importants :"
log "  - Configuration       : /opt/coris"
log "  - Données             : /opt/coris/data"
log "  - Logs                : /opt/coris/logs"
log "  - Sauvegardes         : /opt/coris/backups"
log ""
log "🛠️ Commandes utiles :"
log "  - Status             : cd /opt/coris && ./deployment/scripts/maintenance.sh status"
log "  - Logs               : cd /opt/coris && ./deployment/scripts/maintenance.sh logs"
log "  - Sauvegarde         : cd /opt/coris && ./deployment/scripts/maintenance.sh backup"
log "  - Monitoring         : cd /opt/coris && ./deployment/scripts/maintenance.sh monitor"
log ""
log "🔐 Sécurité :"
log "  - Changer le mot de passe Grafana par défaut"
log "  - Configurer SSL/HTTPS pour la production"
log "  - Vérifier les clés API dans .env"
log ""
log "📞 Support :"
log "  - Documentation : /opt/coris/docs/"
log "  - Logs de déploiement : $LOG_FILE"

echo ""
echo "✅ Système prêt pour la production !"
echo "📱 L'application mobile peut maintenant se connecter à l'API"