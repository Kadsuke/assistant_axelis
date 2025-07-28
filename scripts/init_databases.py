#!/usr/bin/env python3
"""
Script d'initialisation de la base de données Conversations
Version corrigée pour Windows
"""
import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

# Fixer l'encodage pour Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

async def create_conversations_database():
    """Crée la base de données conversations et ses tables"""
    
    # Connexion à PostgreSQL pour créer la base
    try:
        conn = await asyncpg.connect(
            host=os.getenv("CONVERSATIONS_HOST"),
            port=os.getenv("CONVERSATIONS_PORT"),
            user=os.getenv("CONVERSATIONS_USER"),
            password=os.getenv("CONVERSATIONS_PASSWORD"),
            database="postgres"  # Base par défaut
        )
    except Exception as e:
        print(f"[ERROR] Impossible de se connecter à PostgreSQL: {e}")
        print("Vérifiez que PostgreSQL est démarré et que les variables d'environnement sont correctes")
        return False
    
    # Créer la base de données
    try:
        await conn.execute(f"CREATE DATABASE {os.getenv('CONVERSATIONS_DB')}")
        print(f"[OK] Database {os.getenv('CONVERSATIONS_DB')} created")
    except Exception as e:
        print(f"[WARNING] Database might already exist: {e}")
    
    await conn.close()
    
    # Connexion à la nouvelle base pour créer les tables
    try:
        conn = await asyncpg.connect(
            host=os.getenv("CONVERSATIONS_HOST"),
            port=os.getenv("CONVERSATIONS_PORT"),
            user=os.getenv("CONVERSATIONS_USER"),
            password=os.getenv("CONVERSATIONS_PASSWORD"),
            database=os.getenv("CONVERSATIONS_DB")
        )
    except Exception as e:
        print(f"[ERROR] Impossible de se connecter à la base conversations: {e}")
        return False
    
    # SQL de création des tables
    create_tables_sql = """
    -- Activer l'extension UUID
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    
    -- Table des conversations
    CREATE TABLE IF NOT EXISTS conversations (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id VARCHAR(100) NOT NULL,
        filiale_id VARCHAR(50) NOT NULL,
        application_id VARCHAR(50) NOT NULL,
        pack_level VARCHAR(20) NOT NULL,
        channel VARCHAR(20) DEFAULT 'mobile',
        status VARCHAR(20) DEFAULT 'active',
        context VARCHAR(255),
        language VARCHAR(20),
        processing_time DECIMAL(8,3),
        confidence_score DECIMAL(3,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata JSONB
    );
    
    -- Table des messages
    CREATE TABLE IF NOT EXISTS messages (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        conversation_id UUID REFERENCES conversations(id),
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        agent_used VARCHAR(50),
        tools_used JSONB,
        tokens_consumed INTEGER,
        confidence_score DECIMAL(3,2),
        processing_time DECIMAL(8,3),
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata JSONB
    );
    
    -- Table des escalades
    CREATE TABLE IF NOT EXISTS escalations (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        conversation_id UUID REFERENCES conversations(id),
        escalation_reason VARCHAR(100) NOT NULL,
        escalation_type VARCHAR(20) NOT NULL,
        priority VARCHAR(20) DEFAULT 'medium',
        assigned_to VARCHAR(100),
        status VARCHAR(20) DEFAULT 'pending',
        context_summary TEXT,
        escalated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP,
        resolution_notes TEXT
    );
    
    -- Table des agents humains
    CREATE TABLE IF NOT EXISTS human_agents (
        id VARCHAR(100) PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        email VARCHAR(200) NOT NULL,
        specialties JSONB,
        languages JSONB,
        status VARCHAR(20) DEFAULT 'available',
        current_load INTEGER DEFAULT 0,
        max_concurrent INTEGER DEFAULT 5,
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Index pour les performances
    CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
    CREATE INDEX IF NOT EXISTS idx_conversations_filiale ON conversations(filiale_id);
    CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
    """
    
    try:
        await conn.execute(create_tables_sql)
        print("[OK] Tables created successfully")
    except Exception as e:
        print(f"[ERROR] Failed to create tables: {e}")
        return False
    
    await conn.close()
    print("[OK] Database initialization completed")
    return True

if __name__ == "__main__":
    success = asyncio.run(create_conversations_database())
    if not success:
        sys.exit(1)