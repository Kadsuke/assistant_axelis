"""
Script d'initialisation des bases de connaissances ChromaDB
"""
import asyncio
import os
from pathlib import Path
import sys

# Ajouter src au path pour les imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.knowledge_base.chroma_manager import MultiTenantChromaManager
from dotenv import load_dotenv

load_dotenv()

async def init_sample_knowledge_base():
    """Initialise une base de connaissances de test"""
    
    chroma_manager = MultiTenantChromaManager()
    
    # Données de test pour Coris CI
    sample_documents = [
        "Coris Money permet d'effectuer des transferts d'argent rapides et sécurisés.",
        "Les frais de transfert Coris Money varient selon le montant et la destination.",
        "Pour créer une réclamation, contactez le service client au +225 XX XX XX XX.",
        "Le solde de votre compte Coris Money est consultable 24h/24 via l'application.",
        "Les transferts internationaux avec Coris Money sont disponibles vers 15 pays."
    ]
    
    sample_metadatas = [
        {"category": "produits_services", "type": "info_generale"},
        {"category": "tarification", "type": "frais"},
        {"category": "support_technique", "type": "reclamation"},
        {"category": "faq_general", "type": "consultation"},
        {"category": "produits_services", "type": "international"}
    ]
    
    sample_ids = [f"doc_{i}" for i in range(len(sample_documents))]
    
    # Ajouter à ChromaDB pour Coris CI
    await chroma_manager.add_documents(
        application="coris_money",
        filiale_id="coris_ci",
        documents=sample_documents,
        metadatas=sample_metadatas,
        ids=sample_ids
    )
    
    print("✅ Sample knowledge base initialized for coris_money_coris_ci")
    
    # Test de recherche
    results = await chroma_manager.query_documents(
        application="coris_money",
        filiale_id="coris_ci",
        query="comment faire un transfert d'argent",
        n_results=2
    )
    
    print(f"🔍 Test search results: {len(results['documents'][0])} documents found")
    for doc in results['documents'][0]:
        print(f"  - {doc[:100]}...")

if __name__ == "__main__":
    asyncio.run(init_sample_knowledge_base())