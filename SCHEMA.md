# SIM.lab — SQLite normalized schema

`sim.db` est la source durable du monde. Le moteur temporel tourne côté serveur dans `engine.py` / `learning_engine.py`; le navigateur visualise le monde et envoie des commandes.

## État du monde

- `worlds`: horloge, pause/reprise, vitesse, compteurs et `last_tick_at` pour rattraper les courtes interruptions de moteur lors des déploiements.
- `world_settings`: paramètres globaux éditables.
- `resources`: nourriture et eau actuellement présentes.
- `artifacts`: objets inconnus injectés dans le monde.
- `events`: timeline historique append-only.

## Individus et société

- `agents`: état biologique/physique et cycle de vie. Les morts restent stockés avec `alive=0` et `death_year`.
- `agent_traits`: traits hérités/mutés.
- `agent_rules`: seuils et biais de décision propres à chaque vie.
- `agent_parents`: généalogie parent-enfant.
- `relations`: graphe social dirigé.
- `memories`: souvenirs autobiographiques et sociaux.
- `resource_memories`: meilleur emplacement connu de nourriture/eau par individu, confiance, dernière observation et nombre d'utilisations réussies.

## Apprentissage

- `agent_skills`: compétences acquises par pratique, dont `travel` pour l'expérience de déplacement longue distance.
- `hypotheses`: hypothèses avec confiance et preuves pour/contre.
- `agent_concepts`: généralisations abstraites.
- `experiments`: journal durable des essais directs.
- `beliefs`: synthèse des usages suffisamment établis.
- `discoveries`: savoir-faire réellement maîtrisés.

Un bébé n'hérite d'aucune connaissance technique. La boucle cognitive reste :

`perception → hypothèse → expérience/observation → preuves → généralisation → compétence → transmission sociale`.

La mémoire spatiale des ressources est également apprise : un individu doit avoir perçu ou utilisé un point d'eau / une zone de nourriture pour pouvoir tenter d'y revenir ensuite. Une mémoire qui ne correspond plus à une ressource réelle perd progressivement sa confiance.

## Mobilité et exploration

L'exploration n'est plus une succession de pas aléatoires locaux. Un individu choisit une direction d'excursion et la conserve pendant plusieurs ticks. Son rayon d'excursion sûr dépend de son autonomie liée à l'âge, de sa curiosité, de son expérience d'observation et de sa compétence `travel` acquise par la pratique.

L'eau reste une contrainte de survie, mais pas un point d'ancrage permanent :

- la soif ne domine plus les décisions lorsqu'elle est faible ou moyenne ;
- boire près d'un point d'eau est rapide, afin que l'individu puisse repartir ;
- plus il s'éloigne de son point d'eau connu, plus il décide tôt d'y revenir ;
- dépasser le rayon sûr force un demi-tour préventif ;
- l'expérience de voyage réduit légèrement le coût physiologique des déplacements ;
- le repos peut se faire sur place, sans obliger à revenir près de l'eau.

Les cibles temporaires d'exploration sont volontairement non persistées : elles représentent une intention de trajet court terme. La connaissance durable (ressources, compétences, relations, apprentissages) reste, elle, stockée en SQLite.

## Continuité des déploiements

Le moteur persiste `last_tick_at` à chaque flush. Après un redémarrage alors que le monde était en marche, `learning_engine.py` rejoue les ticks correspondant à la courte interruption (jusqu'à 60 secondes réelles). Une simulation volontairement mise en pause n'est jamais rattrapée.

Cette borne protège le démarrage après une panne longue : le mécanisme vise la continuité logique des déploiements/restarts, pas le replay aveugle de plusieurs heures d'indisponibilité.

Toutes les migrations sont additives et idempotentes ; aucun reset de PVC ou de monde n'est requis.
