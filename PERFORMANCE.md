# SIM.lab — performance runtime

## Snapshot `/api/world`

Le moteur sert `/api/world` depuis un cache JSON pré-sérialisé. Depuis le passage en stale-while-revalidate, un snapshot complet n'est reconstruit que lorsqu'un client le demande et que le précédent est devenu trop ancien. Cela évite de payer `world_view()` en continu quand personne ne regarde l'interface.

## Persistance

La persistance durable complète est bornée par `SIM_PERSIST_INTERVAL` (5 s par défaut). Les resets restent persistés immédiatement. En cas de crash brutal, la fenêtre maximale d'état non flushé est donc d'environ 5 s.

## Population vivante

`Engine.living()` met en cache uniquement la **membership** vivant/mort. Le cache est un `tuple` immuable contenant les dictionnaires agents originaux : leurs positions, besoins, relations et connaissances continuent donc d'évoluer normalement, mais aucun appelant ne peut modifier accidentellement la composition du cache via `append`, `remove`, `sort`, `shuffle`, etc.

Le cache est invalidé dès que l'un des éléments suivants change : identité du dictionnaire `agents`, nombre total d'agents, compteur de naissances ou compteur de décès. `/healthz` expose `livingCache.hits`, `misses`, `size` et `immutable`.

Cette immutabilité ferme explicitement le principal risque de maintenance identifié lors de la review de la PR : un appelant futur ne peut plus corrompre silencieusement la liste mise en cache.

## CPU

Le moteur dispose d'une limite de 1 CPU. Les optimisations appliquées successivement ont retiré les reconstructions HTTP concurrentes, les racines carrées inutiles dans `_nearest`, puis réduit le coût de persistance. Le profileur statistique embarqué continue d'indiquer les hotspots sans instrumentation appel-par-appel.

Le profil runtime du 18 septembre 2026 montre ensuite `simulation_runtime._nearest` comme hotspot majeur, avec des scans répétés de la population vivante depuis `learning_engine._act()` et `_choose_action()`. La population vivante est désormais indexée dans une grille spatiale de 100 px. Les requêtes de proximité 80–95 px ne parcourent que les cellules voisines, tout en conservant exactement la règle de distance, les prédicats et l'ordre de départage du scan linéaire. L'index est reconstruit sur naissance/mort/reset/load et mis à jour en O(1) après chaque déplacement.

Cette optimisation ne modifie ni la vitesse du monde, ni le nombre de ticks, ni les règles de décision. Les recherches de ressources et d'artefacts conservent pour l'instant le fallback linéaire ; elles pourront être indexées séparément si le prochain profil les fait remonter.

## Phase 2 — collections statiques du tick

Le profil post-déploiement a montré deux limites du premier lot :

- le profileur comptait tous les threads Python et attribuait donc artificiellement environ 50 % des échantillons au worker de snapshot alors qu'il était bloqué dans `Event.wait()` ;
- les agents étaient indexés, mais chaque agent reconstruisait encore les listes `food`, `water` et `artifacts`, puis exécutait des recherches linéaires dessus.

Le profileur cible désormais uniquement le thread `sim-engine`. Les collections nourriture/eau/artefacts passent par des vues immuables mises en cache par signature `(identité du dictionnaire, taille, dernier id)`. Une naissance de ressource, une consommation, un choc météo ou l'ajout d'un artefact invalide donc automatiquement la vue concernée. Chaque vue possède son index spatial exact et conserve la sémantique historique de distance et de départage.

Les bornes de cellules de l'index sont également calculées à partir du rectangle exact `origin ± max_distance` au lieu d'un rayon de cellules arrondi, ce qui réduit les cellules visitées pour les recherches de 150–240 px.

## Étape suivante

Après déploiement, comparer le CPU à vitesse/population comparables et relire uniquement le profil du thread `sim-engine`. Le prochain lot doit être décidé sur cette preuve : persistance différentielle si `_persist` reste dominant, ou optimisation des décisions/relations si `_act` et `_choose_action` deviennent les principaux hotspots.
