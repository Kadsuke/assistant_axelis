# Dockerfile principal pour l'application
FROM python:3.11-slim

# Définir les variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installer UV
RUN pip install uv

# Créer le répertoire de travail
WORKDIR /app

# Copier les fichiers de configuration
COPY pyproject.toml uv.lock ./

# Installer les dépendances Python
RUN uv sync --frozen

# Copier le code source
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY knowledge_bases/ ./knowledge_bases/
COPY configs/ ./configs/

# Créer les répertoires de données
RUN mkdir -p /app/data/chroma_data /app/data/logs

# Exposer le port
EXPOSE 8000

# Commande de santé
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Commande par défaut
CMD ["uv", "run", "uvicorn", "applications.coris_money.apis.chat:app", "--host", "0.0.0.0", "--port", "8000"]