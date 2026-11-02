# SIM.lab — runtime contract

Le runtime est séparé en trois responsabilités :

1. `simulation_runtime.py` compose le moteur, les optimisations runtime, le cache de snapshot et le profiler.
2. `runtime_api.py` expose le contrat interne stable `tick()`, `reset()`, `snapshot()`, `persist()` ainsi que les opérations de contrôle nécessaires au transport.
3. `http_server.py` ne contient plus de logique de simulation : il valide/routage les requêtes HTTP et délègue au contrat runtime.

`engine_bootstrap.py` compose d'abord les couches gameplay/climat, applique les migrations de compatibilité additives, puis importe le serveur HTTP. Cela conserve l'ordre d'héritage actuel sans injecter de connaissance dans les agents.

## Invariants

- les mutations de tick/persistance explicites passent sous `engine.lock` ;
- la boucle moteur, `reset()`, les contrôles HTTP, `world_view()` et `agent_view()` utilisent le même `RLock` moteur ;
- `living()` suppose ce verrou détenu par son appelant et ne rajoute donc pas un lock sur le hot path ;
- les vues `food`, `water` et `artifacts` sont immuables et mises en cache dans la couche runtime ; leur signature `(identité du dictionnaire, taille, prochain identifiant)` détecte les ajouts et retraits ordinaires du moteur, mais pas une substitution arbitraire à taille et compteur inchangés ;
- les recherches de proximité sur ces vues utilisent des index spatiaux séparés, sans modifier les objets gameplay ni leur ordre logique ;
- toute modification de membership vivant passe par `_new_agent()`, `_die()`, `reset()` ou `_load()` et incrémente une révision explicite ;
- `membership_cache.py` ne reconstruit le tuple vivant que lorsque cette révision change ; un remplacement inattendu du dictionnaire `agents` force néanmoins un rebuild de sécurité et incrémente `sourceFallbacks` ;
- `agent_compat.py` complète avant chargement les traits/règles obligatoires absents des mondes persistés ; une valeur déjà persistée n'est jamais remplacée ;
- les migrations de compatibilité de démarrage sont additives et idempotentes afin que le catch-up ne puisse pas exécuter un agent au schéma incomplet ;
- `snapshot()` utilise `world_view()`, qui construit une vue cohérente sous le verrou moteur ;
- le serveur HTTP ne reçoit jamais une référence directe vers `agents`, `resources` ou `artifacts` ;
- le cache `/api/world` reste stale-while-revalidate et sérialisé une seule fois par génération ;
- `tick()` manuel est borné à 120 pas et n'est pas exposé comme endpoint HTTP ;
- `/healthz` expose `runtimeApi.version=1` et l'état `livingCache` afin de diagnostiquer le runtime.

## Compatibilité des mondes persistés

Avant toute construction du moteur, `agent_compat.py` normalise les agents legacy avec des valeurs neutres pour les champs actuellement requis : `exploreBias`, `curiosity`, `sociability`, `aggression` et `empathy`. La migration utilise uniquement `INSERT OR IGNORE`, reste rejouable et ne modifie jamais une personnalité ou une règle déjà persistée.

La purge du monde reste un recours de dernier niveau : si une incompatibilité structurelle subsiste après cette normalisation, l'opérateur peut repartir d'un monde neuf. Elle n'est pas nécessaire pour une simple absence de traits/règles.

## Vérification de concurrence

Les tests de membership utilisent le même contrat que le moteur : lecteurs et écrivain partagent un `RLock`, chaque transition de membership appelle `changed()`, et aucun tuple ne doit exposer un agent mort. La sécurité de remplacement de source est testée séparément pour détecter un futur chemin reset/load qui oublierait la révision.

## État actuel des recherches spatiales

Le chantier annoncé précédemment comme futur est **déjà intégré dans le code de ce dépôt** : `simulation_runtime.py` utilise `LivingSpatialIndex` pour les agents vivants et `SpatialCollectionCache` pour les vues `food`, `water` et `artifacts` (`spatial_index.py`). Le repli linéaire de `_nearest` reste disponible pour les collections non reconnues ; il compare les distances **au carré**, sans racine carrée, avec une borne stricte (`distance < max_distance`).

L'index conserve l'ordre de départage des candidats à distance égale, reconstruit la population après changement de membership et met à jour la cellule d'un agent après déplacement. Les vues de ressources et d'artefacts sont reconstruites quand leur signature change. `test_spatial_index.py` contient des tests de comparaison au scan linéaire, de déplacement entre cellules, d'égalité de distance, de borne stricte et d'invalidation des vues.

Ce relevé est **statique** : la présence du code et des tests ne prouve ni leur exécution récente, ni une amélioration CPU mesurée sur un cluster. Les mesures de performance et la qualification runtime restent distinctes de cette mise à jour documentaire. Voir [PERFORMANCE.md](PERFORMANCE.md).
