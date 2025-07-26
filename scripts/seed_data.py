"""
Script de peuplement des données de test
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from core.database.connections import db_manager
from core.knowledge_base.chroma_manager import MultiTenantChromaManager
import uuid
from datetime import datetime

async def seed_human_agents():
    """Peuple la table des agents humains"""
    print("👥 Peuplement des agents humains...")
    
    agents_data = [
        {
            "id": "agent_ci_001",
            "name": "Marie Kouame",
            "email": "marie.kouame@corisbank.ci",
            "specialties": ["reclamations", "operations"],
            "languages": ["fr", "en"],
            "status": "available",
            "max_concurrent": 5
        },
        {
            "id": "agent_ci_002", 
            "name": "Ibrahim Diallo",
            "email": "ibrahim.diallo@corisbank.ci",
            "specialties": ["technique", "operations"],
            "languages": ["fr"],
            "status": "available",
            "max_concurrent": 3
        },
        {
            "id": "agent_bf_001",
            "name": "Aminata Traore",
            "email": "aminata.traore@corisbank.bf",
           "specialties": ["reclamations", "commercial"],
           "languages": ["fr"],
           "status": "available",
           "max_concurrent": 4
       },
       {
           "id": "agent_ml_001",
           "name": "Moussa Keita",
           "email": "moussa.keita@corisbank.ml",
           "specialties": ["operations", "technique"],
           "languages": ["fr"],
           "status": "available",
           "max_concurrent": 3
       }
   ]
   
    async with db_manager.get_conversations_connection() as conn:
       for agent in agents_data:
           query = """
           INSERT INTO human_agents (
               id, name, email, specialties, languages, 
               status, current_load, max_concurrent, last_activity
           ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           ON CONFLICT (id) DO UPDATE SET
               name = EXCLUDED.name,
               email = EXCLUDED.email,
               specialties = EXCLUDED.specialties,
               languages = EXCLUDED.languages,
               status = EXCLUDED.status,
               max_concurrent = EXCLUDED.max_concurrent
           """
           
           await conn.execute(
               query,
               agent["id"], agent["name"], agent["email"],
               agent["specialties"], agent["languages"],
               agent["status"], 0, agent["max_concurrent"],
               datetime.now()
           )
           
           print(f"   ✅ Agent ajouté: {agent['name']}")

async def seed_sample_conversations():
   """Crée des conversations d'exemple"""
   print("💬 Création de conversations d'exemple...")
   
   sample_conversations = [
       {
           "user_id": "demo_user_001",
           "filiale_id": "coris_ci",
           "application_id": "coris_money",
           "pack_level": "coris_basic",
           "channel": "mobile",
           "messages": [
               {"role": "user", "content": "Bonjour, comment consulter mon solde ?"},
               {"role": "assistant", "content": "Bonjour ! Pour consulter votre solde Coris Money, vous pouvez...", "agent_used": "coris_banking_assistant"}
           ]
       },
       {
           "user_id": "demo_user_002",
           "filiale_id": "coris_ci", 
           "application_id": "coris_money",
           "pack_level": "coris_advanced",
           "channel": "web",
           "messages": [
               {"role": "user", "content": "Je veux annuler mon transfert de ce matin"},
               {"role": "assistant", "content": "Je vais vérifier les conditions d'annulation...", "agent_used": "coris_operations_specialist"}
           ]
       }
   ]
   
   async with db_manager.get_conversations_connection() as conn:
       for conv_data in sample_conversations:
           # Créer la conversation
           conv_id = str(uuid.uuid4())
           conv_query = """
           INSERT INTO conversations (
               id, user_id, filiale_id, application_id, pack_level,
               channel, status, created_at, updated_at
           ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           """
           
           now = datetime.now()
           await conn.execute(
               conv_query,
               conv_id, conv_data["user_id"], conv_data["filiale_id"],
               conv_data["application_id"], conv_data["pack_level"],
               conv_data["channel"], "active", now, now
           )
           
           # Ajouter les messages
           for msg in conv_data["messages"]:
               msg_id = str(uuid.uuid4())
               msg_query = """
               INSERT INTO messages (
                   id, conversation_id, role, content, agent_used, timestamp
               ) VALUES ($1, $2, $3, $4, $5, $6)
               """
               
               await conn.execute(
                   msg_query,
                   msg_id, conv_id, msg["role"], msg["content"],
                   msg.get("agent_used"), now
               )
           
           print(f"   ✅ Conversation créée: {conv_data['user_id']}")

async def seed_knowledge_base_content():
   """Peuple les bases de connaissances avec du contenu réaliste"""
   print("📚 Peuplement des bases de connaissances...")
   
   chroma_manager = MultiTenantChromaManager()
   
   # Contenu pour Coris CI
   coris_ci_content = [
       {
           "content": "Pour consulter votre solde Coris Money, ouvrez l'application et appuyez sur 'Mon Compte'. Votre solde s'affiche immédiatement.",
           "metadata": {"category": "faq_general", "type": "consultation", "filiale": "coris_ci"}
       },
       {
           "content": "Les frais de transfert Coris Money en Côte d'Ivoire sont de 1% du montant avec un minimum de 100 FCFA et un maximum de 2000 FCFA.",
           "metadata": {"category": "tarification", "type": "frais", "filiale": "coris_ci"}
       },
       {
           "content": "Pour annuler un transfert Coris Money, vous disposez de 30 minutes après l'envoi. Contactez immédiatement le service client au +225 XX XX XX XX.",
           "metadata": {"category": "procedures_bancaires", "type": "annulation", "filiale": "coris_ci"}
       },
       {
           "content": "Les virements internationaux Coris Money sont disponibles vers 15 pays d'Afrique de l'Ouest. Délai de traitement : 24h à 72h ouvrées.",
           "metadata": {"category": "produits_services", "type": "international", "filiale": "coris_ci"}
       },
       {
           "content": "En cas de problème avec votre transfert, créez une réclamation via l'app ou appelez le +225 XX XX XX XX. Délai de traitement : 72h maximum.",
           "metadata": {"category": "support_technique", "type": "reclamation", "filiale": "coris_ci"}
       }
   ]
   
   documents = [item["content"] for item in coris_ci_content]
   metadatas = [item["metadata"] for item in coris_ci_content]
   ids = [f"coris_ci_doc_{i}" for i in range(len(documents))]
   
   await chroma_manager.add_documents(
       application="coris_money",
       filiale_id="coris_ci",
       documents=documents,
       metadatas=metadatas,
       ids=ids
   )
   
   print(f"   ✅ {len(documents)} documents ajoutés pour coris_ci")
   
   # Contenu pour Coris BF
   coris_bf_content = [
       {
           "content": "Les services Coris Money au Burkina Faso incluent les transferts nationaux, les paiements de factures et la consultation de solde 24h/24.",
           "metadata": {"category": "produits_services", "type": "general", "filiale": "coris_bf"}
       },
       {
           "content": "Tarifs Burkina Faso : Transferts nationaux 0.5% (min 50 FCFA, max 1000 FCFA). Transferts UEMOA 1.5% (min 200 FCFA, max 3000 FCFA).",
           "metadata": {"category": "tarification", "type": "frais", "filiale": "coris_bf"}
       },
       {
           "content": "Service client Burkina Faso disponible de 7h à 19h au +226 XX XX XX XX. Support technique 24h/24 via l'application mobile.",
           "metadata": {"category": "support_technique", "type": "contact", "filiale": "coris_bf"}
       }
   ]
   
   bf_documents = [item["content"] for item in coris_bf_content]
   bf_metadatas = [item["metadata"] for item in coris_bf_content]
   bf_ids = [f"coris_bf_doc_{i}" for i in range(len(bf_documents))]
   
   await chroma_manager.add_documents(
       application="coris_money",
       filiale_id="coris_bf",
       documents=bf_documents,
       metadatas=bf_metadatas,
       ids=bf_ids
   )
   
   print(f"   ✅ {len(bf_documents)} documents ajoutés pour coris_bf")

async def seed_escalation_examples():
   """Crée des exemples d'escalades"""
   print("🚨 Création d'exemples d'escalades...")
   
   # Créer d'abord une conversation à escalader
   async with db_manager.get_conversations_connection() as conn:
       conv_id = str(uuid.uuid4())
       
       # Conversation
       await conn.execute("""
           INSERT INTO conversations (
               id, user_id, filiale_id, application_id, pack_level,
               channel, status, created_at, updated_at
           ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
       """, conv_id, "escalation_demo_user", "coris_ci", "coris_money", 
            "coris_basic", "mobile", "escalated", datetime.now(), datetime.now())
       
       # Messages de la conversation
       messages = [
           {"role": "user", "content": "Mon transfert urgent n'est pas arrivé depuis 3 jours !"},
           {"role": "assistant", "content": "Je vais vérifier votre transfert...", "agent_used": "coris_banking_assistant"},
           {"role": "user", "content": "C'est urgent ! J'ai besoin d'aide immédiatement !"},
           {"role": "assistant", "content": "Je comprends votre urgence. Laissez-moi escalader...", "agent_used": "core_escalation_handler"}
       ]
       
       for msg in messages:
           await conn.execute("""
               INSERT INTO messages (
                   id, conversation_id, role, content, agent_used, timestamp
               ) VALUES ($1, $2, $3, $4, $5, $6)
           """, str(uuid.uuid4()), conv_id, msg["role"], msg["content"],
                msg.get("agent_used"), datetime.now())
       
       # Escalade
       esc_id = str(uuid.uuid4())
       await conn.execute("""
           INSERT INTO escalations (
               id, conversation_id, escalation_reason, escalation_type,
               priority, assigned_to, status, context_summary, escalated_at
           ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
       """, esc_id, conv_id, "urgent_transfer_issue", "human_agent",
            "urgent", "agent_ci_001", "pending",
            "Client attend un transfert urgent depuis 3 jours", datetime.now())
       
       print(f"   ✅ Escalade d'exemple créée: {esc_id}")

async def main():
   """Fonction principale de peuplement"""
   print("🌱 Peuplement des données de test")
   print("=" * 50)
   
   try:
       await seed_human_agents()
       await seed_sample_conversations()
       await seed_knowledge_base_content()
       await seed_escalation_examples()
       
       print("\n✅ Peuplement terminé avec succès!")
       print("\n📊 Données créées:")
       print("   - 4 agents humains")
       print("   - 2 conversations d'exemple")
       print("   - Bases de connaissances (CI + BF)")
       print("   - 1 escalade d'exemple")
       
   except Exception as e:
       print(f"\n❌ Erreur lors du peuplement: {e}")
       import traceback
       traceback.print_exc()

if __name__ == "__main__":
   asyncio.run(main())