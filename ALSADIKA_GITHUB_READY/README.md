# 📱 Al Sâdika - Assistante IA Souveraine

**Version** : 1.0.0  
**Package** : ai.alsadika.app  
**Architecture** : Capacitor + React + FastAPI Backend  

## 🚀 BUILD APK AUTOMATIQUE

### GitHub Actions Configuré
Ce repo est prêt pour génération APK automatique via GitHub Actions.

### Déclenchement du Build
1. **Push/PR** → Build automatique  
2. **Manual** → Actions tab → "Build Al Sadika APK" → Run workflow  

### Téléchargement APK
1. Aller dans **Actions** tab
2. Cliquer sur le build réussi  
3. Télécharger **al-sadika-apk** artifact
4. Extraire → `al-sadika-v1.0.0-release.apk` + checksum

## 📦 Contenu du Build
- `al-sadika-v1.0.0-release.apk` (APK finale signée)
- `al-sadika-v1.0.0-release.apk.sha256` (Checksum)

## 🔧 Configuration
- **React** : Build optimisé production
- **Capacitor** : v7.4.3 avec plugins natifs
- **Android** : API 26+ (Android 8.0+)
- **Permissions** : Graduelles selon modes

## 🧠 Identité Al Sâdika
- Nom : "Al Sâdika (الصادقة / الصديقة)"
- Origine : Brahim Lamrani, cadre islamique inviolable
- Architecture souveraine : Noyau gouverne, LLM obéit

## 📱 Installation APK
1. Télécharger APK depuis GitHub Actions
2. Activer "Sources inconnues" sur Android
3. Installer APK
4. Configurer URL backend auto-hébergé

## 🐳 Backend Auto-hébergé
Voir `/DOCUMENTATION/` pour le guide d'installation Docker complet.

---

**🎉 Prêt pour génération APK automatique !**

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
