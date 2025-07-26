#!/bin/bash

# Script de maintenance Coris Intelligent Assistant
set -e

COMMAND=${1:-help}
BACKUP_DIR="/opt/coris/backups"
LOG_DIR="/opt/coris/logs"

case $COMMAND in
    "backup")
        echo "💾 Sauvegarde complète du système..."
        BACKUP_FILE="$BACKUP_DIR/coris_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
        
        # Créer le répertoire de sauvegarde
        mkdir -p "$BACKUP_DIR"
        
        # Sauvegarde base de données
        echo "   📄 Sauvegarde base conversations..."
        docker exec coris-postgres-prod pg_dump -U $CONVERSATIONS_USER coris_conversations > "$BACKUP_DIR/conversations_$(date +%Y%m%d).sql"
        
        # Sauvegarde ChromaDB
        echo "   📚 Sauvegarde ChromaDB..."
        tar -czf "$BACKUP_DIR/chroma_$(date +%Y%m%d).tar.gz" -C /opt/coris/data chroma_data
        
        # Sauvegarde configuration
        echo "   ⚙️ Sauvegarde configuration..."
        tar -czf "$BACKUP_FILE" \
            /opt/coris/data \
            /opt/coris/knowledge_bases \
            "$BACKUP_DIR/conversations_$(date +%Y%m%d).sql" \
            "$BACKUP_DIR/chroma_$(date +%Y%m%d).tar.gz"
        
        echo "✅ Sauvegarde terminée: $BACKUP_FILE"
        
        # Nettoyage des anciennes sauvegardes (garder 7 jours)
        find "$BACKUP_DIR" -name "coris_backup_*.tar.gz" -mtime +7 -delete
        ;;
        
    "restore")
        BACKUP_FILE=${2}
        if [ -z "$BACKUP_FILE" ]; then
            echo "❌ Usage: $0 restore <backup_file>"
            exit 1
        fi
        
        echo "🔄 Restauration depuis: $BACKUP_FILE"
        
        # Arrêter les services
        docker-compose -f deployment/docker/docker-compose.prod.yml down
        
        # Restaurer les données
        tar -xzf "$BACKUP_FILE" -C /
        
        # Redémarrer les services
        docker-compose -f deployment/docker/docker-compose.prod.yml up -d
        
        echo "✅ Restauration terminée"
        ;;
        
    "logs")
        SERVICE=${2:-coris-assistant}
        echo "📋 Logs du service: $SERVICE"
        docker-compose logs -f --tail=100 "$SERVICE"
        ;;
        
    "status")
        echo "📊 Statut des services Coris Assistant"
        echo "======================================"
        
        # Statut Docker
        docker-compose ps
        
        # Vérification API
        if curl -f http://localhost/api/v1/health > /dev/null 2>&1; then
            echo "✅ API: Opérationnelle"
        else
            echo "❌ API: Hors service"
        fi
        
        # Vérification base de données
        if docker exec coris-postgres-prod pg_isready -U $CONVERSATIONS_USER > /dev/null 2>&1; then
            echo "✅ Base de données: Opérationnelle"
        else
            echo "❌ Base de données: Hors service"
        fi
        
        # Métriques système
        echo ""
        echo "📈 Métriques (dernières 24h):"
        curl -s http://localhost/api/v1/metrics | jq '.conversations.total_24h' | xargs echo "   Conversations:"
        curl -s http://localhost/api/v1/metrics | jq '.escalations.total_24h' | xargs echo "   Escalades:"
        ;;
        
    "update")
        echo "🔄 Mise à jour du système..."
        
        # Sauvegarde avant mise à jour
        $0 backup
        
        # Pull des nouvelles images
        docker-compose -f deployment/docker/docker-compose.prod.yml pull
        
        # Rebuild et redémarrage
        docker-compose -f deployment/docker/docker-compose.prod.yml up -d --build
        
        # Vérification post-mise à jour
        sleep 30
        $0 status
        
        echo "✅ Mise à jour terminée"
        ;;
        
    "cleanup")
        echo "🧹 Nettoyage du système..."
        
        # Nettoyage Docker
        docker system prune -f
        docker volume prune -f
        
        # Nettoyage logs (garder 30 jours)
        find "$LOG_DIR" -name "*.log" -mtime +30 -delete
        
        # Nettoyage base conversations (supprimer conversations > 90 jours)
        docker exec coris-postgres-prod psql -U $CONVERSATIONS_USER -d coris_conversations -c "
            DELETE FROM messages WHERE conversation_id IN (
                SELECT id FROM conversations WHERE created_at < NOW() - INTERVAL '90 days'
            );
            DELETE FROM conversations WHERE created_at < NOW() - INTERVAL '90 days';
        "
        
        echo "✅ Nettoyage terminé"
        ;;
        
    "monitor")
        echo "📊 Monitoring en temps réel..."
        echo "Ctrl+C pour arrêter"
        
        while true; do
            clear
            echo "=== Coris Assistant Monitoring - $(date) ==="
            echo ""
            
            # Statut des conteneurs
            echo "🐳 Conteneurs:"
            docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
            
            echo ""
            echo "📈 Métriques:"
            
            # CPU et Mémoire
            docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -4
            
            echo ""
            echo "💬 Conversations actives:"
            curl -s http://localhost/api/v1/metrics | jq '.conversations.total_24h' | xargs echo "   Dernières 24h:"
            
            echo ""
            echo "⚡ Temps de réponse moyen:"
            curl -s http://localhost/api/v1/metrics | jq '.performance.avg_tokens_per_message' | xargs echo "   Tokens/message:"
            
            sleep 10
        done
        ;;
        
    "security")
        echo "🔒 Vérification sécurité..."
        
        # Vérifier les mots de passe par défaut
        if grep -q "admin123" /opt/coris/configs/grafana/datasources.yml; then
            echo "⚠️ Mot de passe Grafana par défaut détecté"
        fi
        
        # Vérifier les permissions des fichiers
        if [ "$(stat -c %a /opt/coris/data)" != "750" ]; then
            echo "⚠️ Permissions du répertoire data incorrectes"
            chmod 750 /opt/coris/data
        fi
        
        # Vérifier les certificats SSL
        if [ ! -f "/opt/coris/ssl/cert.pem" ]; then
            echo "⚠️ Certificat SSL manquant"
        fi
        
        echo "✅ Vérification sécurité terminée"
        ;;
        
    "help"|*)
        echo "🛠️ Script de maintenance Coris Intelligent Assistant"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commandes disponibles:"
        echo "  backup                 - Sauvegarde complète du système"
        echo "  restore <file>         - Restauration depuis une sauvegarde"
        echo "  logs [service]         - Affichage des logs"
        echo "  status                 - Statut des services"
        echo "  update                 - Mise à jour du système"
        echo "  cleanup                - Nettoyage des données anciennes"
        echo "  monitor                - Monitoring en temps réel"
        echo "  security               - Vérification sécurité"
        echo "  help                   - Affichage de cette aide"
        echo ""
        echo "Exemples:"
        echo "  $0 backup"
        echo "  $0 logs coris-assistant"
        echo "  $0 restore /opt/coris/backups/coris_backup_20241201_120000.tar.gz"
        ;;
esac