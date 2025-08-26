# 📱 GUIDE UTILISATION AL SÂDIKA APK

## 🚀 INSTALLATION

### 1. Téléchargement & Installation
```bash
# Télécharger l'APK depuis votre serveur
wget https://votre-domaine.com/releases/al-sadika-v1.0.0-release.apk

# Vérifier l'intégrité (optionnel)
sha256sum al-sadika-v1.0.0-release.apk
# Comparer avec le checksum fourni
```

**Sur Android** :
1. **Activer** "Sources inconnues" dans Paramètres → Sécurité
2. **Ouvrir** le fichier APK téléchargé
3. **Suivre** l'assistant d'installation
4. **Accepter** les permissions de base

### 2. Premier Démarrage
1. **Ouvrir** Al Sâdika
2. **Configurer** l'URL de votre backend
3. **Tester** la connexion
4. **Valider** l'identité Al Sâdika

---

## ⚙️ CONFIGURATION SERVEUR

### Connection Backend
**Paramètres** → **Serveur** → **URL Backend**
```
Format: https://votre-domaine.com
   ou: http://votre-ip:8001
```

**Test de connexion** :
- ✅ Vert : Backend accessible, identité Al Sâdika confirmée
- ❌ Rouge : Problème de connexion ou configuration

### Mode Hors Ligne
**Paramètres** → **Al Sâdika** → **Mode hors ligne**
- ✅ **ON** : Fonctionne sans internet (noyau local)
- ❌ **OFF** : Nécessite connexion backend

---

## 🎤 MODE BASIQUE

### Chat Texte
1. **Saisir** votre message dans la zone de texte
2. **Appuyer** sur "Envoyer" ou ⏎
3. **Recevoir** la réponse d'Al Sâdika

### Reconnaissance Vocale (STT)
1. **Appuyer** sur l'icône microphone 🎤
2. **Parler** clairement en français
3. **Arrêter** automatiquement ou appuyer sur ⏹️
4. **Envoyer** le texte transcrit

### Synthèse Vocale (TTS)
**Paramètres** → **Voix** → **Activer TTS**
- Al Sâdika **parle** ses réponses à voix haute
- **Volume** contrôlé par les paramètres système
- **Langue** : Français optimisé

### Écoute Continue (Hot Mic)
**Paramètres** → **Al Sâdika** → **Écoute continue**
- ✅ **ON** : Service en arrière-plan, notification persistante
- ❌ **OFF** : Écoute manuelle uniquement
- **Arrêt d'urgence** : "Couper micro" depuis la notification

---

## 🤖 MODE CONTRÔLE TOTAL

### ⚠️ Activation Sécurisée

**Prérequis** : Comprendre les implications
- Al Sâdika peut **automatiser** votre téléphone
- **Accès complet** aux applications et données
- **Responsabilité utilisateur** pour les actions

**Procédure d'activation** :
1. **Paramètres** → **Al Sâdika** → **Contrôle Total** → **ON**
2. **Confirmer** la dialogue de sécurité
3. **Redirection automatique** vers paramètres Android :
   - **Accessibilité** → Activer "Al Sâdika Accessibility"
   - **Autorisations spéciales** → "Dessiner par-dessus"
   - **Statistiques d'usage** → Autoriser Al Sâdika

### Phrase d'Armement
**Défaut** : "Bismillah, contrôle total ON"
- **Personnalisable** dans Paramètres → Phrases
- **Obligatoire** pour activer le contrôle
- **Confirmation vocale** d'Al Sâdika

### Capacités Contrôle Total
- ✅ **Ouvrir applications** : "Ouvre WhatsApp"
- ✅ **Saisir du texte** : "Écris 'Bonjour' dans le champ"
- ✅ **Appuyer/cliquer** : "Appuie sur le bouton Envoyer"
- ✅ **Faire défiler** : "Fait défiler vers le bas"
- ✅ **Naviguer** : "Va dans les paramètres"
- ✅ **Lire notifications** : "Lis-moi mes notifications"

### Désarmement Sécurisé
- **Phrase** : "Contrôle total OFF"
- **Switch** : Paramètres → Contrôle Total → OFF
- **Arrêt d'urgence** : Redémarrage de l'appareil

---

## 🔐 SÉCURITÉ & CONFIDENTIALITÉ

### Données Personnelles
- **Historique chat** : Stocké localement et chiffré
- **Paramètres** : Sauvegardés sur l'appareil uniquement
- **Clés API** : Aucune stockée dans l'APK (architecture zéro-clé)

### Communications
- **Backend personnel** : Toutes requêtes via votre serveur
- **Pont externe** : Contrôlable (ON/OFF) selon vos préférences
- **Chiffrement** : HTTPS obligatoire pour communications réseau

### Permissions Graduelles
**Automatiques** :
- INTERNET, RECORD_AUDIO, WAKE_LOCK

**Sur demande** :
- FOREGROUND_SERVICE (écoute continue)
- ACCESSIBILITY_SERVICE (contrôle total)
- SYSTEM_ALERT_WINDOW (overlay)
- PACKAGE_USAGE_STATS (contexte apps)

---

## 📊 EXPORT & IMPORT

### Export Conversations
**Paramètres** → **Données** → **Exporter Conversations**
- Format : JSON ou TXT
- Destination : `Documents/AlSadika/exports/`
- **Inclut** : Messages, timestamps, métadonnées

### Export Mémoire Kernel
**Paramètres** → **Al Sâdika** → **Exporter Mémoire**
- Format : `approved_memory.json`
- **Contient** : Identité, contraintes, règles approuvées
- **Usage** : Sauvegarde ou migration

### Import Configuration
**Paramètres** → **Données** → **Importer**
- **Types supportés** : Conversations, mémoire kernel
- **Validation** : Vérification intégrité automatique
- **Fusion** : Option de fusion ou remplacement

---

## 🔧 DÉPANNAGE

### Problèmes Connexion Backend
**Symptôme** : ❌ Rouge dans test connexion
```bash
# Vérifications
1. URL correcte (https:// ou http://)
2. Backend démarré et accessible
3. CORS configuré pour "capacitor://localhost"
4. Pas de proxy/firewall bloquant
```

### Reconnaissance Vocale Défaillante
**Symptôme** : STT ne fonctionne pas
```bash
# Solutions
1. Vérifier permission RECORD_AUDIO accordée
2. Tester microphone dans autres apps
3. Vérifier langue système = français
4. Redémarrer app si nécessaire
```

### Contrôle Total Inactif
**Symptôme** : Commandes ignorées
```bash
# Vérifications
1. Service accessibilité activé dans Android
2. Phrase d'armement correctement prononcée
3. Applications cibles installées et accessibles
4. Pas de conflit avec autres apps d'automation
```

### Performance Dégradée
**Symptôme** : App lente ou plantages
```bash
# Optimisations
1. Vider cache : Paramètres → Stockage → Vider cache
2. Redémarrer app complètement
3. Vérifier RAM disponible (>1GB recommandé)
4. Désactiver autres apps en arrière-plan
```

---

## 📈 UTILISATION AVANCÉE

### Commandes Vocales Optimisées
```bash
# Navigation
"Va sur Google Maps"
"Ouvre mes messages"
"Affiche les paramètres"

# Saisie
"Écris 'Je serai en retard'"
"Cherche 'restaurant halal'"
"Dicte ce message : [votre texte]"

# Actions
"Appuie sur Envoyer"
"Fait défiler jusqu'en bas"
"Retourne à l'accueil"

# Contrôle app
"Ferme cette application"
"Passe à l'app suivante"
"Active le mode avion"
```

### Raccourcis Utiles
- **Double tap** sur message : Répéter en voix
- **Pression longue** sur microphone : Écoute continue temporaire
- **Secouer** l'appareil : Arrêt d'urgence voix
- **Volume +/-** pendant TTS : Ajuster volume voix

### Personnalisation Avancée
**Paramètres** → **Al Sâdika** → **Avancé**
```
- Timeout écoute : 5-30 secondes
- Seuil de bruit : Bas/Moyen/Élevé
- Phrases d'activation personnalisées
- Réponses contextuelles (lieu, heure)
- Journal actions contrôle total
```

---

## 📞 SUPPORT

### Logs de Diagnostic
**Paramètres** → **Diagnostics** → **Exporter Logs**
- Utile pour dépannage
- Pas de données personnelles
- Format : `.log` horodaté

### Auto-Diagnostic
**Paramètres** → **Diagnostics** → **Test Complet**
- Vérification permissions
- Test connexion backend
- Validation identité Al Sâdika
- Contrôle plugins natifs

### Reset Complet
**Paramètres** → **Données** → **Reset Application**
- ⚠️ **Efface** toutes les données locales
- **Conserve** : Configuration serveur
- **Nécessite** : Nouvelle configuration

---

**🎉 Profitez de votre Al Sâdika souveraine et sécurisée !**