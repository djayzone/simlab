# SIM.lab — livraison sans arrêt

## Séparation runtime

SIM.lab est séparé en deux runtimes :

- `sim-lab` : moteur de simulation, seul détenteur du PVC SQLite ;
- `sim-lab-web` : 2 replicas stateless qui servent l'UI et proxifient `/api/*` vers `sim-lab-engine`.

Les mises à jour web utilisent un RollingUpdate `maxUnavailable: 0`. Une modification HTML/CSS/JS ou du proxy web ne redémarre donc pas le moteur.

## Gameplay hot-loadable

Les mécaniques déclaratives vivent dans la ConfigMap **stable** `sim-lab-mechanics`, montée dans `/mechanics`. Contrairement aux ConfigMaps de code, son nom n'est pas hashé dans le PodTemplate : une modification GitOps de son contenu ne déclenche aucun rollout du moteur.

Le moteur scanne les fichiers JSON toutes les ~2 secondes de temps réel. Si leur digest change :

1. le pack est validé ;
2. les définitions sont échangées sous le verrou du moteur ;
3. la génération `mechanics.generation` augmente ;
4. une nouvelle version peut introduire des objets dans le monde une seule fois ;
5. aucun agent n'apprend automatiquement la mécanique : les objets doivent être perçus, testés, compris et transmis.

Une erreur de pack conserve la génération précédente active et apparaît dans `world.mechanics.error`.

## Contrat v1

Un pack v1 contient `schema`, `id`, `version`, `enabled`, des `artifacts` et éventuellement `introduce`.

Les actions actuellement utilisables sans code sont : `inspect`, `manipulate`, `strike`, `feed`, `bury`, `roll`, `consume`.

Effets génériques disponibles :

- `practice` : progression d'une compétence dynamique ;
- `food_store` ;
- `energy` ;
- `spawn_resource` ;
- `spawn_artifact`.

Agriculture et charbon sont les deux premiers packs de validation. Ajouter ou modifier un pack futur (poterie, stockage d'eau, nouveaux combustibles, etc.) passe uniquement par `mechanics-configmap.yaml` tant que les primitives v1 suffisent.

## Limite volontaire

Une primitive moteur entièrement nouvelle nécessite encore une livraison du code moteur. Le prochain niveau prévu est un DSL d'effets plus riche puis, pour les sémantiques complexes, des workers de mécanique externes. Mais les contenus/règles couverts par les primitives v1 sont déjà livrables à chaud sans arrêt du temps.
