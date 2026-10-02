# SIM.lab — environnement dynamique

Le lot météo ajoute une pression environnementale indépendante sans donner de connaissances magiques aux habitants.

## Modèle

Le moteur distingue un climat global et une grille locale 6×4. Chaque cellule possède température, humidité, précipitations, couverture nuageuse, vent et sécheresse. Un centre orageux se déplace continuellement et produit des différences locales visibles sur la carte.

Le cycle annuel comporte printemps, été, automne et hiver. Les saisons donnent seulement des tendances : chaque année reste stochastique, avec épisodes secs, pluies fortes, chaleur ou froid possibles.

## Cycle de l’eau et écologie

- la pluie augmente la taille/capacité des points d’eau naturels ;
- les fortes pluies peuvent créer des mares temporaires ;
- les mares temporaires régressent puis disparaissent ;
- la sécheresse fait diminuer les réserves d’eau ;
- pluie + température favorable accélèrent la repousse de nourriture ;
- une sécheresse forte peut supprimer une partie des ressources végétales.

Les futures mécaniques de transport d’eau, agriculture, faune et campements pourront consommer directement ces mêmes données environnementales.

## Effets sur les habitants

- chaleur : soif et fatigue légèrement accrues ;
- froid : coût énergétique accru, fortement réduit par une connaissance du feu/chaleur ;
- froid extrême + épuisement : dommage de santé ;
- pluie forte et vent fort : déplacement ralenti.

Ces effets s’ajoutent aux mécaniques de survie existantes et ne remplacent pas la mémoire de l’eau ni la compétence `travel`.

## Apprentissage

Les habitants ne connaissent pas les saisons ni les effets de la pluie à la naissance. Des observations répétées enrichissent progressivement les concepts existants :

- `weather:pluie→eau` ;
- `weather:sécheresse→rareté` ;
- `season:<saison>`.

Il s’agit d’associations empiriques individuelles, pas d’un calendrier inné. Les futurs lots de connaissance collective pourront transformer ces observations en traditions saisonnières.

## Persistance

Trois tables additives sont utilisées :

- `weather_state` : état global courant ;
- `weather_cells` : état local de la grille ;
- `weather_spawned_water` : mares temporaires et année d’expiration.

Aucun reset du monde ou du PVC n’est requis. Le rattrapage `last_tick_at` existant appelle aussi les ticks météo pendant une courte reprise après déploiement.
