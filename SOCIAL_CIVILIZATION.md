# SIM.lab — émergence sociale et civilisation

## Intention

Faire passer le monde d'une collection de vies individuelles à des sociétés observables, sans créer de factions prédéfinies ni injecter des comportements collectifs magiques.

## Lot 1 — communautés persistantes

Une communauté peut apparaître uniquement après des interactions répétées produisant une relation mutuelle suffisante.

Contrats :

- la proximité seule ne crée jamais un groupe ;
- une communauté est persistée dans SQLite et survit aux redémarrages du moteur ;
- l'appartenance peut évoluer ou disparaître si les relations s'érodent ;
- les enfants peuvent appartenir naturellement à la communauté commune de leurs deux parents, sans hériter de connaissance technique ;
- la cohésion spatiale cible un autre membre vivant et mobile, jamais un centre fixe ou un campement artificiel ;
- les besoins vitaux restent prioritaires sur la cohésion ;
- l'API monde expose les communautés et chaque vie expose son appartenance ;
- aucun reset du monde ou du PVC n'est requis.

## Lot 2 — alliances, rivalités et fractures

Les relations entre communautés sont dérivées des interactions de leurs membres :

- socialisation et entraide font progresser la coopération ;
- les partages de nourriture accélèrent les rapprochements ;
- les vols répétés font émerger rivalité puis hostilité ;
- les états sont progressifs et réversibles : neutralité, coopération, alliance, rivalité, hostilité ;
- ces relations modifient réellement les décisions individuelles près d’un membre d’un autre groupe ;
- une communauté dont les sous-groupes internes ne se supportent plus peut se fracturer en nouvelles communautés si des liens forts subsistent au sein des sous-groupes ;
- le graphe diplomatique est persisté dans SQLite et exposé dans les vues runtime ;
- l’absence prolongée d’interactions atténue très lentement les anciennes relations vers la neutralité.

Aucune communauté ne reçoit de diplomatie prédéfinie, aucun conflit collectif n’est forcé et aucun point spatial fixe n’est créé.

## Lots suivants

Le socle permettra ensuite d'ajouter séparément :

1. partage culturel et entraide à l'échelle du groupe ;
2. campements émergents liés aux usages réels des ressources ;
3. influence sociale/leadership sans rôle assigné ;
4. coopération sur des tâches et conflits collectifs ;
5. métriques de civilisation et journal d'événements sociaux.

## Chronique et lisibilité — état observé le 1er novembre 2026 (SIMLAB-27)

Le monde conserve une timeline `events` append-only dans SQLite (`SCHEMA.md`).
L'interface affiche déjà le dernier événement dans le ticker et un journal
limité aux 50 événements renvoyés par `/api/world`, à côté de la vue
`Connaissances`. L'inspecteur affiche les communautés et leurs relations.
Ces éléments rendent des changements visibles, **mais ne constituent pas
encore une explication causale vérifiée** de leur origine.

Les deux onglets du journal utilisent des relations explicites
`tablist` / `tab` / `tabpanel` et un seul onglet actif dans l'ordre
de tabulation. Flèches gauche/droite, Début et Fin déplacent la sélection
et le focus ; un panneau inactif est masqué à la navigation assistée.
La sélection au clic et les raccourcis de panneaux restent inchangés.
Les raccourcis globaux (Espace, F, 1–4) laissent les touches natives aux
contrôles interactifs et aux panneaux du journal lorsqu'ils ont le focus.

**Suite du lot, non implémentée ici :** relier chaque événement significatif
à des causes observables et vérifiables sans inventer d'intentions ; distinguer
les événements du monde des inférences de l'interface ; tester la compréhension
de la chronologie et des communautés sur mobile, au clavier et avec lecteur
d'écran. Le test structurel `test_web_ui.py` et la vérification isolée
du gestionnaire d'onglets ne remplacent pas une recette navigateur/AT.
