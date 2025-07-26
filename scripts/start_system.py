"""
Script de démarrage complet du système Coris Intelligent Assistant
"""
import asyncio
import os
import sys
from pathlib import Path
import subprocess
from dotenv import load_dotenv

# Ajouter src au path
sys.path.append(str(Path(__file__).parent.parent / "src"))

load_dotenv()

async def check_dependencies():
    """Vérifie que toutes les dépendances sont installées"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        "fastapi", "uvicorn", "crewai", "openai", 
        "chromadb", "sqlalchemy", "asyncpg"
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - Installing...")
            subprocess.run([sys.executable, "-m", "pip", "install", package])

async def initialize_databases():
    """Initialise les bases de données"""
    print("\n🗄️ Initializing databases...")
    
    try:
        # Initialiser la base conversations
        print("   📋 Setting up conversations database...")
        result = subprocess.run([
            sys.executable, "scripts/init_databases.py"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Conversations database ready")
        else:
            print(f"   ⚠️ Database setup: {result.stderr}")
    
    except Exception as e:
        print(f"   ❌ Database initialization error: {e}")

async def initialize_knowledge_bases():
    """Initialise les bases de connaissances"""
    print("\n📚 Initializing knowledge bases...")
    
    try:
        print("   🔍 Setting up ChromaDB collections...")
        result = subprocess.run([
            sys.executable, "scripts/init_knowledge_bases.py"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Knowledge bases ready")
        else:
            print(f"   ⚠️ Knowledge base setup: {result.stderr}")
    
    except Exception as e:
        print(f"   ❌ Knowledge base initialization error: {e}")

async def test_system_components():
    """Teste tous les composants du système"""
    print("\n🧪 Testing system components...")
    
    try:
        result = subprocess.run([
            sys.executable, "scripts/test_complete_system.py"
        ], capture_output=True, text=True)
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("   ✅ All components tested successfully")
            return True
        else:
            print(f"   ❌ Component tests failed: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"   ❌ Testing error: {e}")
        return False

async def start_api_server():
    """Démarre le serveur API"""
    print("\n🚀 Starting API server...")
    
    try:
        api_host = os.getenv("API_HOST", "0.0.0.0")
        api_port = os.getenv("API_PORT", "8000")
        
        print(f"   🌐 Starting server on http://{api_host}:{api_port}")
        print("   📱 Mobile app can connect to this endpoint")
        print("   📋 API documentation: http://localhost:8000/docs")
        
        # Démarrer avec uvicorn
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "applications.coris_money.apis.chat:app",
            "--host", api_host,
            "--port", api_port,
            "--reload"
        ])
    
    except KeyboardInterrupt:
        print("\n   🛑 Server stopped by user")
    except Exception as e:
        print(f"   ❌ Server error: {e}")

async def main():
    """Fonction principale de démarrage"""
    print("🎯 Coris Intelligent Assistant - System Startup")
    print("=" * 60)
    
    # 1. Vérifier les dépendances
    await check_dependencies()
    
    # 2. Vérifier la configuration
    print("\n⚙️ Checking configuration...")
    required_env_vars = [
        "OPENAI_API_KEY",
        "CONVERSATIONS_HOST",
        "CHROMADB_PERSIST_DIRECTORY"
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"   ❌ Missing environment variables: {', '.join(missing_vars)}")
        print("   📝 Please configure your .env file")
        return
    else:
        print("   ✅ Configuration validated")
    
    # 3. Initialiser les bases de données
    await initialize_databases()
    
    # 4. Initialiser les bases de connaissances
    await initialize_knowledge_bases()
    
    # 5. Tester les composants
    tests_passed = await test_system_components()
    
    if not tests_passed:
        print("\n❌ System tests failed. Please check configuration.")
        return
    
    # 6. Démarrer le serveur API
    print("\n" + "=" * 60)
    print("🎉 System ready! Starting API server...")
    print("=" * 60)
    
    await start_api_server()

if __name__ == "__main__":
    asyncio.run(main())