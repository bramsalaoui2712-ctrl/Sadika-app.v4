# Instructions de Construction APK - Al Sâdika

## Prérequis

### 1. Environnement de développement
- **Node.js** 18+ : [https://nodejs.org](https://nodejs.org)
- **Yarn** : `npm install -g yarn`
- **Android Studio** : [https://developer.android.com/studio](https://developer.android.com/studio)

### 2. Configuration Android SDK
```bash
# Installer Android SDK via Android Studio
# Ou via ligne de commande (Linux/macOS):
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/tools/bin

# SDK Platform requis: Android API 30+
# Build Tools: 30.0.3+
```

### 3. Variables d'environnement
```bash
# Ajouter au ~/.bashrc ou ~/.zshrc
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/tools/bin
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
```

## Construction APK

### Méthode 1: Script automatique
```bash
# À la racine du projet
chmod +x BUILD_APK.sh
./BUILD_APK.sh
```

### Méthode 2: Construction manuelle
```bash
cd frontend

# 1. Installer dépendances
yarn install

# 2. Build React
yarn build

# 3. Synchroniser Capacitor
npx cap sync android

# 4. Construire APK
cd android
./gradlew assembleRelease

# APK créé dans: app/build/outputs/apk/release/app-release.apk
```

## Signature APK (Optionnel)

### 1. Créer une clé de signature
```bash
keytool -genkey -v -keystore alsadika-release-key.keystore \
  -name alsadika -keyalg RSA -keysize 2048 -validity 10000
```

### 2. Configurer Gradle
Éditer `frontend/android/app/build.gradle`:
```gradle
android {
    signingConfigs {
        release {
            keyAlias 'alsadika'
            keyPassword 'votre_password'
            storeFile file('alsadika-release-key.keystore')
            storePassword 'votre_password'
        }
    }
    buildTypes {
        release {
            signingConfig signingConfigs.release
        }
    }
}
```

### 3. Construire APK signée
```bash
cd frontend/android
./gradlew assembleRelease
```

## Vérification APK

### 1. Vérifier intégrité
```bash
# Dans LIVRAISON/APK/
sha256sum al-sadika-v1.0.0-release.apk
# Comparer avec le fichier .sha256
```

### 2. Analyser APK (optionnel)
```bash
# Installer aapt (Android Asset Packaging Tool)
aapt dump badging al-sadika-v1.0.0-release.apk
```

## Installation sur Android

### 1. Activer sources inconnues
- Android 8+ : **Paramètres** → **Sécurité** → **Sources inconnues**
- Android 7- : **Paramètres** → **Sécurité** → **Autoriser les sources inconnues**

### 2. Installer APK
```bash
# Via ADB (USB debugging activé)
adb install al-sadika-v1.0.0-release.apk

# Ou copier le fichier APK sur l'appareil et l'ouvrir
```

## Dépannage

### Erreur Gradle
```bash
cd frontend/android
./gradlew clean
./gradlew assembleRelease --debug
```

### Erreur SDK
```bash
# Vérifier SDK Manager
android list sdk --extended
android update sdk --no-ui --all
```

### Erreur Capacitor
```bash
cd frontend
npx cap doctor
npx cap sync android --force
```

## Compatibilité

- **Android minimum** : 7.0 (API 24)
- **Android cible** : 13.0 (API 33)
- **Architectures** : ARM64, x86_64
- **Taille APK** : ~15-25 MB
- **Permissions** : Internet, Microphone, Wake Lock

---

**Note** : Cette APK est auto-signée et nécessite l'activation des "sources inconnues" sur Android. Pour distribution publique, utilisez Google Play Store ou autre store officiel.