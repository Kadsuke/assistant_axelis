#!/usr/bin/env python3
"""
Script pour charger votre base de connaissances existante
"""
import asyncio
import sys
import os
from pathlib import Path

# Correction encodage Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ajouter src au path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.knowledge_base.chroma_manager import MultiTenantChromaManager
from core.knowledge_base.document_processor import DocumentProcessor
from dotenv import load_dotenv

load_dotenv()

class KnowledgeBaseLoader:
    def __init__(self):
        self.chroma_manager = MultiTenantChromaManager()
        self.doc_processor = DocumentProcessor()
        
        # Mapping des noms de fichiers vers catégories
        self.file_categories = {
            'faq.md': 'faq_general',
            'produits.md': 'produits_services',
            'reglementation.md': 'regulations',
            'procedures.md': 'procedures_bancaires',
            'tarifs.md': 'tarification',
            'contact.md': 'support_technique',
            'services.md': 'produits_services'
        }
    
    async def load_all_filiales(self, knowledge_base_path: str = "./knowledge_base"):
        """Charge toutes les filiales depuis votre structure existante"""
        
        kb_path = Path(knowledge_base_path)
        if not kb_path.exists():
            print(f"[ERROR] Dossier knowledge_base non trouvé: {knowledge_base_path}")
            return False
        
        coris_money_path = kb_path / "coris_money"
        if not coris_money_path.exists():
            print(f"[ERROR] Dossier coris_money non trouvé: {coris_money_path}")
            return False
        
        print(f"[INFO] Chargement depuis: {coris_money_path}")
        
        # Scanner toutes les filiales
        filiales_found = []
        for item in coris_money_path.iterdir():
            if item.is_dir() and item.name.startswith('coris_'):
                filiales_found.append(item.name)
        
        if not filiales_found:
            print("[ERROR] Aucune filiale trouvée (dossiers commençant par 'coris_')")
            return False
        
        print(f"[INFO] Filiales trouvées: {', '.join(filiales_found)}")
        
        total_documents = 0
        
        for filiale_id in filiales_found:
            print(f"\n{'='*50}")
            print(f"TRAITEMENT FILIALE: {filiale_id.upper()}")
            print(f"{'='*50}")
            
            filiale_path = coris_money_path / filiale_id
            documents_added = await self.load_filiale(filiale_id, filiale_path)
            total_documents += documents_added
            
            print(f"[OK] {filiale_id}: {documents_added} documents ajoutés")
        
        print(f"\n[SUCCESS] TOTAL: {total_documents} documents chargés pour toutes les filiales")
        return True
    
    async def load_filiale(self, filiale_id: str, filiale_path: Path):
        """Charge tous les documents d'une filiale"""
        
        if not filiale_path.exists():
            print(f"[ERROR] Dossier filiale non trouvé: {filiale_path}")
            return 0
        
        # Trouver tous les fichiers markdown
        md_files = list(filiale_path.glob("*.md"))
        
        if not md_files:
            print(f"[WARNING] Aucun fichier .md trouvé dans {filiale_path}")
            return 0
        
        print(f"[INFO] Fichiers trouvés: {[f.name for f in md_files]}")
        
        total_chunks = 0
        
        for md_file in md_files:
            print(f"\n[PROCESSING] {md_file.name}...")
            
            try:
                # Déterminer la catégorie
                category = self.file_categories.get(md_file.name, 'general')
                
                # Traiter le fichier
                documents = await self.doc_processor.process_file(
                    str(md_file),
                    filiale_id=filiale_id,
                    application="coris_money",
                    category=category,
                    custom_metadata={
                        "filiale": filiale_id,
                        "source_file": md_file.name,
                        "load_date": "2024-01-15"
                    }
                )
                
                if documents:
                    # Extraire les données pour ChromaDB
                    doc_contents = [doc["content"] for doc in documents]
                    doc_metadatas = [doc["metadata"] for doc in documents]
                    doc_ids = [doc["id"] for doc in documents]
                    
                    # Ajouter à ChromaDB
                    await self.chroma_manager.add_documents(
                        application="coris_money",
                        filiale_id=filiale_id,
                        documents=doc_contents,
                        metadatas=doc_metadatas,
                        ids=doc_ids
                    )
                    
                    total_chunks += len(documents)
                    print(f"   [OK] {len(documents)} chunks ajoutés")
                    
                    # Afficher un échantillon du contenu
                    if documents:
                        sample_content = documents[0]["content"][:100] + "..."
                        print(f"   [SAMPLE] {sample_content}")
                else:
                    print(f"   [WARNING] Aucun contenu extrait de {md_file.name}")
                    
            except Exception as e:
                print(f"   [ERROR] Erreur traitement {md_file.name}: {e}")
        
        return total_chunks
    
    async def load_single_filiale(self, filiale_id: str, knowledge_base_path: str = "./knowledge_base"):
        """Charge une seule filiale"""
        
        filiale_path = Path(knowledge_base_path) / "coris_money" / filiale_id
        
        if not filiale_path.exists():
            print(f"[ERROR] Dossier filiale non trouvé: {filiale_path}")
            return False
        
        print(f"[INFO] Chargement filiale: {filiale_id}")
        documents_added = await self.load_filiale(filiale_id, filiale_path)
        
        if documents_added > 0:
            print(f"[SUCCESS] {documents_added} documents ajoutés pour {filiale_id}")
            return True
        else:
            print(f"[WARNING] Aucun document ajouté pour {filiale_id}")
            return False
    
    async def verify_loading(self, filiale_id: str):
        """Vérifie que les documents ont été chargés"""
        
        print(f"\n[VERIFICATION] {filiale_id}...")
        
        try:
            # Test de recherche
            results = await self.chroma_manager.query_documents(
                application="coris_money",
                filiale_id=filiale_id,
                query="coris money transfert",
                n_results=3
            )
            
            if results and results.get('documents') and results['documents'][0]:
                documents = results['documents'][0]
                print(f"   [OK] Recherche test: {len(documents)} résultats trouvés")
                
                for i, doc in enumerate(documents[:2]):
                    print(f"   [RESULT {i+1}] {doc[:80]}...")
                
                return True
            else:
                print(f"   [WARNING] Aucun résultat trouvé lors du test de recherche")
                return False
                
        except Exception as e:
            print(f"   [ERROR] Erreur vérification: {e}")
            return False
    
    async def show_stats(self, filiale_id: str = None):
        """Affiche les statistiques de chargement"""
        
        if filiale_id:
            # Stats pour une filiale
            stats = self.chroma_manager.get_collection_stats("coris_money", filiale_id)
            print(f"\n[STATS] {filiale_id}:")
            print(f"   - Documents: {stats.get('count', 0)}")
            print(f"   - Collection: {stats.get('name', 'N/A')}")
        else:
            # Stats pour toutes les filiales connues
            filiales = ['coris_ci', 'coris_bf', 'coris_ml', 'coris_sn']
            print(f"\n[STATS] Toutes les filiales:")
            
            for filiale in filiales:
                try:
                    stats = self.chroma_manager.get_collection_stats("coris_money", filiale)
                    count = stats.get('count', 0)
                    print(f"   - {filiale}: {count} documents")
                except Exception:
                    print(f"   - {filiale}: Collection non trouvée")

async def main():
    """Fonction principale"""
    
    print("🚀 CHARGEMENT BASE DE CONNAISSANCES CORIS")
    print("=" * 60)
    
    loader = KnowledgeBaseLoader()
    
    if len(sys.argv) > 1:
        # Charger une filiale spécifique
        filiale_id = sys.argv[1]
        print(f"Mode: Chargement filiale {filiale_id}")
        
        success = await loader.load_single_filiale(filiale_id)
        if success:
            await loader.verify_loading(filiale_id)
            await loader.show_stats(filiale_id)
    else:
        # Charger toutes les filiales
        print("Mode: Chargement toutes filiales")
        
        success = await loader.load_all_filiales()
        if success:
            print("\n" + "=" * 60)
            print("VERIFICATION DES CHARGEMENTS")
            print("=" * 60)
            
            for filiale in ['coris_ci', 'coris_bf', 'coris_ml', 'coris_sn']:
                await loader.verify_loading(filiale)
            
            await loader.show_stats()
    
    print("\n✅ Processus terminé!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Processus interrompu")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()