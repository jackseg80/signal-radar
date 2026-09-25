# Déploiement et exploitation de Signal Radar 4.0

## Production existante

La version 4.0 est active en observation. Avant toute mise à jour d'un serveur existant, sauvegarder la base SQLite, vérifier l'espace disque et la possibilité de retour arrière, puis tester la version candidate sur une copie isolée. Ne pas appliquer directement les instructions de première installation à une instance en service.

Le script deploy/deploy.sh n'est pas adapté à une mise à jour prudente : il exécute git reset --hard origin/master, arrête le projet compose, supprime les conteneurs orphelins et lance docker image prune -f. Ne le lancez pas sur un serveur existant sans l'avoir modifié et revu pour cet environnement.

## Première installation ou environnement de test isolé

Prérequis : Docker Compose, un clone propre du dépôt et un fichier .env local. Les variables Telegram sont optionnelles.

~~~bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:9000/api/health
~~~

Le tableau de bord écoute sur le port 9000. Conserver .env, les bases, les relevés Saxo et les sauvegardes hors du dépôt.

## Contrôles opérationnels

~~~bash
docker compose ps
docker compose logs --tail 100 scanner
docker compose logs --tail 100 api
curl http://localhost:9000/api/signals/today
~~~

Le calendrier XNYS détermine la séance source et l'ouverture cible. Yahoo est la source quotidienne principale. Nasdaq ne répare qu'une séance historique isolée si les clôtures adjacentes, l'ajustement et l'OHLC concordent. Les bougies finales manquantes et les conflits restent bloquants.

Pour recalculer la validation des titres actuellement configurés :

~~~bash
docker compose exec scanner python scripts/validate_v2.py --scope production
~~~

L'option --scope universe est un screening exploratoire et ne modifie pas la liste de production. Vérifier le rapport, les coûts et le statut d'observation avant toute décision. La confirmation Saxo est manuelle ; aucune route ne transmet d'ordre à un courtier.

## Sauvegarde et retour arrière

Faire une sauvegarde cohérente SQLite et la copier hors du serveur avant une migration. Vérifier PRAGMA integrity_check sur la sauvegarde. Conserver les images Docker précédentes et documenter le retour arrière avant de recréer des conteneurs. Les nouveaux événements peuvent ne pas exister dans une ancienne sauvegarde : exporter les données produites après celle-ci avant toute restauration.

Ne jamais supprimer globalement les images, données ou dossiers avant d'avoir confirmé leur usage et le chemin exact.
