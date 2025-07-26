"""
Point d'entrée alternatif simple
"""
import asyncio
import uvicorn
from applications.coris_money.apis.chat import app

async def start_simple():
    """Démarrage simple pour développement"""
    print("🚀 Starting Coris Intelligent Assistant (Simple Mode)")
    
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )
    
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(start_simple())