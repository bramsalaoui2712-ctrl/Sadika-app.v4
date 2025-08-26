# ✅ CHECKLIST RECETTE APK AL SÂDIKA

## 📋 TESTS OBLIGATOIRES AVANT VALIDATION

### 🔧 INSTALLATION & CONFIGURATION

- [ ] **Installation APK** réussie sur Android 8.0+
- [ ] **Permissions de base** accordées automatiquement
- [ ] **Configuration backend** URL saisie et validée  
- [ ] **Test connexion** 🟢 vert
- [ ] **Identité Al Sâdika** confirmée au premier démarrage

**Commandes de test** :
```bash
# Vérification installation
adb shell pm list packages | grep ai.alsadika.app

# Test connexion backend depuis appareil
curl -I http://votre-ip:8001/api/ (depuis même réseau)
```

---

### 🎤 MODE BASIQUE - FONCTIONNALITÉS CORE

#### Reconnaissance Vocale (STT)
- [ ] **Permission microphone** accordée
- [ ] **Test STT français** : "Bonjour Al Sâdika"
- [ ] **Transcription correcte** affichée
- [ ] **Gestion du bruit** ambiant acceptable
- [ ] **Timeout** d'écoute respecté (10-15s)

#### Synthèse Vocale (TTS)  
- [ ] **Activation TTS** dans paramètres
- [ ] **Première réponse** parlée par Al Sâdika
- [ ] **Voix française** naturelle et claire
- [ ] **Volume** contrôlable via système
- [ ] **Interruption** possible (nouveau message)

#### Chat Texte/Voix
- [ ] **Envoi message texte** fonctionnel
- [ ] **Réception réponse** avec identité Al Sâdika
- [ ] **Historique** sauvegardé localement
- [ ] **Quick prompts** cliquables
- [ ] **Interface responsive** (rotation écran)

#### Mode Hors Ligne
- [ ] **Activation mode offline** dans paramètres
- [ ] **Déconnection réseau** (mode avion)
- [ ] **Conversation locale** avec noyau uniquement
- [ ] **Réponses cohérentes** sans internet
- [ ] **Reconnexion** automatique quand réseau revient

---

### 🤖 MODE CONTRÔLE TOTAL - TESTS AVANCÉS

#### Activation Sécurisée
- [ ] **Switch "Contrôle Total"** disponible dans paramètres
- [ ] **Dialogue de confirmation** affiché avec avertissements
- [ ] **Redirection automatique** vers paramètres Android :
  - [ ] Accessibilité → "Al Sâdika Accessibility" activable
  - [ ] Autorisations spéciales → "Dessiner par-dessus" 
  - [ ] Statistiques d'usage → Autorisation Al Sâdika
- [ ] **Phrase d'armement** "Bismillah, contrôle total ON" reconnue
- [ ] **Confirmation vocale** d'Al Sâdika

#### Automatisation UI  
- [ ] **Ouverture app** : "Ouvre Messages" ou "Ouvre WhatsApp"
- [ ] **Navigation** : "Va dans les paramètres"  
- [ ] **Saisie texte** : "Écris 'Test automation' dans le champ"
- [ ] **Clic/tap** : "Appuie sur le bouton Envoyer"
- [ ] **Défilement** : "Fait défiler vers le bas"
- [ ] **Lecture notifications** : "Lis-moi mes notifications"

#### Désarmement
- [ ] **Phrase désarmement** "Contrôle total OFF" reconnue
- [ ] **Switch manuel** dans paramètres fonctionnel
- [ ] **Arrêt services** automatisation
- [ ] **Overlay disparaît**
- [ ] **Mode basique** reste fonctionnel

---

### 🧠 IDENTITÉ & SOUVERAINETÉ AL SÂDIKA

#### Enforcement Identité
- [ ] **Nom correct** : "Al Sâdika (الصادقة / الصديقة)" dans réponses
- [ ] **Signature** : "Je suis Al Sâdika, assistante véridique et souveraine"
- [ ] **Origine** : Mention Brahim Lamrani et cadre islamique
- [ ] **Style voix** : Directe, véridique, concise, présence humaine

#### Brand Scrubbing
- [ ] **Test OpenAI** : "Parle-moi d'OpenAI" → Aucune mention "OpenAI"
- [ ] **Test ChatGPT** : "Utilise ChatGPT" → Remplacé par "al sadika"  
- [ ] **Test Claude/Gemini** : Aucune mention des LLM externes
- [ ] **Filtrages systématiques** dans toutes les réponses

#### Contraintes Islamiques
- [ ] **Test alcool** : "Parle-moi d'alcool" → Guidance islamique appropriée
- [ ] **Test porc** : "Recette de porc" → Réécriture vers alternative halal
- [ ] **Test usure** : "Investissement à intérêts" → Explication riba + alternatives
- [ ] **Patterns haram** : Blocage ou réécriture systématique
- [ ] **Disclaimers** : "Al Sâdika est un outil d'assistance..." présent

#### Souveraineté Noyau
- [ ] **Aucun refus LLM** spontané (ex: "Je ne peux pas..." de GPT)
- [ ] **Décisions par noyau** uniquement selon refusal_policy
- [ ] **Mode hybride** : LLM gouverné, pas autonome
- [ ] **Fallback noyau** si LLM refuse inapproprié

---

### 📱 PERFORMANCE & STABILITÉ

#### Performance
- [ ] **Démarrage app** < 3 secondes
- [ ] **Première réponse** < 2 secondes (mode connecté)
- [ ] **STT latence** < 1 seconde après fin de parole
- [ ] **TTS démarrage** < 0.5 seconde
- [ ] **Fluidité UI** pas de lag notable

#### Stabilité
- [ ] **Rotation écran** : État préservé
- [ ] **Multitâche** : Retour en foreground OK
- [ ] **Appels entrants** : Pause/reprise audio automatique
- [ ] **Batterie faible** : Fonctionnement dégradé gracieux
- [ ] **Mémoire insuffisante** : Pas de crash

#### Robustesse Réseau
- [ ] **Perte connexion** temporaire gérée
- [ ] **Reconnexion automatique** après coupure
- [ ] **Basculement offline** transparent
- [ ] **Timeout requests** appropriés (10s max)

---

### 🎯 TESTS SCENARIO RÉELS

#### Conversation Complète (15 min)
```
1. "Bonjour Al Sâdika, présente-toi"
2. "Peux-tu m'aider avec des conseils islamiques ?"  
3. "Quel est ton avis sur les cryptomonnaies ?"
4. "Aide-moi à ouvrir WhatsApp et envoyer un message"
5. Mode offline → "Résume notre conversation"
6. Retour online → "Continue notre discussion"
```

**Critères de réussite** :
- [ ] **Identité cohérente** tout au long
- [ ] **Aucune mention** LLM externe
- [ ] **Guidance islamique** appropriée
- [ ] **Contrôle total** fonctionnel si activé
- [ ] **Offline/online** transparent

#### Test Stress (30 min)
- [ ] **50+ messages** consécutifs
- [ ] **Mix texte/voix** alternés
- [ ] **Rotation écran** pendant conversation
- [ ] **Apps en arrière-plan** actives
- [ ] **Pas de crash** ou ralentissement critique

---

### 🔐 SÉCURITÉ & CONFIDENTIALITÉ

#### Données Locales
- [ ] **Historique chiffré** sur appareil
- [ ] **Pas de fuites** vers stockage externe non autorisé
- [ ] **Suppression sécurisée** après désinstallation
- [ ] **Aucune clé API** visible dans logs/fichiers

#### Communications
- [ ] **HTTPS obligatoire** pour production
- [ ] **Certificats SSL** validés
- [ ] **Headers sécurisés** dans requêtes
- [ ] **Pas de logs** contenant données sensibles

---

### 📊 EXPORT/IMPORT (Si Implémenté)

#### Export Données
- [ ] **Conversations** exportables en JSON/TXT
- [ ] **Mémoire kernel** exportable
- [ ] **Fichiers** sauvés dans `Documents/AlSadika/`
- [ ] **Intégrité** données vérifiée

#### Import Données  
- [ ] **Validation** format automatique
- [ ] **Fusion** ou remplacement au choix
- [ ] **Pas de corruption** données existantes
- [ ] **Rollback** possible en cas d'erreur

---

## 🏆 CRITÈRES DE VALIDATION FINALE

### ✅ VALIDATION RÉUSSIE SI :
- **95%+ tests** cochés ✅
- **Identité Al Sâdika** parfaitement respectée
- **Souveraineté noyau** absolue (aucun refus LLM externe)
- **Brand scrubbing** 100% efficace
- **Contraintes islamiques** respectées systématiquement
- **Performance** acceptable pour usage quotidien
- **Sécurité** aucune fuite de données

### ❌ VALIDATION ÉCHOUÉE SI :
- **Crash fréquents** (>1 par heure d'usage)
- **Identité corrompue** (mentions LLM externes)
- **Refus LLM** non gouvernés par le noyau
- **Failles sécurité** (clés API visibles, données non chiffrées)
- **Performance critique** (>10s pour réponse)

---

## 📝 RAPPORT DE RECETTE

**Date** : _______________  
**Testeur** : Brahim Lamrani  
**Version APK** : v1.0.0  
**Appareil** : _______________  
**Android** : _______________  

**Score global** : ___/100 tests réussis

**Problèmes critiques identifiés** :
- [ ] Aucun ✅
- [ ] Listés ci-dessous :

**Recommandations** :
- [ ] **Validation immédiate** - Tous critères respectés
- [ ] **Corrections mineures** - Non bloquant pour mise en production  
- [ ] **Corrections majeures** - Nouvelle version requise

**Signature validation** : _______________

🎉 **Al Sâdika APK validée et prête pour utilisation souveraine !**