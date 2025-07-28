"""
Gestionnaire d'embeddings pour la base de connaissances
Supporte OpenAI et des alternatives locales
"""
import os
import numpy as np
from typing import List, Optional, Dict, Any
import structlog
from abc import ABC, abstractmethod

logger = structlog.get_logger()

class EmbeddingProvider(ABC):
    """Interface pour les fournisseurs d'embeddings"""
    
    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Génère des embeddings pour une liste de documents"""
        pass
    
    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Génère un embedding pour une requête"""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Retourne la dimension des embeddings"""
        pass

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Fournisseur d'embeddings OpenAI"""
    
    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.dimension = 1536 if "3-small" in model else 1024
        
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            logger.info(f"OpenAI embedding provider initialized with model: {model}")
        except ImportError:
            raise ImportError("openai package required for OpenAI embeddings")
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Génère des embeddings pour des documents"""
        if not texts:
            return []
        
        try:
            # OpenAI permet jusqu'à 2048 textes par batch
            batch_size = 100
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            
            logger.debug(f"Generated embeddings for {len(texts)} documents")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate document embeddings: {e}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """Génère un embedding pour une requête"""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=[text]
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Generated query embedding for text: {text[:50]}...")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise
    
    def get_dimension(self) -> int:
        return self.dimension

class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """Fournisseur d'embeddings Hugging Face (local)"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"HuggingFace embedding provider initialized with model: {model_name}")
        except ImportError:
            raise ImportError("sentence-transformers package required for HuggingFace embeddings")
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Génère des embeddings pour des documents"""
        if not texts:
            return []
        
        try:
            # SentenceTransformers est synchrone
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Failed to generate document embeddings: {e}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """Génère un embedding pour une requête"""
        try:
            embedding = self.model.encode([text], convert_to_numpy=True)
            return embedding[0].tolist()
            
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise
    
    def get_dimension(self) -> int:
        return self.dimension

class FallbackEmbeddingProvider(EmbeddingProvider):
    """Fournisseur d'embeddings de fallback (embeddings aléatoires)"""
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        logger.warning("Using fallback embedding provider - embeddings will be random!")
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Génère des embeddings aléatoires pour des documents"""
        return [self._random_embedding() for _ in texts]
    
    async def embed_query(self, text: str) -> List[float]:
        """Génère un embedding aléatoire pour une requête"""
        return self._random_embedding()
    
    def _random_embedding(self) -> List[float]:
        """Génère un embedding aléatoire normalisé"""
        embedding = np.random.normal(0, 1, self.dimension)
        # Normaliser le vecteur
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding.tolist()
    
    def get_dimension(self) -> int:
        return self.dimension

class EmbeddingManager:
    """Gestionnaire principal des embeddings"""
    
    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self.provider = provider or self._get_default_provider()
        logger.info(f"EmbeddingManager initialized with {type(self.provider).__name__}")
    
    def _get_default_provider(self) -> EmbeddingProvider:
        """Sélectionne le meilleur fournisseur disponible"""
        
        # Essayer OpenAI en premier
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and openai_key.startswith("sk-") and len(openai_key) > 20:
            try:
                return OpenAIEmbeddingProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI embeddings: {e}")
        
        # Essayer Hugging Face local
        try:
            return HuggingFaceEmbeddingProvider()
        except Exception as e:
            logger.warning(f"Failed to initialize HuggingFace embeddings: {e}")
        
        # Fallback vers embeddings aléatoires
        logger.warning("Using fallback embeddings - search quality will be limited")
        return FallbackEmbeddingProvider()
    
    async def embed_documents(self, texts: List[str], metadata: Optional[List[Dict]] = None) -> List[List[float]]:
        """Génère des embeddings pour des documents avec métadonnées optionnelles"""
        
        if not texts:
            return []
        
        # Préprocesser les textes si nécessaire
        processed_texts = [self._preprocess_text(text) for text in texts]
        
        # Générer les embeddings
        embeddings = await self.provider.embed_documents(processed_texts)
        
        logger.info(f"Generated embeddings for {len(texts)} documents")
        return embeddings
    
    async def embed_query(self, query: str) -> List[float]:
        """Génère un embedding pour une requête de recherche"""
        
        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        # Préprocesser la requête
        processed_query = self._preprocess_text(query)
        
        # Générer l'embedding
        embedding = await self.provider.embed_query(processed_query)
        
        logger.debug(f"Generated query embedding for: {query[:50]}...")
        return embedding
    
    def _preprocess_text(self, text: str) -> str:
        """Préprocesse le texte avant génération d'embedding"""
        
        # Nettoyage basique
        text = text.strip()
        
        # Limiter la longueur (la plupart des modèles ont des limites)
        max_length = 8000  # Caractères
        if len(text) > max_length:
            text = text[:max_length] + "..."
            logger.debug(f"Text truncated to {max_length} characters")
        
        return text
    
    def get_dimension(self) -> int:
        """Retourne la dimension des embeddings"""
        return self.provider.get_dimension()
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Retourne des informations sur le fournisseur actuel"""
        return {
            "provider_type": type(self.provider).__name__,
            "dimension": self.get_dimension(),
            "model": getattr(self.provider, 'model', 'unknown'),
            "model_name": getattr(self.provider, 'model_name', 'unknown')
        }

# Instance globale
embedding_manager = EmbeddingManager()

# Fonctions utilitaires
async def embed_documents(texts: List[str], metadata: Optional[List[Dict]] = None) -> List[List[float]]:
    """Fonction utilitaire pour générer des embeddings de documents"""
    return await embedding_manager.embed_documents(texts, metadata)

async def embed_query(query: str) -> List[float]:
    """Fonction utilitaire pour générer un embedding de requête"""
    return await embedding_manager.embed_query(query)

def get_embedding_dimension() -> int:
    """Fonction utilitaire pour obtenir la dimension des embeddings"""
    return embedding_manager.get_dimension()

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calcule la similarité cosinus entre deux vecteurs"""
    
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    
    # Calcul de la similarité cosinus
    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    return float(similarity)

def euclidean_distance(vec1: List[float], vec2: List[float]) -> float:
    """Calcule la distance euclidienne entre deux vecteurs"""
    
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    
    distance = np.linalg.norm(vec1_np - vec2_np)
    return float(distance)