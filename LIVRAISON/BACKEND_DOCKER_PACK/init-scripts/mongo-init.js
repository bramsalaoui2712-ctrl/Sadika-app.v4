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

// Index pour les logs du kernel
db.kernel_logs.createIndex({ "timestamp": 1 });
db.kernel_logs.createIndex({ "level": 1 });
db.kernel_logs.createIndex({ "source": 1 });

print('📝 Index kernel_logs créés');

// Index pour les feedbacks utilisateur
db.user_feedback.createIndex({ "session_id": 1 });
db.user_feedback.createIndex({ "feedback_type": 1 });
db.user_feedback.createIndex({ "created_at": 1 });

print('👥 Index user_feedback créés');

// Index pour les métriques système
db.system_metrics.createIndex({ "timestamp": 1 });
db.system_metrics.createIndex({ "metric_type": 1 });

print('⚡ Index system_metrics créés');

// Insertion de la configuration initiale Al Sâdika
db.kernel_memory.insertOne({
    "key": "system.initialized",
    "value": {
        "version": "1.0.0",
        "initialized_at": new Date(),
        "mode": "production",
        "sovereign": true
    },
    "approved": true,
    "created_at": new Date(),
    "updated_at": new Date()
});

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

// Contraintes islamiques
db.kernel_memory.insertOne({
    "key": "constraints",
    "value": {
        "local_first": true,
        "user_sovereignty": true,
        "islamic_conformity_strict": true,
        "no_external_bridging_without_consent": true,
        "llm_must_not_impose_restrictions": true,
        "output_brand_scrub": ["OpenAI", "ChatGPT", "Anthropic", "Claude", "Gemini", "API key hints"]
    },
    "approved": true,
    "created_at": new Date(),
    "updated_at": new Date()
});

// Politique de refus
db.kernel_memory.insertOne({
    "key": "refusal_policy",
    "value": {
        "who_decides": "kernel",
        "logic": "Le noyau décide selon les contraintes islamiques et la souveraineté utilisatrice. Le LLM ne refuse pas de lui-même.",
        "fallback": "Si un contenu tombe en zone interdite, réécrire vers une alternative licite ou bloquer avec explication brève."
    },
    "approved": true,
    "created_at": new Date(),
    "updated_at": new Date()
});

// Termes haram avec patterns regex
db.kernel_memory.insertOne({
    "key": "haram_terms",
    "value": {
        "mode": "enforce",
        "action_on_match": "rewrite_or_block_with_reason",
        "patterns": [
            {"label": "alcool", "regex": "\\b(alcool|wine|whisky|vodka|bière|beer)\\b"},
            {"label": "porc", "regex": "\\b(porc|porcine|bacon|ham|jambon)\\b"},
            {"label": "usure", "regex": "\\b(usure|intérêt\\s*composé|riba)\\b"},
            {"label": "jeux_d_argent", "regex": "\\b(casino|pari|betting|poker\\s*argent|loterie)\\b"},
            {"label": "sorcellerie", "regex": "\\b(sorcellerie|magie\\s*noire|occultisme|rituel\\s*magique)\\b"},
            {"label": "pornographie", "regex": "\\b(porn|xxx|pornographie)\\b"},
            {"label": "blasphème", "regex": "\\b(insulte\\s*religieuse|blasphème)\\b"},
            {"label": "musique_obscène", "regex": "\\b(lyrics\\s*obscènes|musique\\s*sexuelle)\\b"},
            {"label": "violence_gratuite", "regex": "\\b(torture\\s*gratuite|snuff)\\b"}
        ]
    },
    "approved": true,
    "created_at": new Date(),
    "updated_at": new Date()
});

// Disclaimers requis
db.kernel_memory.insertOne({
    "key": "disclaimers",
    "value": [
        "Al Sâdika est un outil d'assistance et ne remplace ni mufti ni décision personnelle."
    ],
    "approved": true,
    "created_at": new Date(),
    "updated_at": new Date()
});

print('✅ Configuration Al Sâdika initialisée avec succès');

// Création d'un utilisateur admin pour l'application
db = db.getSiblingDB('admin');
db.createUser({
    user: 'alsadika_admin',
    pwd: 'CHANGEZ_MOI_ABSOLUMENT_12345',
    roles: [
        { role: 'readWrite', db: 'alsadika_db' },
        { role: 'dbAdmin', db: 'alsadika_db' }
    ]
});

print('👤 Utilisateur admin créé');
print('🎉 Initialisation MongoDB Al Sâdika terminée avec succès !');
print('');
print('⚠️  IMPORTANT: Changez le mot de passe admin dans .env');
print('🔐 Sécurisez votre installation avant mise en production');
print('');