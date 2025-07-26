"""
Outils NLP core réutilisables
"""
import asyncio
from typing import Dict, List, Optional
import openai
import os
from dotenv import load_dotenv
import structlog

load_dotenv()
logger = structlog.get_logger()

openai.api_key = os.getenv("OPENAI_API_KEY")

async def classify_intent(message: str, available_intents: List[str]) -> Dict:
    """
    Classifie l'intention d'un message utilisateur
    """
    system_prompt = f"""
    Tu es un classificateur d'intentions pour un assistant bancaire.
    
    Intentions disponibles: {', '.join(available_intents)}
    
    Analyse le message utilisateur et retourne:
    1. L'intention principale (une seule)
    2. Le niveau de confiance (0-100)
    3. Les entités extraites (montants, dates, etc.)
    4. Le sentiment général (positif, neutre, négatif)
    
    Réponds au format JSON uniquement.
    """
    
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        # Parser la réponse JSON
        import json
        result = json.loads(response.choices[0].message.content)
        
        logger.info("Intent classified", 
                   intent=result.get('intention'),
                   confidence=result.get('confiance'))
        
        return result
        
    except Exception as e:
        logger.error("Intent classification failed", error=str(e))
        return {
            "intention": "unknown",
            "confiance": 0,
            "entites": {},
            "sentiment": "neutre"
        }

async def detect_language(message: str) -> str:
    """
    Détecte la langue d'un message
    """
    # Langues supportées par Coris Money
    supported_languages = ["fr", "en"]
    
    # Simple détection basée sur des mots-clés
    french_keywords = ["bonjour", "salut", "merci", "comment", "pourquoi", "transfert", "argent"]
    english_keywords = ["hello", "hi", "thank", "how", "why", "transfer", "money"]
    
    message_lower = message.lower()
    
    french_score = sum(1 for keyword in french_keywords if keyword in message_lower)
    english_score = sum(1 for keyword in english_keywords if keyword in message_lower)
    
    if french_score > english_score:
        return "fr"
    elif english_score > 0:
        return "en"
    else:
        return "fr"  # Défaut pour l'Afrique francophone

async def analyze_sentiment(message: str) -> Dict:
    """
    Analyse le sentiment d'un message
    """
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {
                    "role": "system", 
                    "content": "Analyse le sentiment de ce message. Réponds avec: positif, neutre, négatif, urgent. Format JSON: {\"sentiment\": \"...\", \"urgence\": \"...\", \"emotions\": [...]}"
                },
                {"role": "user", "content": message}
            ],
            temperature=0.1,
            max_tokens=100
        )
        
        import json
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        logger.error("Sentiment analysis failed", error=str(e))
        return {"sentiment": "neutre", "urgence": "normale", "emotions": []}