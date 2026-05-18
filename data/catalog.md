# Data Catalog — Urban Data Explorer

Inventaire des jeux de données utilisés dans le projet Urban Data Explorer.
Projet : Marché immobilier parisien — 20 arrondissements, 2021-2025.

---

## Zone Bronze (données brutes)

### dvf_paris.csv
Transactions immobilières DVF filtrées pour Paris (ventes d'appartements uniquement).

| Champ | Type | Description |
|-------|------|-------------|
| date_mutation | date | Date de la transaction |
| valeur_fonciere | float | Prix de vente (€) |
| surface_reelle_bati | float | Surface en m² |
| nombre_pieces_principales | int | Nombre de pièces |
| type_local | string | Type de bien (Appartement) |
| code_commune | string | Code INSEE arrondissement (75101–75120) |
| arrondissement | int | Numéro d'arrondissement (1–20) |

- **Source :** DVF géolocalisé national — data.gouv.fr
- **URL :** `https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres-geolocalisees/20260424-090024/dvf.csv.gz`
- **Périmètre :** Ventes d'appartements à Paris (codes INSEE 75101–75120)
- **Période :** Janvier 2021 – Décembre 2025
- **Taille brute :** ~523 MB compressé, 188 798 lignes après filtrage Paris
- **Format :** CSV (téléchargement streaming, filtrage par chunks)
- **Licence :** Licence Ouverte / Open Licence 2.0

---

### logements_sociaux.csv
Programmes de logements sociaux financés par la Ville de Paris depuis 2001.

| Champ | Type | Description |
|-------|------|-------------|
| id_livraison | string | Identifiant du programme |
| adresse_programme | string | Adresse du programme |
| code_postal | string | Code postal |
| annee | int | Année de financement |
| nb_logmt_total | int | Nombre total de logements financés |
| nb_plai | int | Logements PLAI (très social) |
| nb_plus | int | Logements PLUS |
| nb_pls | int | Logements PLS |
| arrdt | string | Arrondissement (colonne source) |
| arrondissement | int | Numéro d'arrondissement normalisé (1–20) |

- **Source :** OpenData Paris
- **URL :** `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/logements-sociaux-finances-a-paris/exports/csv`
- **Périmètre :** Programmes financés depuis 2001 (4 174 programmes)
- **Note :** Ce dataset comptabilise les *nouveaux* logements financés depuis 2001, pas le stock total existant. Le taux `logements_sociaux_pct` (% du parc) est issu du RPLS 2022 (voir ci-dessous).
- **Format :** CSV
- **Licence :** Licence Ouverte Paris

---

### arrondissements.geojson
Géométrie des 20 arrondissements parisiens.

| Champ | Type | Description |
|-------|------|-------------|
| c_ar | int | Numéro d'arrondissement |
| l_ar | string | Libellé officiel |
| l_aroff | string | Libellé quartier |
| surface | float | Surface en m² |
| geometry | Polygon | Contour géographique (WGS84) |

- **Source :** OpenData Paris
- **URL :** `https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/arrondissements/exports/geojson`
- **Format :** GeoJSON (WGS84)
- **Licence :** Licence Ouverte Paris

---

### revenus_france.csv
Revenus fiscaux des ménages par commune — France entière.

| Champ | Type | Description |
|-------|------|-------------|
| code_insee | string | Code INSEE commune (75101–75120 pour Paris) |
| revenu_median | float | Revenu disponible médian par unité de consommation (€/an) |

- **Source :** INSEE DGFiP — Revenu des Français à la commune
- **URL :** `https://static.data.gouv.fr/resources/revenu-des-francais-a-la-commune/20251210-134014/revenu-des-francais-a-la-commune-1765372688826.csv`
- **Périmètre :** 34 926 communes françaises ; filtré sur Paris → `revenus_paris.csv` (20 lignes)
- **Format :** CSV
- **Licence :** Licence Ouverte INSEE

---

### crimes_paris.csv
Statistiques de délinquance par arrondissement parisien et par indicateur.

| Champ | Type | Description |
|-------|------|-------------|
| CODGEO_2025 | string | Code INSEE (75101–75120 + 75056 Paris global) |
| annee | int | Année (2016–2025) |
| indicateur | string | Type d'infraction (15 catégories) |
| nombre | int | Nombre de faits constatés |
| taux_pour_mille | float | Taux pour 1 000 habitants (séparateur décimal `,`) |
| est_diffuse | string | `diff` = donnée publiée |
| insee_pop | int | Population de référence INSEE |
| insee_log | int | Nombre total de logements INSEE (résidences principales) |

- **Source :** SSMSI (Service Statistique Ministériel de la Sécurité Intérieure) — Ministère de l'Intérieur
- **URL :** `https://static.data.gouv.fr/resources/bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales/20260326-124144/donnee-data.gouv-2025-geographie2025-produit-le2026-02-03.csv.gz`
- **Périmètre :** Codes commençant par `75` (3 150 lignes) — données par arrondissement (75101–75120) disponibles
- **Note sur le calcul `crimes_pour_mille` :** Somme des taux/1000 des 14 indicateurs diffusés (hors "Usage de stupéfiants AFD" pour éviter double-compte), année 2025.
- **Format :** CSV gzip (séparateur `;`)
- **Licence :** Licence Ouverte

---

## Zone Silver (données nettoyées — Parquet)

### dvf_clean.parquet
DVF nettoyé et enrichi — 158 447 transactions retenues.

| Champ | Type | Règle |
|-------|------|-------|
| date_mutation | datetime | Parsing ISO |
| arrondissement | int | Extrait du code INSEE |
| prix_m2 | float | `valeur_fonciere / surface_reelle_bati` |
| annee | int | `date_mutation.year` |
| typo | string | T1 (≤1p) / T2 / T3 / T4 / T5+ (≥5p) |

**Règles de filtrage :**
- Surface > 9 m² (exclusion caves, parkings)
- Prix/m² entre 3 000 € et 50 000 € (exclusion outliers)
- Suppression des doublons stricts

---

### logements_sociaux_clean.parquet
4 174 programmes avec colonne `arrondissement` normalisée (int 1–20).

---

### revenus_clean.parquet
20 lignes — une par arrondissement. Colonnes : `code_insee`, `revenu_median`, `arrondissement`.

---

### crimes_clean.parquet
20 lignes — une par arrondissement. Colonnes : `arrondissement`, `crimes_pour_mille`, `population_ssmsi`.

---

### arrondissements_clean.geojson
GeoJSON normalisé avec champ `arrondissement` (int) unifié dans les propriétés.

---

## Zone Gold (données analytiques finales)

### arrondissements_enrichis.json + .parquet + .geojson
Table principale servant l'API et le dashboard.

| Champ | Type | Source | Description |
|-------|------|--------|-------------|
| num | int | — | Numéro d'arrondissement (1–20) |
| nom | string | — | Nom officiel |
| surnom | string | — | Quartier(s) emblématique(s) |
| code_insee | string | — | Code INSEE (75101–75120) |
| prix_medians | object | DVF data.gouv.fr | Prix médian €/m² par année {2021…2025} |
| nb_transactions | object | DVF data.gouv.fr | Nombre de ventes par année |
| logements_sociaux_pct | float | **RPLS 2022** | Part du parc locatif social (%) |
| nb_logements_sociaux | int | OpenData Paris | Nb de logements financés depuis 2001 |
| revenu_median_uc | float | INSEE DGFiP | Revenu médian disponible par UC (€/an) |
| population | int | SSMSI / INSEE | Population légale (millésime 2022) |
| superficie_km2 | float | OpenData Paris GeoJSON | Superficie calculée depuis la géométrie |
| densite_hab_km2 | float | Calculé | `population / superficie_km2` |
| crimes_pour_mille | float | SSMSI 2025 | Somme taux/1000 sur 14 indicateurs (année 2025) |
| variation_pct_2023 | float | DVF data.gouv.fr | Variation prix médian 2024→2025 (%) |
| repartition_pieces | object | DVF data.gouv.fr | Distribution typologies {T1…T5+} en % |

**Note sur `logements_sociaux_pct` :**
Issu du RPLS 2022 (Répertoire du Parc Locatif Social), Ministère chargé du Logement.
Calculé comme : nb logements locatifs sociaux / résidences principales (RP INSEE 2020) × 100.
Publication : https://www.statistiques.developpement-durable.gouv.fr/le-parc-locatif-social-au-1er-janvier-2022
Cette valeur diffère de `nb_logements_sociaux / insee_log` car ce dernier ne comptabilise que les programmes financés depuis 2001 (OpenData Paris), pas le stock total existant.

---

## Qualité des données

| Indicateur | Complétude | Source | Traçabilité |
|-----------|-----------|--------|------------|
| Prix médians | 100% (20 arr × 5 ans) | DVF data.gouv.fr | Calculé — `dvf_clean.parquet` |
| Logements sociaux % | 100% | RPLS 2022 (Ministère Logement) | Table `LOGSOC_PCT_RPLS` dans `aggregate.py` |
| Logements sociaux nb | 100% | OpenData Paris | Calculé — `logements_sociaux_clean.parquet` |
| Revenus médians | 100% | INSEE DGFiP | Calculé — `revenus_clean.parquet` |
| Population | 100% | SSMSI / INSEE 2022 | Calculé — `crimes_clean.parquet` |
| Criminalité | 100% | SSMSI 2025 | Calculé — `crimes_clean.parquet` |
| Transactions | 100% | DVF data.gouv.fr | Calculé — `dvf_clean.parquet` |
| Répartition pièces | 100% | DVF data.gouv.fr | Calculé — `dvf_clean.parquet` |
| Superficie | 100% | OpenData Paris GeoJSON | Calculé — `arrondissements_clean.geojson` |

---

## Traçabilité

Le manifest `data/bronze/manifest.json` enregistre pour chaque source :
- Timestamp d'extraction
- URL source
- Nombre de lignes récupérées
- Statut (ok / erreur)

---

*Urban Data Explorer — Meriem Bennacer — 2026*
