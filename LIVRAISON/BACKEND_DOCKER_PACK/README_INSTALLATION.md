# 🚀 AL SÂDIKA BACKEND - GUIDE D'INSTALLATION AUTO-HÉBERGÉ

## 📋 PRÉREQUIS

### Système Recommandé
- **OS** : Linux (Ubuntu/Debian/CentOS) ou macOS
- **RAM** : 2GB minimum, 4GB recommandé
- **Stockage** : 10GB libres minimum
- **Processeur** : 2 cœurs minimum

### Logiciels Requis
- **Docker** : Version 20.10+ ([installer](https://docs.docker.com/get-docker/))
- **Docker Compose** : Version 2.0+ (inclus avec Docker Desktop)
- **Ports libres** : 8001 (backend), 27017 (MongoDB), 80/443 (nginx optionnel)

---

## 🔧 INSTALLATION RAPIDE

### 1. Préparation
```bash
# Télécharger le package Al Sâdika
wget https://releases.alsadika.com/backend-docker-pack-v1.0.0.tar.gz
tar -xzf backend-docker-pack-v1.0.0.tar.gz
cd alsadika-backend/

# OU cloner depuis votre dépôt
git clone https://github.com/votre-username/alsadika-backend.git
cd alsadika-backend/
```

### 2. Configuration
```bash
# Copier le fichier de configuration
cp .env.example .env

# Éditer avec vos paramètres
nano .env
```

**⚠️ OBLIGATOIRE** : Modifiez ces variables dans `.env` :
```bash
# Sécurité
MONGO_ROOT_PASSWORD=votre_mot_de_passe_securise_123
JWT_SECRET=votre_cle_jwt_aleatoire_unique

# Réseau (remplacez par votre domaine/IP)
CORS_ORIGINS=https://votre-domaine.com,http://votre-ip:8001
ALLOWED_HOSTS=votre-domaine.com,votre-ip

# LLM (pour mode hybride)
EMERGENT_LLM_KEY=votre_cle_emergent_universelle
```

### 3. Démarrage
```bash
# Démarrage des services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f

# Vérifier le statut
docker-compose ps
```

### 4. Vérification
```bash
# Test santé backend
curl http://votre-ip:8001/api/

# Test identité Al Sâdika
curl http://votre-ip:8001/api/kernel/memory
```

---

## 🔧 CONFIGURATION AVANCÉE

### Domaine Custom avec HTTPS
```bash
# Activer nginx avec certificats SSL
cp nginx.conf.example nginx.conf
mkdir -p ssl/

# Ajouter vos certificats SSL
cp votre-certificat.crt ssl/
cp votre-cle-privee.key ssl/

# Démarrer avec proxy
docker-compose --profile proxy up -d
```

### Cache Redis (Performance)
```bash
# Activer Redis pour mise en cache
docker-compose --profile cache up -d

# Vérifier Redis
docker exec alsadika-redis redis-cli ping
```

---

## 📊 SURVEILLANCE

### Logs Système
```bash
# Logs backend
docker-compose logs alsadika-backend

# Logs MongoDB
docker-compose logs mongodb

# Logs en temps réel
docker-compose logs -f --tail=100
```

### Métriques Santé
```bash
# Statut des conteneurs
docker-compose ps

# Utilisation ressources
docker stats

# Espace disque
df -h volumes/
```

### Endpoints de Monitoring
- **Santé** : `GET /api/`
- **Métriques** : `GET /api/metrics`
- **Statut kernel** : `GET /api/kernel/status`

---

## 🔐 SÉCURITÉ

### Recommandations Production
1. **Changez tous les mots de passe** par défaut
2. **Limitez l'accès réseau** (firewall, VPN)
3. **Activez HTTPS** avec certificats valides
4. **Mettez à jour régulièrement** les images Docker
5. **Surveillez les logs** pour détecter intrusions

### Sauvegarde
```bash
# Sauvegarde MongoDB
docker exec alsadika-mongodb mongodump --out /backup/$(date +%Y%m%d)

# Sauvegarde volumes
tar -czf backup-alsadika-$(date +%Y%m%d).tar.gz volumes/

# Sauvegarde configuration
cp .env backup-env-$(date +%Y%m%d)
```

---

## 🔄 MAINTENANCE

### Mise à Jour
```bash
# Arrêter les services
docker-compose down

# Sauvegarder
tar -czf backup-pre-update-$(date +%Y%m%d).tar.gz volumes/ .env

# Télécharger nouvelle version
wget https://releases.alsadika.com/backend-docker-pack-v1.0.1.tar.gz

# Mettre à jour et redémarrer
docker-compose pull
docker-compose up -d
```

### Redémarrage Services
```bash
# Redémarrer tout
docker-compose restart

# Redémarrer backend uniquement
docker-compose restart alsadika-backend

# Redémarrer MongoDB uniquement
docker-compose restart mongodb
```

---

## 🌐 APPAIRAGE APK

### Configuration APK → Backend
1. **Dans l'APK Al Sâdika** : Paramètres → Serveur
2. **URL Backend** : `https://votre-domaine.com` ou `http://votre-ip:8001`
3. **Test connexion** : L'APK teste automatiquement
4. **Validation** : Identité Al Sâdika confirmée

### Résolution Problèmes Connexion
```bash
# Vérifier connectivité
curl -I http://votre-ip:8001/api/

# Vérifier CORS
curl -H "Origin: capacitor://localhost" http://votre-ip:8001/api/

# Logs connexions APK
docker-compose logs alsadika-backend | grep "capacitor"
```

---

## ❌ DÉPANNAGE

### Problèmes Courants

**Backend ne démarre pas**
```bash
# Vérifier les logs
docker-compose logs alsadika-backend

# Vérifier la configuration
docker-compose config

# Tester manuellement
docker run --rm -it alsadika-backend python -c "import server; print('OK')"
```

**MongoDB inaccessible**
```bash
# Vérifier statut
docker-compose ps mongodb

# Tester connexion
docker exec alsadika-mongodb mongosh --eval "db.adminCommand('ping')"

# Réinitialiser données (ATTENTION: perte de données)
docker-compose down -v
docker-compose up -d
```

**APK ne se connecte pas**
```bash
# Vérifier CORS dans .env
CORS_ORIGINS=capacitor://localhost,http://localhost,https://votre-domaine.com

# Redémarrer après changement CORS
docker-compose restart alsadika-backend
```

### Support
- **Logs détaillés** : `docker-compose logs --details`
- **Configuration** : Vérifiez `.env` et `docker-compose.yml`
- **Réseau** : Testez connectivité `curl` et `ping`

---

## 📞 CONTACT & SUPPORT

**Documentation** : Voir `/DOCUMENTATION/`  
**Tests** : Voir `/TESTS_RECETTE/`  
**Configurations** : Voir `/CONFIGS_ANDROID/`

🎉 **Félicitations ! Votre Al Sâdika est auto-hébergée et souveraine !**