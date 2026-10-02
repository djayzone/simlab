# SIM.lab — équilibrage apprentissage et émergence

Le gameplay doit produire des trajectoires observables sans injecter de connaissance directement dans les agents.

## Cibles d'équilibrage

- une hypothèse correcte répétée doit pouvoir devenir une découverte après environ trois succès directs cohérents ;
- un premier succès ne suffit jamais à créer une découverte ;
- une hypothèse fausse et confiante ne doit pas supprimer l'exploration des autres usages possibles d'un objet ;
- l'observation et l'enseignement sont progressifs mais peuvent réellement transmettre une découverte après plusieurs interactions ;
- l'enseignement privilégie ce que le professeur maîtrise déjà, tout en conservant la possibilité de transmettre des croyances incomplètes ;
- les besoins vitaux restent prioritaires lorsqu'ils deviennent urgents ; hors urgence, l'expérimentation doit être compétitive avec exploration et observation ;
- l’eau est un point de passage : les vies ciblent la berge, la proximité immédiate ne crée pas artificiellement un besoin de boire et une vie rassasiée reprend une excursion au lieu de rester agrégée au centre de la mare ;
- le journal expose les premières tentatives, succès utiles, consolidations d'hypothèses et découvertes sans journaliser chaque échec répétitif.

## Densité d'opportunités

Les packs hot-loadables `agriculture` et `charcoal` passent en version `1.1.0`. La nouvelle activation introduit respectivement 12 parcelles et 8 fosses à charbon dans les mondes persistants qui n'ont encore jamais activé cette version.

Ce réensemencement ajoute des occasions d'interaction sans apprendre quoi que ce soit aux vies. Elles doivent toujours percevoir, tester, accumuler des preuves et transmettre leurs conclusions.

## Invariants

- aucun reset du monde ou du PVC ;
- aucune découverte héritée à la naissance ;
- aucune action correcte révélée à l'agent par le moteur de décision ;
- les succès, échecs, fausses croyances et différences individuelles restent possibles.
