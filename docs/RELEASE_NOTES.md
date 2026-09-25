# Signal Radar 4.0.0 — 25 septembre 2026

Cette version regroupe la refonte du scanner et du tableau de bord autour des signaux à l'ouverture suivante.

## Changements

- Sépare le déclenchement technique, l'éligibilité d'un achat réel, le portefeuille papier commun et le suivi virtuel indépendant des signaux positifs.
- Rend la confirmation du compte Saxo distincte des simulations ; aucun ordre n'est transmis à Saxo.
- Contrôle les séances XNYS, la fraîcheur et la cohérence des bougies, et bloque les décisions qui dépendent de cours non vérifiés.
- Ajoute Nasdaq comme source de secours pour une seule séance historique interne manquante, avec vérification OHLC, des clôtures adjacentes et du facteur d'ajustement. Chaque réparation est journalisée et exposée dans l'interface.
- Ajoute les rapports de validation next-open et une observation de 20 séances. Les nouveaux titres ne sont jamais promus automatiquement.
- Clarifie le tableau de bord : séance source, ouverture visée, achats bloqués, raisons, candidats papier et réparations de cours.

## État au déploiement

- 495 tests réussis localement et compilation du Frontend réussie au 25 septembre 2026.
- Sur le serveur de production, l'API est saine, la base SQLite est intègre et les sept réparations Nasdaq du 22 septembre sont enregistrées.
- La validation de production couvre 37 couples titre/stratégie sans erreur de données, mais les frais Saxo restent provisoires et aucun achat réel n'est actuellement recommandé.
- L'observation de 20 séances reste à terminer.

## Compatibilité et limites

Le flux de décision est documenté sous NEXT_OPEN_V2 pour distinguer cette génération applicative du schéma et des règles v2. Les tables ajoutées sont migrées de manière additive. Les anciens historiques restent consultables et ne sont pas fusionnés avec le nouveau P&L. Les données de compte et de déploiement propres à l'utilisateur ne sont pas incluses dans cette publication.


## Correctif du tableau de bord — 25 septembre 2026

- Restaure une grille de panneaux déplaçables et redimensionnables dans le Radar, avec disposition mémorisée par navigateur et bouton de réinitialisation.
- Place les signaux et la vue d’ensemble des actions côte à côte par défaut ; ajoute Approaching et un aperçu compact des positions papier ouvertes.
- Garde les détails papier dans leur page dédiée et replie l’observation Saxo sous la grille.
- Déployé sur robot2 après compilation et contrôle des vues ; API saine, scanner et base inchangés.
- Voir [le guide du tableau de bord](DASHBOARD_GUIDE.md) pour les gestes et la portée de chaque vue.
