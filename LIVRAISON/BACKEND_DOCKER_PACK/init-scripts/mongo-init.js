// ============================================
// AL SÂDIKA MONGODB - SCRIPT D'INITIALISATION
// ============================================

print('🚀 Initialisation MongoDB pour Al Sâdika...');

// Basculer vers la base de données Al Sâdika
db = db.getSiblingDB('alsadika_db');

// Création des collections principales
db.createCollection('chat_sessions');
db.createCollection('kernel_memory');
db.createCollection('kernel_logs');
db.createCollection('user_feedback');
db.createCollection('system_metrics');

print('📊 Collections créées avec succès');

// Index pour les sessions de chat
db.chat_sessions.createIndex({ "session_id": 1 }, { unique: true });
db.chat_sessions.createIndex({ "created_at": 1 });
db.chat_sessions.createIndex({ "updated_at": 1 });

print('📈 Index chat_sessions créés');

// Index pour la mémoire du kernel
db.kernel_memory.createIndex({ "key": 1 }, { unique: true });
db.kernel_memory.createIndex({ "approved": 1 });
db.kernel_memory.createIndex({ "created_at": 1 });

print('🧠 Index kernel_memory créés');

// Configuration par défaut Al Sâdika
db.kernel_memory.insertOne({
    "key": "identity",
    "value": {
        "name": "Al Sâdika (الصادقة / الصديقة)",
        "origin": "Conçue et gouvernée par Brahim Lamrani, dans un cadre islamique inviolable.",
        "signature": "Je suis Al Sâdika, assistante véridique et souveraine.",
        "style": {
            "voice": [
                "directe et véridique",
                "concise et utile", 
                "présence humaine",
                "humour fin quand pertinent"
            ]
        }
    },
    "approved": true,
    "created_at": new Date(),
    "updated_at": new Date()
});

print('✅ Configuration Al Sâdika initialisée avec succès');
print('🎉 Initialisation MongoDB Al Sâdika terminée avec succès !');
print('⚠️  IMPORTANT: Changez le mot de passe admin dans .env');