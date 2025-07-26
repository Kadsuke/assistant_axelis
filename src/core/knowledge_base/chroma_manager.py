"""
Gestionnaire ChromaDB Multi-Tenant
"""
import os
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import Dict, List, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()

class MultiTenantChromaManager:
    def __init__(self):
        self.client = self._initialize_client()
        self._collections = {}
        self.embedding_function = self._get_embedding_function()
    
    def _initialize_client(self):
        """Initialise le client ChromaDB"""
        persist_dir = os.getenv("CHROMADB_PERSIST_DIRECTORY", "./data/chroma_data")
        
        try:
            client = chromadb.PersistentClient(
                path=persist_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"ChromaDB client initialized", persist_dir=persist_dir)
            return client
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client", error=str(e))
            raise
    
    def _get_embedding_function(self):
        """Fonction d'embedding OpenAI"""
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="text-embedding-3-small"
        )
    
    def get_collection_name(self, application: str, filiale_id: str) -> str:
        """Génère le nom de collection unique"""
        return f"{application}_{filiale_id}"
    
    def get_or_create_collection(self, application: str, filiale_id: str):
        """Récupère ou crée la collection"""
        collection_name = self.get_collection_name(application, filiale_id)
        
        if collection_name not in self._collections:
            try:
                collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"Retrieved existing collection: {collection_name}")
            except Exception:
                collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function,
                    metadata={
                        "application": application,
                        "filiale_id": filiale_id,
                        "created_at": datetime.now().isoformat()
                    }
                )
                logger.info(f"Created new collection: {collection_name}")
            
            self._collections[collection_name] = collection
        
        return self._collections[collection_name]
    
    async def add_documents(self, application: str, filiale_id: str, 
                           documents: List[str], metadatas: List[Dict], ids: List[str]):
        """Ajoute des documents à la collection"""
        collection = self.get_or_create_collection(application, filiale_id)
        
        enhanced_metadatas = []
        for metadata in metadatas:
            enhanced_metadata = {
                **metadata,
                "application": application,
                "filiale_id": filiale_id,
                "added_at": datetime.now().isoformat()
            }
            enhanced_metadatas.append(enhanced_metadata)
        
        collection.add(
            documents=documents,
            metadatas=enhanced_metadatas,
            ids=ids
        )
        
        logger.info(f"Added {len(documents)} documents to {application}_{filiale_id}")
    
    async def query_documents(self, application: str, filiale_id: str, 
                             query: str, n_results: int = 5):
        """Recherche dans la collection spécifique"""
        collection = self.get_or_create_collection(application, filiale_id)
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        return results
    
    def get_collection_stats(self, application: str, filiale_id: str) -> Dict:
        """Statistiques de la collection"""
        collection = self.get_or_create_collection(application, filiale_id)
        return {
            "name": collection.name,
            "count": collection.count(),
            "metadata": collection.metadata
        }