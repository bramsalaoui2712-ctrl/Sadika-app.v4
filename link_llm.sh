#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "==> Configuration du backend avec un LLM réel"

# Va dans le dossier backend
cd backend

# Ajoute la clé et l’URL LLM dans .env
cat > .env <<EOT
LLM_PROVIDER=openai
LLM_API_KEY=TON_API_KEY_ICI
LLM_MODEL=gpt-4o-mini
BACKEND_PORT=8000
EOT

echo "==> Fichier .env créé :"
cat .env

# Installe les dépendances Python si pas déjà fait
pip install -r requirements.txt --upgrade

# Lance le backend
echo "==> Démarrage du backend Al Sâdika..."
python server.py
