"""
Checklist de mise en production - Coris Intelligent Assistant
"""
import asyncio
import os
import sys
import subprocess
import json
import httpx
from pathlib import Path
from datetime import datetime
import yaml

class ProductionChecker:
    def __init__(self):
        self.checks = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def check(self, name: str, status: str, message: str = "", critical: bool = True):
        """Enregistre un résultat de vérification"""
        emoji = "✅" if status == "pass" else ("⚠️" if status == "warning" else "❌")
        level = "CRITICAL" if critical and status == "fail" else ("WARNING" if status == "warning" else "OK")
        
        self.checks.append({
            "name": name,
            "status": status,
            "message": message,
            "level": level,
            "emoji": emoji
        })
        
        if status == "pass":
            self.passed += 1
        elif status == "warning":
            self.warnings += 1
        else:
            self.failed += 1
        
        print(f"{emoji} {name}: {message or status.upper()}")
    
    async def check_environment_variables(self):
        """Vérification des variables d'environnement"""
        print("\n🔍 Vérification des variables d'environnement...")
        
        required_vars = [
            ("OPENAI_API_KEY", True),
            ("SECRET_KEY", True),
            ("DATAWAREHOUSE_HOST", True),
            ("RECLAMATIONS_HOST", True),
            ("CONVERSATIONS_HOST", False),
            ("CHROMADB_PERSIST_DIRECTORY", False)
        ]
        
        for var_name, critical in required_vars:
            value = os.getenv(var_name)
            if value and value != "your-secret-key-change-this":
                self.check(f"Variable {var_name}", "pass", "Configurée", critical)
            elif value == "your-secret-key-change-this":
                self.check(f"Variable {var_name}", "fail", "Valeur par défaut détectée", critical)
            else:
                self.check(f"Variable {var_name}", "fail", "Non configurée", critical)
    
    async def check_file_structure(self):
        """Vérification de la structure des fichiers"""
        print("\n📁 Vérification de la structure des fichiers...")
        
        critical_files = [
            "src/main.py",
            "src/core/packs/manager.py",
            "src/core/database/connections.py",
            "src/agents/config/agents.yaml",
            "src/agents/config/tasks.yaml",
            "docker-compose.yml",
            ".env"
        ]
        
        for file_path in critical_files:
            if Path(file_path).exists():
                self.check(f"Fichier {file_path}", "pass", "Présent")
            else:
                self.check(f"Fichier {file_path}", "fail", "Manquant", True)
    
    async def check_docker_environment(self):
        """Vérification de l'environnement Docker"""
        print("\n🐳 Vérification de l'environnement Docker...")
        
        try:
            # Vérifier Docker
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.check("Docker", "pass", f"Installé: {result.stdout.strip()}")
            else:
                self.check("Docker", "fail", "Non installé", True)
            
            # Vérifier Docker Compose
            result = subprocess.run(["docker-compose", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.check("Docker Compose", "pass", f"Installé: {result.stdout.strip()}")
            else:
                self.check("Docker Compose", "fail", "Non installé", True)
            
            # Vérifier que Docker fonctionne
            result = subprocess.run(["docker", "info"], capture_output=True, text=True)
            if result.returncode == 0:
                self.check("Docker Service", "pass", "Opérationnel")
            else:
                self.check("Docker Service", "fail", "Non opérationnel", True)
                
        except FileNotFoundError:
            self.check("Docker", "fail", "Non trouvé dans PATH", True)
    
    async def check_database_connections(self):
        """Vérification des connexions aux bases de données"""
        print("\n🗄️ Vérification des connexions aux bases de données...")
        
        # Test de connexion basic (sans vraiment se connecter)
        required_db_vars = [
            ("DATAWAREHOUSE_HOST", "DATAWAREHOUSE_USER", "DATAWAREHOUSE_PASSWORD"),
            ("RECLAMATIONS_HOST", "RECLAMATIONS_USER", "RECLAMATIONS_PASSWORD")
        ]
        
        for host_var, user_var, pass_var in required_db_vars:
            host = os.getenv(host_var)
            user = os.getenv(user_var)
            password = os.getenv(pass_var)
            
            if all([host, user, password]):
                self.check(f"Credentials {host_var}", "pass", "Configurées")
            else:
                missing = [var for var, val in [(host_var, host), (user_var, user), (pass_var, password)] if not val]
                self.check(f"Credentials {host_var}", "fail", f"Manquantes: {', '.join(missing)}", True)
    
    async def check_pack_configurations(self):
        """Vérification des configurations de packs"""
        print("\n📦 Vérification des configurations de packs...")
        
        try:
            # Vérifier base_packs.yaml
            base_packs_path = Path("src/core/packs/config/base_packs.yaml")
            if base_packs_path.exists():
                with open(base_packs_path) as f:
                    base_packs = yaml.safe_load(f)
                
                if "base_packs" in base_packs and base_packs["base_packs"]:
                    self.check("Base Packs Config", "pass", f"{len(base_packs['base_packs'])} packs définis")
                else:
                    self.check("Base Packs Config", "fail", "Configuration vide", True)
            else:
                self.check("Base Packs Config", "fail", "Fichier manquant", True)
            
            # Vérifier app_packs.yaml pour Coris Money
            app_packs_path = Path("src/applications/coris_money/config/app_packs.yaml")
            if app_packs_path.exists():
                with open(app_packs_path) as f:
                    app_packs = yaml.safe_load(f)
                
                if "coris_money_packs" in app_packs and app_packs["coris_money_packs"]:
                    self.check("Coris Money Packs", "pass", f"{len(app_packs['coris_money_packs'])} packs définis")
                else:
                    self.check("Coris Money Packs", "fail", "Configuration vide", True)
            else:
                self.check("Coris Money Packs", "fail", "Fichier manquant", True)
            
            # Vérifier qu'au moins une filiale est configurée
            filiales_dir = Path("src/applications/coris_money/config/filiales")
            if filiales_dir.exists():
                filiales = list(filiales_dir.glob("*.yaml"))
                if filiales:
                    self.check("Filiales Config", "pass", f"{len(filiales)} filiale(s) configurée(s)")
                else:
                    self.check("Filiales Config", "warning", "Aucune filiale configurée", False)
            else:
                self.check("Filiales Config", "fail", "Dossier filiales manquant", True)
                
        except Exception as e:
            self.check("Pack Configurations", "fail", f"Erreur de lecture: {e}", True)
    
    async def check_agents_configuration(self):
        """Vérification de la configuration des agents"""
        print("\n🤖 Vérification de la configuration des agents...")
        
        try:
            # Vérifier agents.yaml
            agents_path = Path("src/agents/config/agents.yaml")
            if agents_path.exists():
                self.check("Agents Config File", "pass", "Présent")
                # Note: La validation complète nécessiterait de charger CrewAI
            else:
                self.check("Agents Config File", "fail", "Manquant", True)
            
            # Vérifier tasks.yaml
            tasks_path = Path("src/agents/config/tasks.yaml")
            if tasks_path.exists():
                self.check("Tasks Config File", "pass", "Présent")
            else:
                self.check("Tasks Config File", "fail", "Manquant", True)
            
            # Vérifier les agents core
            core_agents_dir = Path("src/agents/core")
            if core_agents_dir.exists():
                core_files = list(core_agents_dir.glob("*.yaml"))
                if core_files:
                    self.check("Core Agents", "pass", f"{len(core_files)} fichier(s) d'agents core")
                else:
                    self.check("Core Agents", "warning", "Aucun agent core défini", False)
            
            # Vérifier les agents Coris Money
            coris_agents_dir = Path("src/agents/applications/coris_money")
            if coris_agents_dir.exists():
                coris_files = list(coris_agents_dir.glob("*.yaml"))
                if coris_files:
                    self.check("Coris Money Agents", "pass", f"{len(coris_files)} fichier(s) d'agents")
                else:
                    self.check("Coris Money Agents", "warning", "Aucun agent Coris Money défini", False)
                    
        except Exception as e:
            self.check("Agents Configuration", "fail", f"Erreur: {e}", True)
    
    async def check_security_configuration(self):
        """Vérification de la configuration de sécurité"""
        print("\n🔒 Vérification de la configuration de sécurité...")
        
        # Vérifier la clé secrète
        secret_key = os.getenv("SECRET_KEY")
        if secret_key and secret_key != "your-secret-key-change-this" and len(secret_key) >= 32:
            self.check("Secret Key", "pass", "Configurée et sécurisée")
        elif secret_key == "your-secret-key-change-this":
            self.check("Secret Key", "fail", "Valeur par défaut - CRITIQUE", True)
        else:
            self.check("Secret Key", "fail", "Manquante ou trop courte", True)
        
        # Vérifier les clés API
        api_keys = os.getenv("API_KEYS")
        if api_keys and "test-key" not in api_keys:
            self.check("API Keys", "pass", "Configurées pour production")
        elif "test-key" in (api_keys or ""):
            self.check("API Keys", "warning", "Clé de test détectée", False)
        else:
            self.check("API Keys", "fail", "Non configurées", True)
        
        # Vérifier les permissions des fichiers
        env_file = Path(".env")
        if env_file.exists():
            stat = env_file.stat()
            permissions = oct(stat.st_mode)[-3:]
            if permissions == "600":
                self.check("Permissions .env", "pass", "Sécurisées (600)")
            else:
                self.check("Permissions .env", "warning", f"Permissions: {permissions} (recommandé: 600)", False)
    
    async def check_monitoring_setup(self):
        """Vérification de la configuration du monitoring"""
        print("\n📊 Vérification du monitoring...")
        
        # Vérifier Prometheus config
        prometheus_config = Path("configs/prometheus/prometheus.yml")
        if prometheus_config.exists():
            self.check("Prometheus Config", "pass", "Configuré")
        else:
            self.check("Prometheus Config", "warning", "Configuration manquante", False)
        
        # Vérifier Grafana config
        grafana_config = Path("configs/grafana/datasources.yml")
        if grafana_config.exists():
            self.check("Grafana Config", "pass", "Configuré")
        else:
            self.check("Grafana Config", "warning", "Configuration manquante", False)
        
        # Vérifier la configuration de logs
        log_dir = Path("data/logs")
        if log_dir.exists():
            self.check("Log Directory", "pass", "Configuré")
        else:
            self.check("Log Directory", "warning", "Répertoire de logs manquant", False)
    
    async def check_production_readiness(self):
        """Vérifications spécifiques à la production"""
        print("\n🚀 Vérification de la préparation production...")
        
        # Vérifier l'environnement
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            self.check("Environment", "pass", "Production")
        else:
            self.check("Environment", "warning", f"Configuré en: {environment}", False)
        
        # Vérifier le niveau de log
        log_level = os.getenv("LOG_LEVEL", "INFO")
        if log_level in ["WARNING", "ERROR"]:
            self.check("Log Level", "pass", f"Production ({log_level})")
        else:
            self.check("Log Level", "warning", f"Développement ({log_level})", False)
        
        # Vérifier la configuration SSL
        ssl_cert = Path("/opt/coris/ssl/cert.pem")
        if ssl_cert.exists():
            self.check("SSL Certificate", "pass", "Configuré")
        else:
            self.check("SSL Certificate", "warning", "Non configuré", False)
    
    async def test_api_endpoints(self):
        """Test des endpoints critiques"""
        print("\n🌐 Test des endpoints API...")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Test health endpoint
                try:
                    response = await client.get("http://localhost:8000/api/v1/health")
                    if response.status_code == 200:
                        self.check("Health Endpoint", "pass", "Opérationnel")
                    else:
                        self.check("Health Endpoint", "fail", f"HTTP {response.status_code}", True)
                except Exception as e:
                    self.check("Health Endpoint", "fail", f"Inaccessible: {e}", True)
                
                # Test avec Nginx si configuré
                try:
                    response = await client.get("http://localhost/api/v1/health")
                    if response.status_code == 200:
                        self.check("Nginx Proxy", "pass", "Opérationnel")
                    else:
                        self.check("Nginx Proxy", "warning", f"HTTP {response.status_code}", False)
                except Exception:
                    self.check("Nginx Proxy", "warning", "Non configuré ou inaccessible", False)
                    
        except Exception as e:
            self.check("API Testing", "fail", f"Erreur générale: {e}", True)
    
    async def generate_report(self):
        """Génère le rapport final"""
        print("\n" + "="*60)
        print("📋 RAPPORT DE VÉRIFICATION PRODUCTION")
        print("="*60)
        
        # Résumé
        total_checks = len(self.checks)
        print(f"\n📊 Résumé:")
        print(f"   ✅ Réussis: {self.passed}/{total_checks}")
        print(f"   ⚠️  Avertissements: {self.warnings}/{total_checks}")
        print(f"   ❌ Échecs: {self.failed}/{total_checks}")
        
        # Échecs critiques
        critical_failures = [c for c in self.checks if c["level"] == "CRITICAL"]
        if critical_failures:
            print(f"\n🚨 ÉCHECS CRITIQUES ({len(critical_failures)}):")
            for check in critical_failures:
                print(f"   {check['emoji']} {check['name']}: {check['message']}")
        
        # Avertissements
        warnings = [c for c in self.checks if c["level"] == "WARNING"]
        if warnings:
            print(f"\n⚠️  AVERTISSEMENTS ({len(warnings)}):")
            for check in warnings:
                print(f"   {check['emoji']} {check['name']}: {check['message']}")
        
        # Déterminer l'état global
        if critical_failures:
            status = "❌ NON PRÊT POUR LA PRODUCTION"
            print(f"\n{status}")
            print("🔧 Actions requises:")
            print("   1. Corriger tous les échecs critiques")
            print("   2. Relancer cette vérification")
            print("   3. Effectuer des tests complets")
            return False
        elif warnings:
            status = "⚠️  PRÊT AVEC RÉSERVES"
            print(f"\n{status}")
            print("💡 Recommandations:")
            print("   1. Corriger les avertissements si possible")
            print("   2. Documenter les exceptions acceptées")
            print("   3. Planifier les améliorations")
            return True
        else:
            status = "✅ PRÊT POUR LA PRODUCTION"
            print(f"\n{status}")
            print("🎉 Félicitations ! Le système est prêt pour la production.")
            return True
    
    async def run_all_checks(self):
        """Exécute toutes les vérifications"""
        print("🔍 CHECKLIST DE MISE EN PRODUCTION")
        print("=" * 60)
        print(f"🕐 Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await self.check_environment_variables()
        await self.check_file_structure()
        await self.check_docker_environment()
        await self.check_database_connections()
        await self.check_pack_configurations()
        await self.check_agents_configuration()
        await self.check_security_configuration()
        await self.check_monitoring_setup()
        await self.check_production_readiness()
        await self.test_api_endpoints()
        
        return await self.generate_report()

async def main():
    """Fonction principale"""
    checker = ProductionChecker()
    
    try:
        is_ready = await checker.run_all_checks()
        
        # Sauvegarder le rapport
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_checks": len(checker.checks),
            "passed": checker.passed,
            "warnings": checker.warnings, 
            "failed": checker.failed,
            "production_ready": is_ready,
            "checks": checker.checks
        }
        
        report_file = Path("production_checklist_report.json")
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📄 Rapport sauvegardé: {report_file}")
        
        # Code de sortie
        if is_ready and checker.failed == 0:
            sys.exit(0)  # Succès complet
        elif is_ready:
            sys.exit(1)  # Prêt avec avertissements
        else:
            sys.exit(2)  # Non prêt
            
    except KeyboardInterrupt:
        print("\n🛑 Vérification interrompue par l'utilisateur")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Erreur lors de la vérification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())