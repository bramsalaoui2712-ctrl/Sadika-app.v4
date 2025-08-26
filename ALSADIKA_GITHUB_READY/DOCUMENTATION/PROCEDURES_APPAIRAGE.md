# 🔗 PROCÉDURES D'APPAIRAGE APK ↔ NOYAU

## 🎯 PRINCIPE

L'APK Al Sâdika doit être appairée avec votre backend auto-hébergé pour fonctionner. Cette procédure garantit que seule votre instance contrôle Al Sâdika.

---

## 🚀 APPAIRAGE INITIAL

### 1. Préparation Backend
```bash
# Vérifier que le backend est démarré
curl http://votre-ip:8001/api/
# Réponse attendue: {"message": "Hello World"}

# Vérifier l'identité Al Sâdika
curl http://votre-ip:8001/api/kernel/memory | jq '.memory.identity'
# Doit contenir le nom "Al Sâdika (الصادقة / الصديقة)"
```

### 2. Configuration APK
**Dans l'application Al Sâdika** :
1. **Ouvrir** Paramètres (icône ⚙️)
2. **Appuyer** sur "Al Sâdika" (bouton violet)
3. **Aller** dans "Serveur Backend"
4. **Saisir** l'URL : `https://votre-domaine.com` ou `http://votre-ip:8001`
5. **Appuyer** sur "Tester la connexion"

### 3. Validation Automatique
L'APK effectue automatiquement :
- ✅ Test de connectivité réseau
- ✅ Vérification HTTPS/HTTP
- ✅ Test CORS Capacitor
- ✅ Validation identité Al Sâdika
- ✅ Test streaming SSE

**Indicateurs visuels** :
- 🟢 **Vert** : Appairage réussi
- 🟡 **Orange** : Connexion OK, problème configuration
- 🔴 **Rouge** : Échec de connexion

---

## 🔐 MÉTHODES D'AUTHENTIFICATION

### Méthode 1 : URL Simple (Recommandée)
```
Configuration APK: https://votre-domaine.com
Configuration Backend CORS: capacitor://localhost
```

### Méthode 2 : Clé API (Sécurité renforcée)
```bash
# Dans .env backend
API_KEY_HEADER=X-AlSadika-Key
API_KEY_VALUE=votre_cle_secrete_unique_123

# Dans APK
URL: https://votre-domaine.com
Clé API: votre_cle_secrete_unique_123
```

### Méthode 3 : QR Code (Futur v1.1)
```
Backend génère QR code contenant:
- URL sécurisée  
- Clé temporaire
- Configuration CORS
APK scanne → Appairage automatique
```

---

## 🌐 CONFIGURATION RÉSEAU

### CORS pour Capacitor
**Dans votre `.env` backend** :
```bash
# Obligatoire pour les APK Capacitor
CORS_ORIGINS=capacitor://localhost,https://votre-domaine.com,http://localhost:3000

# Si accès depuis navigateur aussi
CORS_ORIGINS=capacitor://localhost,https://votre-domaine.com,http://localhost:3000,http://votre-ip:8001
```

### Headers Sécurisés
```bash
# Configuration nginx (si utilisé)
add_header Access-Control-Allow-Origin "capacitor://localhost";
add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS";
add_header Access-Control-Allow-Headers "Content-Type, Authorization, X-AlSadika-Key";
```

---

## 🔧 DÉPANNAGE APPAIRAGE

### Erreur "Connexion refusée"
```bash
# Vérifications
1. Backend démarré: docker-compose ps
2. Port accessible: netstat -ln | grep 8001
3. Firewall: ufw allow 8001
4. DNS: ping votre-domaine.com
```

### Erreur CORS
```bash
# Symptôme: Connexion OK depuis curl, KO depuis APK
# Solution: Vérifier CORS_ORIGINS dans .env
CORS_ORIGINS=capacitor://localhost

# Redémarrer backend après modification
docker-compose restart alsadika-backend
```

### Erreur "Identité Al Sâdika non trouvée"
```bash
# Vérifier configuration kernel
curl http://votre-ip:8001/api/kernel/memory | jq '.memory.identity.name'

# Si vide, réinjecter l'identité
curl -X POST http://votre-ip:8001/api/kernel/memory/approve \
  -H "Content-Type: application/json" \
  -d '{"key": "identity", "value": {"name": "Al Sâdika (الصادقة / الصديقة)"}}'
```

### Erreur SSL/HTTPS
```bash
# Pour domaine avec certificat SSL
1. Vérifier certificat valide: openssl s_client -connect votre-domaine.com:443
2. Renouveler si expiré: certbot renew
3. Redémarrer nginx: docker-compose restart nginx

# Pour IP sans SSL (développement uniquement)
URL APK: http://votre-ip:8001 (sans 's')
```

---

## 📱 APPAIRAGE MULTIPLE

### Plusieurs Appareils
Chaque APK peut être appairée au même backend :
```bash
# APK 1 (téléphone principal)
Session ID: phone-main-xxx

# APK 2 (tablette)  
Session ID: tablet-xxx

# APK 3 (téléphone secondaire)
Session ID: phone-secondary-xxx
```

**Avantages** :
- Historique partagé entre appareils
- Configuration centralisée
- Synchronisation automatique

### Isolation par Utilisateur (Futur)
```bash
# Configuration multi-utilisateurs (v1.2)
URL: https://votre-domaine.com/user/brahim
URL: https://votre-domaine.com/user/famille  
URL: https://votre-domaine.com/user/invites
```

---

## 🔄 MIGRATION & SAUVEGARDE

### Changement de Serveur Backend
```bash
# 1. Exporter configuration actuelle
APK → Paramètres → Données → Exporter Config

# 2. Configurer nouveau backend avec même identité Al Sâdika  
# 3. Changer URL dans APK
# 4. Réimporter configuration

# 5. Vérifier appairage
Test connexion → 🟢 Vert
```

### Sauvegarde Appairage
```json
// Fichier: alsadika-pairing-backup.json
{
  "backend_url": "https://votre-domaine.com",
  "api_key": "votre_cle_si_applicable",
  "cors_origin": "capacitor://localhost",
  "identity_hash": "sha256_de_lidentite_alsadika",
  "created_at": "2025-08-26T10:00:00Z"
}
```

---

## ✅ TESTS DE VALIDATION

### Checklist Appairage Réussi
- [ ] **URL backend** accessible depuis APK
- [ ] **Test connexion** 🟢 vert
- [ ] **Identité Al Sâdika** confirmée  
- [ ] **Premier message** envoyé et réponse reçue
- [ ] **Mode hors ligne** fonctionnel
- [ ] **Reconnaissance vocale** opérationnelle
- [ ] **Synthèse vocale** avec voix Al Sâdika

### Commandes de Test
```bash
# Test complet depuis APK
1. "Bonjour Al Sâdika, qui es-tu ?"
   → Doit répondre avec identité complète

2. "Peux-tu me parler d'OpenAI ?"  
   → Brand scrubbing : aucune mention "OpenAI"

3. Mode hors ligne → "Résume ce que tu sais"
   → Doit répondre sans internet

4. Reconnaissance vocale → "Test microphone"
   → Transcription correcte

5. Synthèse vocale activée
   → Al Sâdika parle ses réponses
```

---

## 📞 SUPPORT APPAIRAGE

### Auto-Diagnostic
**APK** → **Paramètres** → **Diagnostics** → **Test Complet**
- Rapport détaillé des problèmes
- Export automatique des logs
- Solutions suggérées

### Logs Backend
```bash
# Connexions APK dans les logs
docker-compose logs alsadika-backend | grep "capacitor"

# Erreurs CORS
docker-compose logs alsadika-backend | grep "CORS"

# Tests de connexion
docker-compose logs alsadika-backend | grep "kernel/memory"
```

**🎉 Appairage réussi = Al Sâdika souveraine et sécurisée !**