# SIM.lab — contrôle météo live

Le climat naturel reste le mode par défaut (`auto`). La console opérateur permet de passer temporairement en mode `manual` afin de tester les réactions du monde sans modifier les connaissances des habitants.

## API

`POST /api/weather/control`

Actions principales :

- `{ "action": "auto" }` : rend la main au climat naturel ;
- `{ "preset": "clear" }` ;
- `{ "preset": "rain" }` ;
- `{ "preset": "storm" }` ;
- `{ "preset": "heatwave" }` ;
- `{ "preset": "cold_snap" }` ;
- `{ "preset": "drought" }` ;
- réglage manuel de `temperature`, `precipitation`, `wind`, `drought`, `humidity`, `cloud`, `storm_intensity` ;
- `season` peut forcer `printemps`, `été`, `automne` ou `hiver`.

Les valeurs normalisées (`precipitation`, `wind`, `drought`, etc.) restent bornées entre 0 et 1. La température est limitée à -25..50 °C.

## UI

Le HUD météo contient un panneau dépliable **Contrôle météo live** avec presets, sélection de saison, sliders température/pluie/vent/sécheresse et bouton `Auto`.

Le mode manuel n'altère pas les règles d'apprentissage : les agents observent simplement les conditions imposées comme n'importe quel phénomène environnemental. Le retour à `Auto` reprend immédiatement le cycle naturel.