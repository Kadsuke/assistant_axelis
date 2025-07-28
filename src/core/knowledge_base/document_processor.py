"""
Processeur de documents pour la base de connaissances
Gère l'extraction, le nettoyage et la segmentation des documents
"""
import re
import os
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime
import structlog
import hashlib
import mimetypes

# Imports pour traitement de documents
try:
    import PyPDF2
    import docx
    import markdown
    from bs4 import BeautifulSoup
    HAS_DOC_PROCESSORS = True
except ImportError:
    HAS_DOC_PROCESSORS = False

logger = structlog.get_logger()

class DocumentProcessor:
    """
    Processeur de documents multi-format
    Extrait le texte et génère des métadonnées
    """
    
    def __init__(self):
        self.chunk_size = 1000  # Taille des chunks en caractères
        self.chunk_overlap = 200  # Chevauchement entre chunks
        self.supported_formats = {
            '.txt': self._process_text,
            '.md': self._process_markdown,
            '.pdf': self._process_pdf,
            '.docx': self._process_docx,
            '.html': self._process_html,
            '.json': self._process_json,
            '.csv': self._process_csv
        }
        
        # Patterns pour extraction d'informations
        self.patterns = {
            'phone': r'\+225\d{8}|\d{2}\s?\d{2}\s?\d{2}\s?\d{2}',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'account': r'\b\d{10,16}\b',
            'amount': r'\b\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?\s?(?:XOF|FCFA|€|USD|\$)\b',
            'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            'procedure_step': r'(?:étape|step)\s*\d+|^\d+\.\s+',
            'faq_question': r'^(?:Q|Question)\s*:?\s*(.+?)(?=\n|$)',
            'faq_answer': r'^(?:R|Réponse|Answer)\s*:?\s*(.+?)(?=\n|$)'
        }
    
    async def process_file(self, 
                          file_path: str, 
                          filiale_id: str,
                          application: str,
                          category: Optional[str] = None,
                          custom_metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Traite un fichier et retourne une liste de documents segmentés
        
        Args:
            file_path: Chemin vers le fichier
            filiale_id: ID de la filiale
            application: Application concernée
            category: Catégorie du document
            custom_metadata: Métadonnées personnalisées
            
        Returns:
            Liste des documents segmentés avec métadonnées
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Détecter le type de fichier
            file_extension = file_path.suffix.lower()
            if file_extension not in self.supported_formats:
                logger.warning(f"Unsupported file format: {file_extension}")
                return []
            
            # Extraire le contenu
            content = await self.supported_formats[file_extension](file_path)
            
            if not content:
                logger.warning(f"No content extracted from: {file_path}")
                return []
            
            # Générer les métadonnées de base
            base_metadata = await self._generate_base_metadata(
                file_path, filiale_id, application, category, custom_metadata
            )
            
            # Segmenter le contenu
            chunks = self._chunk_text(content)
            
            # Traiter chaque chunk
            documents = []
            for i, chunk in enumerate(chunks):
                # Analyser le chunk
                chunk_analysis = self._analyze_chunk(chunk)
                
                # Créer les métadonnées du chunk
                chunk_metadata = {
                    **base_metadata,
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "chunk_size": len(chunk),
                    **chunk_analysis
                }
                
                # Générer un ID unique pour le chunk
                chunk_id = self._generate_chunk_id(file_path, i, chunk)
                
                documents.append({
                    "id": chunk_id,
                    "content": chunk.strip(),
                    "metadata": chunk_metadata
                })
            
            logger.info(f"Processed file: {file_path.name}", 
                       chunks_created=len(documents),
                       total_size=len(content))
            
            return documents
            
        except Exception as e:
            logger.error(f"Error processing file: {file_path}", error=str(e))
            return []
    
    async def process_text_content(self,
                                  content: str,
                                  source_name: str,
                                  filiale_id: str,
                                  application: str,
                                  category: Optional[str] = None,
                                  custom_metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Traite du contenu texte directement
        
        Args:
            content: Contenu texte à traiter
            source_name: Nom de la source
            filiale_id: ID de la filiale
            application: Application concernée
            category: Catégorie du contenu
            custom_metadata: Métadonnées personnalisées
            
        Returns:
            Liste des documents segmentés
        """
        try:
            if not content.strip():
                return []
            
            # Métadonnées de base
            base_metadata = {
                "source": source_name,
                "filiale_id": filiale_id,
                "application": application,
                "category": category or "text_content",
                "type": "text",
                "processed_at": datetime.now().isoformat(),
                "content_hash": hashlib.md5(content.encode()).hexdigest(),
                **(custom_metadata or {})
            }
            
            # Segmenter le contenu
            chunks = self._chunk_text(content)
            
            documents = []
            for i, chunk in enumerate(chunks):
                chunk_analysis = self._analyze_chunk(chunk)
                
                chunk_metadata = {
                    **base_metadata,
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "chunk_size": len(chunk),
                    **chunk_analysis
                }
                
                chunk_id = f"{source_name}_{filiale_id}_{i}_{hashlib.md5(chunk.encode()).hexdigest()[:8]}"
                
                documents.append({
                    "id": chunk_id,
                    "content": chunk.strip(),
                    "metadata": chunk_metadata
                })
            
            return documents
            
        except Exception as e:
            logger.error("Error processing text content", error=str(e))
            return []
    
    async def _generate_base_metadata(self,
                                     file_path: Path,
                                     filiale_id: str,
                                     application: str,
                                     category: Optional[str],
                                     custom_metadata: Optional[Dict]) -> Dict:
        """Génère les métadonnées de base pour un fichier"""
        
        file_stats = file_path.stat()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        metadata = {
            "source": str(file_path.name),
            "source_path": str(file_path),
            "filiale_id": filiale_id,
            "application": application,
            "category": category or "general",
            "file_extension": file_path.suffix.lower(),
            "mime_type": mime_type,
            "file_size": file_stats.st_size,
            "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            "processed_at": datetime.now().isoformat()
        }
        
        if custom_metadata:
            metadata.update(custom_metadata)
        
        return metadata
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Segmente le texte en chunks avec chevauchement
        
        Args:
            text: Texte à segmenter
            
        Returns:
            Liste des chunks
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Si ce n'est pas le dernier chunk, essayer de couper à un délimiteur naturel
            if end < len(text):
                # Chercher le dernier point, nouvelle ligne ou espace
                for delimiter in ['\n\n', '\n', '. ', '? ', '! ', ' ']:
                    last_delimiter = text.rfind(delimiter, start, end)
                    if last_delimiter > start:
                        end = last_delimiter + len(delimiter)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Calculer le prochain point de départ avec chevauchement
            start = max(start + 1, end - self.chunk_overlap)
        
        return chunks
    
    def _analyze_chunk(self, chunk: str) -> Dict:
        """
        Analyse un chunk pour extraire des informations structurées
        
        Args:
            chunk: Chunk de texte à analyser
            
        Returns:
            Dictionnaire d'informations extraites
        """
        analysis = {
            "contains_phone": bool(re.search(self.patterns['phone'], chunk)),
            "contains_email": bool(re.search(self.patterns['email'], chunk)),
            "contains_amount": bool(re.search(self.patterns['amount'], chunk)),
            "contains_date": bool(re.search(self.patterns['date'], chunk)),
            "contains_procedure": bool(re.search(self.patterns['procedure_step'], chunk, re.MULTILINE)),
            "is_faq": bool(re.search(self.patterns['faq_question'], chunk, re.MULTILINE)),
            "word_count": len(chunk.split()),
            "sentence_count": len(re.split(r'[.!?]+', chunk)),
            "language": self._detect_language(chunk)
        }
        
        # Extraire les entités spécifiques
        phones = re.findall(self.patterns['phone'], chunk)
        if phones:
            analysis["phone_numbers"] = phones
        
        emails = re.findall(self.patterns['email'], chunk)
        if emails:
            analysis["email_addresses"] = emails
        
        amounts = re.findall(self.patterns['amount'], chunk)
        if amounts:
            analysis["amounts_mentioned"] = amounts
        
        # Déterminer le type de contenu
        analysis["content_type"] = self._classify_content_type(chunk, analysis)
        
        return analysis
    
    def _detect_language(self, text: str) -> str:
        """Détection basique de la langue"""
        # Mots français courants
        french_indicators = ['le', 'la', 'les', 'de', 'du', 'des', 'et', 'est', 'dans', 'pour', 'avec', 'vous', 'votre']
        # Mots anglais courants
        english_indicators = ['the', 'and', 'is', 'in', 'for', 'with', 'you', 'your', 'this', 'that']
        
        text_lower = text.lower()
        french_count = sum(1 for word in french_indicators if word in text_lower)
        english_count = sum(1 for word in english_indicators if word in text_lower)
        
        if french_count > english_count:
            return "fr"
        elif english_count > french_count:
            return "en"
        else:
            return "unknown"
    
    def _classify_content_type(self, chunk: str, analysis: Dict) -> str:
        """Classifie le type de contenu du chunk"""
        if analysis.get("is_faq"):
            return "faq"
        elif analysis.get("contains_procedure"):
            return "procedure"
        elif analysis.get("contains_amount") and analysis.get("word_count", 0) < 50:
            return "tarif"
        elif "contact" in chunk.lower() and analysis.get("contains_phone"):
            return "contact_info"
        elif any(word in chunk.lower() for word in ["erreur", "problème", "bug", "dysfonctionnement"]):
            return "troubleshooting"
        elif any(word in chunk.lower() for word in ["règlement", "condition", "juridique", "légal"]):
            return "regulation"
        else:
            return "general"
    
    def _generate_chunk_id(self, file_path: Path, chunk_index: int, chunk_content: str) -> str:
        """Génère un ID unique pour un chunk"""
        content_hash = hashlib.md5(chunk_content.encode()).hexdigest()[:8]
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        return f"{file_path.stem}_{file_hash}_{chunk_index}_{content_hash}"
    
    # Méthodes de traitement par type de fichier
    
    async def _process_text(self, file_path: Path) -> str:
        """Traite un fichier texte"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback sur d'autres encodages
            for encoding in ['latin-1', 'cp1252']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            raise
    
    async def _process_markdown(self, file_path: Path) -> str:
        """Traite un fichier Markdown"""
        if not HAS_DOC_PROCESSORS:
            logger.warning("Markdown processor not available, treating as text")
            return await self._process_text(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # Convertir en HTML puis extraire le texte
            html = markdown.markdown(md_content)
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text()
        except Exception as e:
            logger.warning(f"Error processing markdown file: {e}")
            return await self._process_text(file_path)
    
    async def _process_pdf(self, file_path: Path) -> str:
        """Traite un fichier PDF"""
        if not HAS_DOC_PROCESSORS:
            logger.warning("PDF processor not available")
            return ""
        
        try:
            text = ""
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error processing PDF file: {e}")
            return ""
    
    async def _process_docx(self, file_path: Path) -> str:
        """Traite un fichier Word"""
        if not HAS_DOC_PROCESSORS:
            logger.warning("DOCX processor not available")
            return ""
        
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error processing DOCX file: {e}")
            return ""
    
    async def _process_html(self, file_path: Path) -> str:
        """Traite un fichier HTML"""
        if not HAS_DOC_PROCESSORS:
            logger.warning("HTML processor not available, treating as text")
            return await self._process_text(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Supprimer les scripts et styles
            for script in soup(["script", "style"]):
                script.decompose()
            
            return soup.get_text()
        except Exception as e:
            logger.warning(f"Error processing HTML file: {e}")
            return await self._process_text(file_path)
    
    async def _process_json(self, file_path: Path) -> str:
        """Traite un fichier JSON"""
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convertir le JSON en texte lisible
            if isinstance(data, dict):
                text_parts = []
                for key, value in data.items():
                    if isinstance(value, (str, int, float)):
                        text_parts.append(f"{key}: {value}")
                    elif isinstance(value, list):
                        text_parts.append(f"{key}: {', '.join(map(str, value))}")
                return "\n".join(text_parts)
            elif isinstance(data, list):
                return "\n".join(str(item) for item in data)
            else:
                return str(data)
        except Exception as e:
            logger.error(f"Error processing JSON file: {e}")
            return ""
    
    async def _process_csv(self, file_path: Path) -> str:
        """Traite un fichier CSV"""
        try:
            import csv
            text_parts = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.DictReader(f)
                for row in csv_reader:
                    row_text = ", ".join(f"{key}: {value}" for key, value in row.items() if value)
                    text_parts.append(row_text)
            
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            return ""
    
    def get_supported_formats(self) -> List[str]:
        """Retourne la liste des formats supportés"""
        return list(self.supported_formats.keys())
    
    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Valide qu'un fichier peut être traité
        
        Args:
            file_path: Chemin vers le fichier
            
        Returns:
            Tuple (valid, message)
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                return False, "File does not exist"
            
            if not file_path.is_file():
                return False, "Path is not a file"
            
            file_extension = file_path.suffix.lower()
            if file_extension not in self.supported_formats:
                return False, f"Unsupported format: {file_extension}"
            
            # Vérifier la taille du fichier (limite à 50MB)
            max_size = 50 * 1024 * 1024  # 50MB
            if file_path.stat().st_size > max_size:
                return False, f"File too large (max {max_size/1024/1024}MB)"
            
            return True, "File is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

# Instance globale
document_processor = DocumentProcessor()