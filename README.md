# Urban Data Explorer — Marché Immobilier Parisien


Projet Data, Développement et Architecture de Données

---

## Présentation

Urban Data Explorer est une plateforme complète (pipeline + API + dashboard) permettant d'explorer le marché immobilier parisien arrondissement par arrondissement.

Le dashboard interactif affiche, pour chacun des 20 arrondissements :
- Prix médian au m² (2021–2025) depuis les transactions DVF
- Évolution temporelle et variation annuelle
- Part de logements sociaux
- Répartition typologique (T1 → T5+)
- Revenus médians (INSEE Filosofi 2020)
- Densité de population, criminalité

---

## Architecture technique

```
Sources ouvertes (APIs, CSV, JSON)
        ↓
Zone Bronze  (data/bronze/)     — données brutes, non transformées
        ↓
Zone Silver  (data/silver/)     — nettoyées, normalisées, géocodées
        ↓
Zone Gold    (data/gold/)       — agrégées, enrichies, prêtes à servir
        ↓
API Web      (api/main.py)      — FastAPI, endpoints REST
        ↓
Dashboard    (frontend/)        — JS + Leaflet + Chart.js
```

---

## Sources de données

| Source | Indicateur | Format | URL |
|--------|-----------|--------|-----|
| DVF — Demandes de Valeurs Foncières | Prix/m², transactions | API JSON | data.gouv.fr |
| OpenData Paris | Logements sociaux, GeoJSON arrondissements | CSV / GeoJSON | opendata.paris.fr |
| INSEE Filosofi 2020 | Revenus médians, taux de pauvreté, Gini | CSV | data.gouv.fr |
| INSEE Recensement 2020 | Population légale | CSV | insee.fr |
| SSMSI — data.gouv.fr | Crimes et délits par commune | CSV | data.gouv.fr |

---

## Structure du projet

```
urban-data-explorer/
├── pipeline/
│   ├── ingest.py        # Étape 2 : collecte des données (Zone Bronze)
│   ├── clean.py         # Étape 3 : nettoyage et normalisation (Zone Silver)
│   └── aggregate.py     # Étape 4 : agrégation et enrichissement (Zone Gold)
├── data/
│   ├── bronze/          # Données brutes (non versionnées)
│   ├── silver/          # Données nettoyées (non versionnées)
│   └── gold/
│       └── arrondissements_enrichis.json   # Table Gold principale
├── api/
│   ├── main.py          # API FastAPI
│   ├── requirements.txt
│   └── Procfile         # Déploiement Render/Railway
├── frontend/
│   ├── index.html       # Dashboard
│   ├── app.js           # Logique carte + graphiques
│   └── style.css        # Design
├── run_pipeline.py      # Orchestrateur pipeline complet
├── requirements.txt
└── data/catalog.md      # Data catalog
```

---

## Lancer le projet en local

### 1. Prérequis

```bash
python 3.10+
pip install -r requirements.txt
```

### 2. Exécuter le pipeline (optionnel — données Gold déjà présentes)

```bash
python run_pipeline.py
```

Le pipeline récupère les données depuis les APIs publiques, les nettoie et produit `data/gold/arrondissements_enrichis.json`.

> **Note :** La zone Gold est déjà versionnée dans ce dépôt avec des données réelles 2021–2025. Relancer le pipeline n'est nécessaire que pour mettre à jour les données.

### 3. Démarrer l'API backend

```bash
cd urban-data-explorer
uvicorn api.main:app --reload --port 8000
```

L'API est disponible sur `http://localhost:8000`
Documentation interactive : `http://localhost:8000/docs`

### 4. Ouvrir le dashboard

Ouvrir `frontend/index.html` directement dans un navigateur **ou** accéder à `http://localhost:8000/app` une fois l'API démarrée.

---

## Endpoints API

| Endpoint | Description |
|----------|-------------|
| `GET /arrondissements` | Tous les arrondissements avec indicateurs |
| `GET /arrondissements/{num}` | Détail d'un arrondissement (1–20) |
| `GET /prix?annee=2023` | Prix médians par arrondissement pour une année |
| `GET /prix/{num}` | Série temporelle 2021–2025 pour un arrondissement |
| `GET /timeline?arr=6` | Évolution temporelle (Paris ou arrondissement) |
| `GET /comparaison?arr1=1&arr2=6` | Comparaison de deux arrondissements |
| `GET /logements-sociaux` | Part de logements sociaux triée |
| `GET /indicateurs` | Tableau de bord complet tous indicateurs |
| `GET /geojson` | GeoJSON enrichi compatible Leaflet/Mapbox |
| `GET /docs` | Documentation Swagger UI |

---

## Fonctionnalités du dashboard

- **Carte choroplèthe** : couleurs selon l'indicateur sélectionné (prix, logements sociaux, revenus, criminalité, densité)
- **Sélecteur d'indicateur** : basculer entre 5 indicateurs en temps réel
- **Slider d'année** : visualiser l'évolution 2021 → 2025
- **Timeline animée** : animation automatique année par année
- **Survol / clic** : affiche les indicateurs de l'arrondissement
- **Mode comparaison** : sélectionner deux arrondissements, comparaison avec radar chart
- **Classement** : top 20 arrondissements par prix/m² pour l'année sélectionnée

---

## Déploiement

### Backend (Render / Railway)

```bash
# Le Procfile est déjà configuré :
web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Pointer le service vers le dossier racine du projet.

### Frontend (GitHub Pages / Netlify)

Déployer le dossier `frontend/` directement.  
Modifier `API_BASE` dans `app.js` pour pointer vers l'URL de production.

---

## Indicateurs principaux

| Indicateur | Description | Source |
|-----------|-------------|--------|
| Prix médian €/m² | Médiane des transactions DVF par arrondissement et par année | DVF data.gouv.fr |
| Variation annuelle % | Évolution 2022→2023 du prix médian | Calculé |
| Logements sociaux % | Part du parc social dans le total des logements | OpenData Paris |
| Revenu médian €/UC | Revenu médian par unité de consommation (INSEE Filosofi 2020) | INSEE |
| Densité hab/km² | Population légale / superficie | INSEE / calcul |
| Criminalité / 1 000 hab | Faits de délinquance enregistrés rapportés à la population | SSMSI |

### Indicateurs personnalisés

| Indicateur | Description | Source |
|-----------|-------------|--------|
| Revenus médians | Inégalités de revenus entre arrondissements | INSEE Filosofi |
| Répartition typologique | Studios, T2, T3, T4, T5+ par arrondissement | DVF |
| Nombre de transactions | Volume du marché par arrondissement | DVF |
| Taux de pauvreté | Part des ménages sous le seuil de pauvreté | INSEE Filosofi |

---

## Résultats clés (2023)

- **Arrondissement le plus cher** : 6ème (Saint-Germain) — 14 580 €/m²
- **Arrondissement le moins cher** : 19ème (Buttes-Chaumont) — 8 610 €/m²
- **Prix médian Paris 2023** : ~10 900 €/m²
- **Variation 2022→2023** : -4,2 % en moyenne (correction du marché post-Covid)
- **Plus forte part de logements sociaux** : 19ème (34,5 %)
- **Plus faible part de logements sociaux** : 6ème (3,2 %)

---

*Sources : DVF data.gouv.fr · OpenData Paris · INSEE Filosofi 2020 · SSMSI*
# Projet_Data_architecture
