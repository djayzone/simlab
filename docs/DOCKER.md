# Lancer SIM.lab avec Docker

Ce guide ne suppose aucune connaissance de Python.

## 1. Installer Docker

Installez **Docker Desktop** sur Windows/macOS ou Docker Engine sur Linux.

Vérifiez ensuite :

```bash
docker --version
docker compose version
```

## 2. Télécharger le projet

```bash
git clone https://github.com/djayzone/simlab.git
cd simlab
```

## 3. Méthode la plus simple : Docker Compose

```bash
docker compose up --build
```

Attendez que le conteneur soit démarré, puis ouvrez :

```text
http://localhost:8080
```

Pour arrêter :

```bash
docker compose down
```

Votre monde n'est pas supprimé : la base SQLite reste dans le volume `simlab-data`.

Pour supprimer également toutes les données :

```bash
docker compose down -v
```

## 4. Méthode Docker classique

Construire l'image :

```bash
docker build -t simlab:local .
```

Lancer le produit :

```bash
docker run --name simlab -p 8080:8080 -v simlab-data:/data simlab:local
```

Ouvrez ensuite :

```text
http://localhost:8080
```

Arrêter :

```bash
docker stop simlab
```

Relancer :

```bash
docker start simlab
```

Supprimer uniquement le conteneur :

```bash
docker rm simlab
```

Les données restent dans le volume.

## Vérifier que SIM.lab fonctionne

```bash
curl http://localhost:8080/healthz
```

Réponse attendue :

```json
{"ok":true}
```

## Voir les logs

Avec Compose :

```bash
docker compose logs -f simlab
```

Avec Docker :

```bash
docker logs -f simlab
```

## Changer le port

Exemple pour exposer SIM.lab sur le port 9000 de votre machine :

```bash
docker run --rm -p 9000:8080 -v simlab-data:/data simlab:local
```

L'URL devient alors :

```text
http://localhost:9000
```

## Mettre à jour

```bash
git pull
docker compose up --build -d
```
