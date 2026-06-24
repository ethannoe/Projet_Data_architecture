"""
Étape 4 : Agrégation et Enrichissement
Zone Silver → Zone Gold
Produit : arrondissements_enrichis.json (table principale)
"""
import pandas as pd
import numpy as np
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SILVER_DIR = Path("data/silver")
GOLD_DIR = Path("data/gold")
GOLD_DIR.mkdir(parents=True, exist_ok=True)

# DVF géolocalisé couvre Jan 2021 – Déc 2025
ANNEES = [2021, 2022, 2023, 2024, 2025]

# Taux de logements sociaux par arrondissement — RPLS 2022
# Source : Répertoire du Parc Locatif Social (RPLS), Ministère chargé du Logement
# https://www.statistiques.developpement-durable.gouv.fr/le-parc-locatif-social-au-1er-janvier-2022
# Méthode : nb logements locatifs sociaux / total résidences principales (RP INSEE 2020) * 100
LOGSOC_PCT_RPLS = {
    1: 4.3,   2: 5.1,   3: 7.8,   4: 6.9,   5: 7.2,
    6: 3.2,   7: 4.1,   8: 4.8,   9: 7.9,  10: 14.8,
   11: 15.6, 12: 17.9, 13: 26.7, 14: 19.2, 15: 15.8,
   16: 6.7,  17: 14.3, 18: 23.8, 19: 34.5, 20: 27.9,
}


def load_superficie_from_geojson() -> dict:
    """Superficie réelle des arrondissements en km² depuis le GeoJSON OpenData Paris."""
    geojson_path = SILVER_DIR / "arrondissements_clean.geojson"
    if not geojson_path.exists():
        return {}
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    result = {}
    for feature in gj.get("features", []):
        props = feature.get("properties", {})
        arr_num = props.get("arrondissement") or props.get("c_ar")
        surface_m2 = props.get("surface")
        if arr_num and surface_m2:
            result[int(arr_num)] = round(float(surface_m2) / 1_000_000, 3)  # m² → km²
    return result


def aggregate_prix_medians(dvf: pd.DataFrame) -> dict:
    """
    Calcule le prix médian par arrondissement et par année.
    Retourne un dict : {arrondissement: {annee: prix_median}}
    """
    if dvf.empty:
        logger.warning("DVF vide, agrégation ignorée.")
        return {}

    result = {}
    for arr in range(1, 21):
        result[arr] = {}
        for annee in ANNEES:
            subset = dvf[(dvf["arrondissement"] == arr) & (dvf["annee"] == annee)]
            if len(subset) > 10:
                result[arr][str(annee)] = round(float(subset["prix_m2"].median()), 0)
            else:
                result[arr][str(annee)] = None

    return result


def aggregate_repartition_pieces(dvf: pd.DataFrame) -> dict:
    """
    Calcule la répartition des typologies (T1…T5+) par arrondissement.
    """
    if dvf.empty:
        return {}

    result = {}
    for arr in range(1, 21):
        subset = dvf[dvf["arrondissement"] == arr]
        if subset.empty:
            continue
        counts = subset["typo"].value_counts(normalize=True) * 100
        result[arr] = {
            typo: round(float(counts.get(typo, 0)), 1)
            for typo in ["T1", "T2", "T3", "T4", "T5+"]
        }
    return result


def aggregate_nb_transactions(dvf: pd.DataFrame) -> dict:
    """Compte le nombre de transactions par arrondissement et par année."""
    if dvf.empty:
        return {}

    result = {}
    for arr in range(1, 21):
        result[arr] = {}
        for annee in ANNEES:
            n = len(dvf[(dvf["arrondissement"] == arr) & (dvf["annee"] == annee)])
            result[arr][str(annee)] = n
    return result


def calculer_variation(prix_medians: dict, arr: int) -> float | None:
    """Variation annuelle N-1→N en % (utilise la dernière paire d'années consécutives disponible)."""
    pm = prix_medians.get(arr, {})
    available = sorted([int(y) for y, v in pm.items() if v is not None])
    if len(available) < 2:
        return None
    yn, y_prev = available[-1], available[-2]
    p_prev = pm.get(str(y_prev))
    p_n = pm.get(str(yn))
    if p_prev and p_n and p_prev > 0:
        return round(((p_n - p_prev) / p_prev) * 100, 1)
    return None


def aggregate_logements_sociaux(logsoc: pd.DataFrame) -> dict:
    """Compte de logements sociaux par arrondissement depuis OpenData Paris."""
    if logsoc.empty or "arrondissement" not in logsoc.columns:
        return {}
    result = {}
    for arr in range(1, 21):
        subset = logsoc[logsoc["arrondissement"] == arr]
        if "nb_logmt_total" in subset.columns:
            total = int(subset["nb_logmt_total"].sum())
            result[arr] = total
    return result


def merge_gold_table(
    prix_medians: dict,
    nb_transactions: dict,
    repartition_pieces: dict,
    revenus: pd.DataFrame,
    crimes: pd.DataFrame = None,
    logsoc: pd.DataFrame = None,
) -> list:
    """
    Fusionne toutes les agrégations + charge le gold existant comme fallback.
    Retourne la liste des arrondissements enrichis.
    """
    # Charge le gold existant (données pré-calculées réalistes) comme base
    gold_path = GOLD_DIR / "arrondissements_enrichis.json"
    if gold_path.exists():
        with open(gold_path, encoding="utf-8") as f:
            gold_existing = {a["num"]: a for a in json.load(f)["arrondissements"]}
    else:
        gold_existing = {}

    superficie = load_superficie_from_geojson()

    merged = []
    for arr in range(1, 21):
        base = gold_existing.get(arr, {"num": arr})

        # Surface réelle depuis GeoJSON (source OpenData Paris)
        if superficie.get(arr):
            base["superficie_km2"] = superficie[arr]

        # Écrase avec les vraies données calculées si disponibles
        if prix_medians.get(arr):
            computed = {k: v for k, v in prix_medians[arr].items() if v is not None}
            if len(computed) >= 3:
                base["prix_medians"] = prix_medians[arr]

        if nb_transactions.get(arr):
            base["nb_transactions"] = nb_transactions[arr]

        if repartition_pieces.get(arr):
            base["repartition_pieces"] = repartition_pieces[arr]

        # Fusion revenus INSEE si disponibles
        if not revenus.empty and "arrondissement" in revenus.columns:
            row = revenus[revenus["arrondissement"] == arr]
            if not row.empty:
                if "revenu_median" in row.columns:
                    base["revenu_median_uc"] = float(row["revenu_median"].iloc[0])
                if "taux_pauvrete" in row.columns:
                    base["taux_pauvrete"] = float(row["taux_pauvrete"].iloc[0])
                if "gini" in row.columns:
                    base["gini"] = float(row["gini"].iloc[0])

        # Logements sociaux — nombre depuis OpenData Paris, taux depuis RPLS 2022
        if logsoc is not None:
            logsoc_counts = aggregate_logements_sociaux(logsoc)
            if logsoc_counts.get(arr):
                base["nb_logements_sociaux"] = logsoc_counts[arr]
        # Taux officiel RPLS 2022 (source tracée dans LOGSOC_PCT_RPLS)
        base["logements_sociaux_pct"] = LOGSOC_PCT_RPLS.get(arr, base.get("logements_sociaux_pct"))

        base["variation_pct"] = calculer_variation(prix_medians, arr) or base.get("variation_pct")

        # Criminalité SSMSI — taux réel par arrondissement
        if crimes is not None and not crimes.empty and "crimes_pour_mille" in crimes.columns:
            if "arrondissement" in crimes.columns:
                row_c = crimes[crimes["arrondissement"] == arr]
                if not row_c.empty:
                    taux = row_c["crimes_pour_mille"].iloc[0]
                    if not pd.isna(taux):
                        base["crimes_pour_mille"] = float(taux)
                    # Population réelle depuis SSMSI
                    if "population_ssmsi" in row_c.columns:
                        pop_ssmsi = row_c["population_ssmsi"].iloc[0]
                        if pop_ssmsi and not pd.isna(pop_ssmsi):
                            base["population"] = int(pop_ssmsi)
                            # Recalcul densité depuis surface GeoJSON si disponible
                            if base.get("superficie_km2"):
                                base["densite_hab_km2"] = round(int(pop_ssmsi) / base["superficie_km2"])
            else:
                # Fallback ville entière
                taux = crimes["crimes_pour_mille"].iloc[0]
                if not pd.isna(taux):
                    base["crimes_pour_mille"] = float(taux)

        merged.append(base)

    return merged


def export_gold(arrondissements: list) -> None:
    """Exporte la couche gold en JSON + Parquet + GeoJSON enrichi."""
    metadata = {
        "description": "Données agrégées marché immobilier Paris — couche Gold",
        "sources": [
            "DVF (data.gouv.fr)",
            "OpenData Paris",
            "INSEE Filosofi 2020",
        ],
        "date_production": pd.Timestamp.now().isoformat(),
        "periode": "2021-2025",
    }

    # JSON principal
    gold = {"metadata": metadata, "arrondissements": arrondissements}
    output = GOLD_DIR / "arrondissements_enrichis.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(gold, f, ensure_ascii=False, indent=2)
    logger.info(f"Gold JSON → {output}")

    # Parquet (pour usage analytique / Jupyter)
    df = pd.json_normalize(arrondissements)
    df.to_parquet(GOLD_DIR / "arrondissements_enrichis.parquet", index=False)
    logger.info(f"Gold Parquet → {GOLD_DIR}/arrondissements_enrichis.parquet")

    # GeoJSON enrichi (Silver GeoJSON + indicateurs Gold)
    geojson_src = SILVER_DIR / "arrondissements_clean.geojson"
    if not geojson_src.exists():
        geojson_src = Path("data/bronze/arrondissements.geojson")
    if geojson_src.exists():
        with open(geojson_src, encoding="utf-8") as f:
            geojson = json.load(f)

        gold_by_arr = {a["num"]: a for a in arrondissements}

        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            arr_num = props.get("arrondissement") or props.get("c_ar")
            if arr_num:
                try:
                    arr_num = int(arr_num)
                    a = gold_by_arr.get(arr_num, {})
                    pm = a.get("prix_medians", {})
                    props["arrondissement"]        = arr_num
                    props["nom"]                   = a.get("nom", f"{arr_num}ème")
                    props["surnom"]                = a.get("surnom", "")
                    props["prix_m2_2021"]          = pm.get("2021")
                    props["prix_m2_2022"]          = pm.get("2022")
                    props["prix_m2_2023"]          = pm.get("2023")
                    props["prix_m2_2024"]          = pm.get("2024")
                    props["prix_m2_2025"]          = pm.get("2025")
                    props["logements_sociaux_pct"] = a.get("logements_sociaux_pct")
                    props["revenu_median_uc"]      = a.get("revenu_median_uc")
                    props["population"]            = a.get("population")
                    props["densite_hab_km2"]       = a.get("densite_hab_km2")
                    props["crimes_pour_mille"]     = a.get("crimes_pour_mille")
                    props["variation_pct"]         = a.get("variation_pct")
                    props["superficie_km2"]        = a.get("superficie_km2")
                except (ValueError, TypeError):
                    pass

        geojson["metadata"] = metadata
        geojson_out = GOLD_DIR / "arrondissements_enrichis.geojson"
        with open(geojson_out, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)
        logger.info(f"Gold GeoJSON → {geojson_out}")
    else:
        logger.warning("GeoJSON source introuvable — export GeoJSON Gold ignoré.")


def run_aggregation() -> list:
    """Pipeline d'agrégation complet — Zone Gold."""
    logger.info("=" * 50)
    logger.info("ZONE GOLD — DÉMARRAGE AGRÉGATION")
    logger.info("=" * 50)

    # Chargement Silver
    dvf_path = SILVER_DIR / "dvf_clean.parquet"
    dvf = pd.read_parquet(dvf_path) if dvf_path.exists() else pd.DataFrame()

    revenus_path = SILVER_DIR / "revenus_clean.parquet"
    revenus = pd.read_parquet(revenus_path) if revenus_path.exists() else pd.DataFrame()

    crimes_path = SILVER_DIR / "crimes_clean.parquet"
    crimes = pd.read_parquet(crimes_path) if crimes_path.exists() else pd.DataFrame()

    logsoc_path = SILVER_DIR / "logements_sociaux_clean.parquet"
    logsoc = pd.read_parquet(logsoc_path) if logsoc_path.exists() else pd.DataFrame()

    if not dvf.empty:
        logger.info(f"DVF silver chargé : {len(dvf)} lignes")
    else:
        logger.warning("DVF silver absent — utilisation des données gold pré-calculées.")

    if not revenus.empty:
        logger.info(f"Revenus INSEE silver chargé : {len(revenus)} lignes")

    if not crimes.empty:
        logger.info(f"Crimes SSMSI silver chargé : {len(crimes)} lignes")

    prix_medians = aggregate_prix_medians(dvf)
    nb_transactions = aggregate_nb_transactions(dvf)
    repartition_pieces = aggregate_repartition_pieces(dvf)

    arrondissements = merge_gold_table(prix_medians, nb_transactions, repartition_pieces, revenus, crimes, logsoc)
    export_gold(arrondissements)

    # ── Bases de données ───────────────────────────────────────────────────────
    # SQL (SQLite) — données structurées avec schéma relationnel (C1.1)
    try:
        from database.sql_db import write_gold_to_sql
        write_gold_to_sql(arrondissements)
    except ImportError:
        logger.warning("sqlalchemy absent — base SQL ignorée.")
    except Exception as exc:
        logger.error(f"Erreur écriture SQL : {exc}")

    # NoSQL (TinyDB) — profils documents JSON + log pipeline (C1.2)
    try:
        from database.nosql_db import write_profiles, log_pipeline_run
        write_profiles(arrondissements)
        log_pipeline_run(
            {"zone": "gold", "periode": "2021-2025"},
            {
                "nb_arrondissements": len(arrondissements),
                "nb_lignes_dvf":      len(dvf) if not dvf.empty else 0,
                "nb_lignes_revenus":  len(revenus) if not revenus.empty else 0,
                "nb_lignes_crimes":   len(crimes) if not crimes.empty else 0,
            },
        )
    except ImportError:
        logger.warning("tinydb absent — base NoSQL ignorée.")
    except Exception as exc:
        logger.error(f"Erreur écriture NoSQL : {exc}")

    logger.info("=" * 50)
    logger.info("ZONE GOLD — AGRÉGATION TERMINÉE")
    logger.info("=" * 50)
    return arrondissements


if __name__ == "__main__":
    run_aggregation()
