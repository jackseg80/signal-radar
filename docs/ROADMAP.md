# Signal Radar — roadmap et statut

Mis à jour le 25 septembre 2026. La version de l'application est **4.0.0**. Les documents de stratégie portant « V3 » décrivent une étape de validation statistique historique, pas le numéro de version du produit.

## Terminé

- Moteur de backtest modulaire, stratégies RSI(2), IBS et TOM, analyse de robustesse et rapports.
- Base SQLite unifiée, API FastAPI, tableau de bord React, journal des opérations et historique papier.
- Scanner multi-stratégie et calendrier XNYS.
- Décisions pour l'ouverture suivante avec contrôle strict des cours, des positions, du cash et des règles du portefeuille.
- Portefeuille papier commun de 5 000 USD, indépendant du compte Saxo, et suivi virtuel séparé par signal positif.
- Journal de provenance des données et secours Nasdaq pour une séance historique isolée manquante.
- Interface distincte pour déclenchement technique, recommandation bloquée, simulation papier et suivi virtuel.
- Validation next-open, contrôle des comparaisons multiples, rapports de période et observation manuelle Saxo.

## En observation

- Comparer les signaux et ouvertures simulées aux données Saxo pendant 20 séances XNYS.
- Mesurer les écarts d'ouverture, les exécutions éventuelles et les frais réels du compte USD.
- Maintenir l'achat réel bloqué tant que les frais ne sont pas rapprochés et que la validation de production ne satisfait pas les critères.

## À revoir avant toute promotion

- Compléter les 20 séances et publier un rapport auditable.
- Recalculer les résultats avec des coûts Saxo vérifiés à partir de transactions exécutées.
- Examiner les périodes défavorables, les chevauchements et le portefeuille commun de 5 000 USD.
- Toute modification de l'univers reste une décision manuelle après revue ; un screening ne promeut aucun titre.

## Hors périmètre actuel

Aucune API Saxo, aucun ordre automatique, aucune exécution automatique, ni extension automatique de la liste négociable ne sont prévus. Une intégration de courtier ou un déploiement avec de nouvelles permissions nécessiterait une décision séparée.

## Historique

Les phases 1 à 5 décrites dans les anciens rapports restent des jalons historiques. Les tableaux de résultats rétrospectifs ne valent pas recommandation actuelle ; consulter le rapport de validation de production le plus récent.
