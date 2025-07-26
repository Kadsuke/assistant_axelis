# src/tools/mcp_tools/knowledge_base.py
from core.knowledge_base.chroma_manager import MultiTenantChromaManager

chroma_manager = MultiTenantChromaManager()

@mcp_tool
async def search_knowledge_base(query: str, filiale_id: str, application: str, 
                               category: str = None, n_results: int = 5):
    """Recherche dans la base de connaissances spécifique à la filiale/app"""
    
    # Recherche dans la collection dédiée
    results = await chroma_manager.query_documents(
        application=application,
        filiale_id=filiale_id,
        query=query,
        n_results=n_results
    )
    
    # Filtrage par catégorie si spécifié
    if category:
        filtered_results = []
        for i, metadata in enumerate(results['metadatas'][0]):
            if metadata.get('category') == category:
                filtered_results.append({
                    'document': results['documents'][0][i],
                    'metadata': metadata,
                    'distance': results['distances'][0][i]
                })
        return filtered_results
    
    return results

@mcp_tool
async def get_knowledge_base_stats(filiale_id: str, application: str):
    """Statistiques de la base de connaissances"""
    return chroma_manager.get_collection_stats(application, filiale_id)