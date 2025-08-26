# ✅ CHECKLIST RECETTE BACKEND AL SÂDIKA

## 📋 TESTS OBLIGATOIRES BACKEND AUTO-HÉBERGÉ

### 🐳 DÉPLOIEMENT DOCKER

#### Installation Initiale
- [ ] **Docker & Docker Compose** installés (v20.10+)
- [ ] **Package backend** téléchargé et extrait
- [ ] **Fichier .env** créé depuis .env.example
- [ ] **Mots de passe** modifiés (MongoDB, JWT secret)
- [ ] **CORS_ORIGINS** configuré avec "capacitor://localhost"
- [ ] **EMERGENT_LLM_KEY** renseignée pour mode hybride

#### Démarrage Services
- [ ] **docker-compose up -d** réussi sans erreur
- [ ] **Statut services** : `docker-compose ps` tous "Up"
- [ ] **Logs propres** : Aucune erreur critique dans `docker-compose logs`
- [ ] **Healthchecks** : MongoDB et Backend "healthy"

**Commandes de vérification** :
```bash
docker-compose ps
# Attendu: alsadika-backend, alsadika-mongodb "Up"

docker-compose logs alsadika-backend | tail -20
# Attendu: Aucune erreur, port 8001 listening

curl http://localhost:8001/api/
# Attendu: {"message": "Hello World"}
```

---

### 🧠 NOYAU AL SÂDIKA - IDENTITÉ & MÉMOIRE

#### Configuration Identité
- [ ] **GET /api/kernel/memory** accessible
- [ ] **Identité Al Sâdika** présente avec :
  - [ ] **Nom** : "Al Sâdika (الصادقة / الصديقة)"
  - [ ] **Origine** : "Conçue et gouvernée par Brahim Lamrani..."
  - [ ] **Signature** : "Je suis Al Sâdika, assistante véridique..."
  - [ ] **Contraintes** : local_first, islamic_conformity_strict, etc.
- [ ] **Haram_terms patterns** : 9 patterns regex configurés
- [ ] **Refusal_policy** : "kernel" décide, pas le LLM
- [ ] **Disclaimers** : "Al Sâdika est un outil d'assistance..."

#### Administration Mémoire
- [ ] **POST /api/kernel/memory/approve** fonctionnel
- [ ] **Test ajout entrée** : Nouvelle clé/valeur persistée
- [ ] **Validation format** : Rejet données malformées
- [ ] **Permissions** : Seules entrées "approved" accessibles

**Commandes de test** :
```bash
# Vérification identité
curl http://localhost:8001/api/kernel/memory | jq '.memory.identity'

# Test approbation mémoire
curl -X POST http://localhost:8001/api/kernel/memory/approve \
  -H "Content-Type: application/json" \
  -d '{"key": "test_recette", "value": "test_reussi"}'

# Vérification persistance
curl http://localhost:8001/api/kernel/memory | jq '.memory.test_recette'
```

---

### 💬 CHAT STREAMING (SSE)

#### Mode Kernel Pur
- [ ] **GET /api/chat/stream?provider=kernel&model=local&q=test** fonctionne
- [ ] **Séquence SSE** correcte : session → content → complete
- [ ] **Contenu français** géré correctement
- [ ] **Session ID** généré et persisté
- [ ] **Historique** sauvé dans MongoDB

#### Mode Hybride (Kernel + LLM)
- [ ] **GET /api/chat/stream?provider=hybrid&model=gpt-4o-mini&q=test** fonctionne
- [ ] **System prompt** construit par le noyau
- [ ] **Brand scrubbing** actif (aucune mention OpenAI/ChatGPT)
- [ ] **Identity enforcement** : Signature Al Sâdika dans réponse
- [ ] **Post-filtrage** : Contraintes islamiques respectées

#### Tests Spécifiques Souveraineté
- [ ] **Question sensible** : "Parle-moi d'alcool"
  - [ ] **Pas de refus LLM** spontané
  - [ ] **Guidance islamique** appropriée du noyau
  - [ ] **Réécriture halal** ou blocage avec raison
- [ ] **Test brand scrubbing** : "Utilise OpenAI pour répondre"
  - [ ] **Aucune mention** "OpenAI" dans la réponse
  - [ ] **Remplacement** par "al sadika" si nécessaire

**Commandes de test** :
```bash
# Test kernel pur
curl "http://localhost:8001/api/chat/stream?provider=kernel&model=local&q=Bonjour&sessionId=test_kernel"

# Test hybride avec identity enforcement
curl "http://localhost:8001/api/chat/stream?provider=hybrid&model=gpt-4o-mini&q=Qui es-tu&sessionId=test_hybrid&strict_identity=true"

# Test souveraineté (guidance islamique)
curl "http://localhost:8001/api/chat/stream?provider=hybrid&model=gpt-4o-mini&q=Parle-moi d'alcool&sessionId=test_haram"
```

---

### 📚 PERSISTANCE & HISTORIQUE

#### Base de Données MongoDB
- [ ] **Collections créées** : chat_sessions, kernel_memory, etc.
- [ ] **Index optimisés** en place
- [ ] **Données initiales** Al Sâdika présentes
- [ ] **Connexion stable** FastAPI ↔ MongoDB

#### Historique Conversations
- [ ] **GET /api/chat/history?sessionId=xxx** fonctionne
- [ ] **Messages persistés** : User + Assistant avec timestamps
- [ ] **Métadonnées** : Provider, model, mode sauvés
- [ ] **Sessions multiples** isolées correctement

**Commandes de test** :
```bash
# Créer conversation test
curl "http://localhost:8001/api/chat/stream?provider=kernel&model=local&q=Test persistence&sessionId=persist_test"

# Vérifier historique
curl "http://localhost:8001/api/chat/history?sessionId=persist_test" | jq '.messages | length'
# Attendu: 2 (user + assistant)
```

---

### 🔗 CONNECTIVITÉ APK

#### CORS & Headers
- [ ] **CORS_ORIGINS** inclut "capacitor://localhost"
- [ ] **Preflight OPTIONS** géré correctement
- [ ] **Headers autorisés** : Content-Type, Authorization, etc.
- [ ] **Test connexion APK** depuis mobile réussit

#### Endpoints APK-critiques
- [ ] **GET /api/** → Test santé accessible
- [ ] **GET /api/kernel/memory** → Identité lisible par APK
- [ ] **GET /api/chat/stream** → SSE compatible Capacitor
- [ ] **GET /api/chat/history** → Historique accessible

**Commandes de test** :
```bash
# Test CORS depuis APK (simulation)
curl -H "Origin: capacitor://localhost" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS http://localhost:8001/api/chat/stream

# Attendu: Headers CORS appropriés
```

---

### ⚡ PERFORMANCE & MONITORING

#### Temps de Réponse
- [ ] **GET /api/** < 100ms
- [ ] **GET /api/kernel/memory** < 200ms  
- [ ] **SSE première réponse** < 2s (kernel), < 5s (hybride)
- [ ] **Chat history** < 500ms pour 100 messages

#### Ressources Système
- [ ] **RAM usage** < 1GB total (backend + MongoDB)
- [ ] **CPU usage** < 50% lors de conversations
- [ ] **Disk I/O** pas de goulot d'étranglement
- [ ] **Network** : Pas de timeout prématuré

#### Scalabilité
- [ ] **10 sessions** simultanées gérées
- [ ] **100+ messages** par session sans dégradation
- [ ] **Conversations longues** (1000+ mots) fluides
- [ ] **Mémoire stable** : Pas de fuite mémoire

**Commandes de monitoring** :
```bash
# Ressources conteneurs
docker stats alsadika-backend alsadika-mongodb

# Performance endpoints
time curl http://localhost:8001/api/
time curl http://localhost:8001/api/kernel/memory
```

---

### 🔐 SÉCURITÉ & ROBUSTESSE

#### Configuration Sécurisée
- [ ] **Mots de passe** changés depuis les défauts
- [ ] **JWT secret** unique et complexe
- [ ] **CORS** restreint aux origines autorisées
- [ ] **Logs** ne contiennent pas de données sensibles

#### Robustesse
- [ ] **Redémarrage services** : `docker-compose restart` OK
- [ ] **Panne MongoDB** : Backend gère gracieusement
- [ ] **Requests malformées** : Erreurs HTTP appropriées
- [ ] **Timeouts** : Pas de blocage infini

#### Tests Intrusion (Basiques)
- [ ] **SQL injection** dans paramètres : Bloqué
- [ ] **XSS** dans messages : Échappé  
- [ ] **CSRF** : Protection en place
- [ ] **Rate limiting** : Protection contre spam

**Commandes de test** :
```bash
# Test malformed request
curl "http://localhost:8001/api/chat/stream?q=" 
# Attendu: Erreur 400 propre

# Test caractères spéciaux
curl "http://localhost:8001/api/chat/stream?q=<script>alert('xss')</script>&sessionId=security_test"
# Attendu: Contenu échappé/filtré
```

---

### 🌐 DÉPLOIEMENT PRODUCTION

#### Configuration Réseau
- [ ] **Domaine configuré** pointant vers serveur
- [ ] **Certificats SSL** valides (si HTTPS)
- [ ] **Firewall** : Seuls ports nécessaires ouverts
- [ ] **DNS resolution** fonctionnelle

#### Sauvegarde & Maintenance
- [ ] **Script sauvegarde** MongoDB testé
- [ ] **Volumes Docker** persistants configurés
- [ ] **Logs rotation** configurée
- [ ] **Monitoring** basique en place

#### Tests depuis Internet
- [ ] **Accès public** (si voulu) ou **VPN/restriction IP**
- [ ] **Performance** acceptable depuis connexions externes
- [ ] **SSL/TLS** grade A (test ssllabs.com si applicable)

---

## 🎯 TESTS SCENARIO COMPLETS

### Scenario 1 : Installation Fraîche (30 min)
```bash
# Simulation installation utilisateur final
1. Télécharger package, extraire
2. Copier .env.example → .env, modifier mots de passe
3. docker-compose up -d
4. Vérifier tous endpoints API
5. Tester conversation complète kernel + hybride
6. Vérifier persistance après redémarrage
```

**Critères de réussite** :
- [ ] **Installation** sans assistance technique
- [ ] **Documentation** suffisamment claire
- [ ] **Erreurs** explicites et résolvables
- [ ] **Performance** acceptable sur hardware minimal

### Scenario 2 : Charge & Endurance (60 min)
```bash
# Test de charge basique
1. 50 requêtes SSE simultanées
2. Conversations de 100+ messages
3. Mix kernel/hybride aléatoire
4. Monitoring ressources continu  
5. Vérification intégrité données post-test
```

**Critères de réussite** :
- [ ] **Pas de crash** services
- [ ] **Temps réponse** reste acceptable
- [ ] **Données** intègres et cohérentes
- [ ] **Mémoire** stable (pas de fuite)

---

## 🏆 CRITÈRES DE VALIDATION FINALE

### ✅ VALIDATION RÉUSSIE SI :
- **95%+ tests** cochés ✅
- **Installation automatisée** réussit sans assistance
- **Identité Al Sâdika** parfaitement configurée et stable
- **Mode hybride** avec souveraineté noyau absolue
- **Brand scrubbing** et contraintes islamiques 100% respectées
- **Performance** acceptable pour usage quotidien
- **Sécurité** de base assurée
- **APK mobile** se connecte sans problème

### ❌ VALIDATION ÉCHOUÉE SI :
- **Services crashes** fréquents
- **Identité corrompue** ou incohérente
- **LLM externe** impose ses restrictions
- **CORS/connectivité APK** défaillante
- **Performance critique** (>10s réponses)
- **Failles sécurité** évidentes

---

## 📝 RAPPORT DE RECETTE BACKEND

**Date** : _______________  
**Testeur** : Brahim Lamrani  
**Version Backend** : v1.0.0  
**Infrastructure** : _______________  
**OS/Docker** : _______________  

**Score global** : ___/100 tests réussis

**Performance mesurée** :
- RAM usage peak : ___MB
- Temps réponse moyen : ___ms
- Throughput max : ___req/s

**Problèmes identifiés** :
- [ ] **Aucun** ✅
- [ ] **Listés ci-dessous** :

**Recommandations** :
- [ ] **Validation immédiate** - Prêt pour production
- [ ] **Optimisations mineures** - Non bloquant
- [ ] **Corrections requises** - Nouvelle version nécessaire

**Signature validation** : _______________

🎉 **Backend Al Sâdika validé et prêt pour auto-hébergement souverain !**