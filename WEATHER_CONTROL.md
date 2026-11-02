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

## Sécheresse naturelle : modèle récupérable (SIMLAB-15)

En mode `auto`, la sécheresse n'est pas un compteur cumulatif :
`climate_engine.py` appelle `advance_drought()` dans `climate_model.py`.
La cible dépend de la saison, de la température, de l'humidité, des précipitations
et du vent ; elle reste comprise entre **0,08 et 0,96**. L'état évolue
progressivement vers cette cible et reste borné à **0–0,98**. Une pluie
persistante accélère la récupération, mais une seule averse ne remet pas
instantanément une sécheresse profonde à zéro.

En mode `manual`, une valeur explicite `drought` (y compris les presets
`drought` et `heatwave`) reste imposée par l'opérateur. Si seuls les
paramètres de pluie, température ou vent sont imposés, la sécheresse continue
d'évoluer selon ces conditions. L'action `{ "action": "auto" }` libère les
contraintes manuelles et reprend l'évolution naturelle : elle **ne réinitialise
pas** la sécheresse à zéro.

**Attention aux presets successifs :** en mode `manual`, chaque nouveau preset
est fusionné avec les réglages déjà imposés. Passer de `heatwave` ou `drought`
à `rain` **ne libère pas** la valeur `drought` précédente : la pluie est forcée,
mais la sécheresse reste verrouillée. Pour permettre sa récupération naturelle,
choisir d'abord `Auto` afin de libérer les contraintes, puis éventuellement
appliquer `rain` si une pluie manuelle est souhaitée. `Auto` ne remet pas le
niveau de sécheresse à zéro. Ce scénario de succession de presets n'est pas
couvert par les cinq tests unitaires du modèle et reste à valider en HTTP/UI.

Contrat vérifiable hors ligne depuis la racine du dépôt :

```bash
python3 -m unittest test_climate_model.py
```

Les cinq tests déterministes couvrent l'été normal, la sécheresse extrême
bornée, la récupération après trente pas d'automne humide, l'effet limité
d'une averse unique et les bornes d'entrée. **Ce sont des tests unitaires du
modèle**, pas une recette du monde persistant, du contrôle HTTP ou de l'UX.
Le présent changement est uniquement documentaire ; aucune validation
runtime ni résultat de test nouveau n'est revendiqué.
