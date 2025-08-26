# 🚀 INSTRUCTIONS BUILD APK AL SÂDIKA

## 📋 ÉTAPES POUR GÉNÉRER L'APK

### 1. Créer le Repo GitHub
```bash
# Sur GitHub.com :
1. Créer nouveau repo "alsadika-app"
2. Rendre privé ou public selon préférence
3. Ne pas initialiser avec README (on a déjà tout)
```

### 2. Upload du Code
```bash
# Depuis votre machine :
cd /path/to/ALSADIKA_GITHUB_READY/
git init
git remote add origin https://github.com/VOTRE_USERNAME/alsadika-app.git
git add .
git commit -m "Initial Al Sadika project with GitHub Actions"
git push -u origin main
```

### 3. Déclencher le Build APK
```bash
# Option A : Push automatique (déjà fait à l'étape 2)
# Option B : Manuel
1. Aller sur GitHub → votre repo → Actions tab
2. Cliquer "Build Al Sadika APK"
3. Cliquer "Run workflow" → "Run workflow"
```

### 4. Attendre la Génération (10-15 minutes)
```bash
# Le workflow va :
1. Setup Android SDK
2. Install Node.js + yarn dependencies  
3. Build React production
4. Sync Capacitor Android
5. Build APK release
6. Générer checksum SHA256
7. Upload comme artifact
```

### 5. Télécharger l'APK
```bash
# Une fois le build ✅ réussi :
1. Actions tab → cliquer sur le build réussi
2. Scroll down → "Artifacts" section  
3. Télécharger "al-sadika-apk"
4. Extraire le zip → vous avez :
   - al-sadika-v1.0.0-release.apk
   - al-sadika-v1.0.0-release.apk.sha256
```

## 🔧 TROUBLESHOOTING

### Si le Build Échoue
```bash
# Vérifier :
1. Actions tab → cliquer sur le build rouge
2. Voir les logs détaillés
3. Erreurs communes :
   - Dépendances manquantes → Réessayer  
   - Permissions Gradle → Déjà fixé dans workflow
   - Mémoire insuffisante → GitHub Actions a assez
```

### Build Prend Trop de Temps
```bash
# Normal :
- Premier build : 10-15 minutes (téléchargement SDK)
- Builds suivants : 5-8 minutes (cache)
```

## ✅ VÉRIFICATION APK

### Une Fois l'APK Téléchargée
```bash
# Vérifier l'intégrité :
sha256sum al-sadika-v1.0.0-release.apk
# Comparer avec le .sha256 fourni

# Installer sur Android :
1. Activer "Sources inconnues"
2. Transférer APK sur téléphone
3. Installer depuis gestionnaire fichiers
4. Tester "Bonjour Al Sâdika"
```

## 🎯 RÉSULTAT ATTENDU

**Après ces étapes, vous aurez** :
- ✅ `al-sadika-v1.0.0-release.apk` (installable)
- ✅ Checksum SHA256 pour vérification
- ✅ APK prête pour vos tests de recette
- ✅ Livraison complète selon vos exigences

---

**Temps total estimé : 20-30 minutes**  
**Résultat : APK finale Al Sâdika prête à installer !** 🎉