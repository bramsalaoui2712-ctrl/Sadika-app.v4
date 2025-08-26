#!/bin/bash
# Script de construction APK pour Al Sâdika
# Requis: Android SDK, Capacitor CLI, Node.js, Yarn

set -e

echo "🚀 Construction APK Al Sâdika v1.0.0"
echo "======================================"

# Vérifications préalables
if ! command -v npx &> /dev/null; then
    echo "❌ NPX non trouvé. Installez Node.js"
    exit 1
fi

if ! command -v yarn &> /dev/null; then
    echo "❌ Yarn non trouvé. Installez Yarn"
    exit 1
fi

cd frontend

echo "📦 Installation des dépendances..."
yarn install

echo "🔨 Construction du build React..."
yarn build

echo "📱 Synchronisation Capacitor..."
npx cap sync android

echo "🏗️ Construction APK..."
cd android
if command -v gradlew &> /dev/null; then
    ./gradlew assembleRelease
elif command -v gradle &> /dev/null; then
    gradle assembleRelease
else
    echo "❌ Gradle non trouvé. Installez Android SDK avec Gradle"
    exit 1
fi

APK_PATH="app/build/outputs/apk/release/app-release.apk"
if [ -f "$APK_PATH" ]; then
    echo "✅ APK créé avec succès!"
    
    # Copier vers LIVRAISON
    mkdir -p ../../../LIVRAISON/APK
    cp "$APK_PATH" "../../../LIVRAISON/APK/al-sadika-v1.0.0-release.apk"
    
    # Générer SHA256
    cd ../../../LIVRAISON/APK
    APK_SIZE=$(stat -c%s "al-sadika-v1.0.0-release.apk")
    APK_SHA=$(sha256sum "al-sadika-v1.0.0-release.apk" | cut -d' ' -f1)
    
    cat > al-sadika-v1.0.0-release.apk.sha256 << EOF
# CHECKSUM AL SÂDIKA APK v1.0.0
# Vérification intégrité fichier APK

# Pour vérifier :
# sha256sum al-sadika-v1.0.0-release.apk
# Comparer avec la valeur ci-dessous

FICHIER: al-sadika-v1.0.0-release.apk
SHA256: $APK_SHA
TAILLE: $(($APK_SIZE / 1024 / 1024))MB ($APK_SIZE bytes)
DATE: $(date +%Y-%m-%d)

# IMPORTANT: 
# - Vérifiez toujours l'intégrité avant installation
# - APK auto-signée (sources inconnues requises sur Android)
# - Compatible Android 7.0+ (API 24+)
EOF
    
    echo "📋 Informations APK:"
    echo "   Fichier: al-sadika-v1.0.0-release.apk"
    echo "   Taille: $(($APK_SIZE / 1024 / 1024))MB"
    echo "   SHA256: $APK_SHA"
    
else
    echo "❌ Erreur: APK non créé"
    exit 1
fi

echo ""
echo "🎉 Construction terminée avec succès!"
echo "📁 APK disponible dans: LIVRAISON/APK/"