"""
Étape 3 : Nettoyage, Normalisation et Géocodage
Zone Bronze → Zone Silver
"""
import pandas as pd
import numpy as np
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BRONZE_DIR = Path("data/bronze")
SILVER_DIR = Path("data/silver")
SILVER_DIR.mkdir(parents=True, exist_ok=True)


def clean_dvf(path: Path = BRONZE_DIR / "dvf_paris.csv") -> pd.DataFrame:
    """
    Nettoyage du jeu DVF :
    - Suppression doublons
    - Filtrage sur ventes d'appartements valides
    - Normalisation des types (dates → datetime, prix → float)
    - Calcul du prix au m²
    - Filtrage outliers (prix/m² entre 3 000 et 50 000 €)
    """
    if not path.exists():
        logger.warning(f"Fichier DVF absent : {path}")
        return pd.DataFrame()

    logger.info("Nettoyage DVF...")
    df = pd.read_csv(path, dtype=str)

    # Types
    df["date_mutation"] = pd.to_datetime(df.get("date_mutation", pd.Series(dtype=str)), errors="coerce")
    df["valeur_fonciere"] = pd.to_numeric(df.get("valeur_fonciere", pd.Series()), errors="coerce")
    df["surface_reelle_bati"] = pd.to_numeric(df.get("surface_reelle_bati", pd.Series()), errors="coerce")
    df["nombre_pieces_principales"] = pd.to_numeric(
        df.get("nombre_pieces_principales", pd.Series()), errors="coerce"
    )
    df["arrondissement"] = pd.to_numeric(df.get("arrondissement", pd.Series()), errors="coerce")

    # Suppression doublons
    avant = len(df)
    df.drop_duplicates(inplace=True)
    logger.info(f"Doublons supprimés : {avant - len(df)}")

    # Filtrage lignes valides
    df = df.dropna(subset=["valeur_fonciere", "surface_reelle_bati", "date_mutation"])
    df = df[df["surface_reelle_bati"] > 9]  # < 9m² = données aberrantes
    df = df[df["valeur_fonciere"] > 1000]

    # Prix au m²
    df["prix_m2"] = df["valeur_fonciere"] / df["surface_reelle_bati"]

    # Outliers
    avant = len(df)
    df = df[(df["prix_m2"] >= 3000) & (df["prix_m2"] <= 50000)]
    logger.info(f"Outliers prix/m² supprimés : {avant - len(df)}")

    # Colonnes utiles
    cols = [
        "date_mutation", "arrondissement", "code_commune",
        "valeur_fonciere", "surface_reelle_bati", "prix_m2",
        "nombre_pieces_principales", "type_local",
    ]
    df = df[[c for c in cols if c in df.columns]].copy()
    df["annee"] = df["date_mutation"].dt.year

    # Typo pièces
    df["typo"] = df["nombre_pieces_principales"].apply(_code_typo)

    output = SILVER_DIR / "dvf_clean.parquet"
    df.to_parquet(output, index=False)
    logger.info(f"DVF silver → {output} ({len(df)} lignes)")
    return df


def _code_typo(n) -> str:
    if pd.isna(n):
        return "Inconnu"
    n = int(n)
    if n <= 1:
        return "T1"
    elif n == 2:
        return "T2"
    elif n == 3:
        return "T3"
    elif n == 4:
        return "T4"
    else:
        return "T5+"


def clean_logements_sociaux(path: Path = BRONZE_DIR / "logements_sociaux.csv") -> pd.DataFrame:
    """
    Nettoyage des logements sociaux.
    Standardise les codes arrondissement et les taux.
    """
    if not path.exists():
        logger.warning(f"Fichier logements sociaux absent : {path}")
        return pd.DataFrame()

    logger.info("Nettoyage logements sociaux...")
    df = pd.read_csv(path)

    # Tentative d'identification de la colonne arrondissement
    arr_col = next((c for c in df.columns if "arrondissement" in c.lower() or "arr" in c.lower()), None)
    if arr_col:
        df["arrondissement"] = pd.to_numeric(
            df[arr_col].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
        )
        df = df.dropna(subset=["arrondissement"])
        df["arrondissement"] = df["arrondissement"].astype(int)

    output = SILVER_DIR / "logements_sociaux_clean.parquet"
    df.to_parquet(output, index=False)
    logger.info(f"Logements sociaux silver → {output} ({len(df)} lignes)")
    return df


def clean_revenus_insee(path: Path = BRONZE_DIR / "revenus_paris.csv") -> pd.DataFrame:
    """
    Nettoyage des données revenus INSEE.
    Détection flexible des colonnes : Filosofi (MED20/MED21) ou IRCOM (revenu_moyen).
    """
    if not path.exists():
        logger.warning(f"Fichier revenus INSEE absent : {path}")
        return pd.DataFrame()

    logger.info("Nettoyage revenus INSEE...")
    df = pd.read_csv(path, dtype=str)
    logger.info(f"Colonnes disponibles : {list(df.columns)}")

    # ── Détection colonne code commune ───────────────────────────────────────
    code_col = next(
        (c for c in df.columns if c.upper() in ["CODGEO", "CODE_COMMUNE", "COM", "DEPCOM"]),
        None,
    )
    if code_col is None:
        for col in df.columns:
            vals = df[col].dropna().astype(str)
            if vals.str.match(r"^7510\d$|^7511\d$|^7512\d$").sum() >= 3:
                code_col = col
                break
    if code_col is None:
        logger.warning("Colonne code commune introuvable dans revenus.")
        return pd.DataFrame()

    df = df.rename(columns={code_col: "code_insee"})
    df["code_insee"] = df["code_insee"].astype(str).str.strip()

    # ── Détection colonne revenu médian ou moyen ──────────────────────────────
    # INSEE DGFiP : "[DISP] Médiane (€)" — Filosofi : MED20/MED21 — IRCOM : revenu_moyen
    median_col = next(
        (
            c
            for c in df.columns
            if c.upper() in ["MED21", "MED20", "MED19", "MEDIAN", "REVENU_MEDIAN"]
            or "médiane" in c.lower()
            or "mediane" in c.lower()
            or "med" == c.lower()
            or "revenu_moyen" in c.lower()
            or "fiscal_moyen" in c.lower()
        ),
        None,
    )

    result = df[["code_insee"]].copy()
    if median_col:
        result["revenu_median"] = pd.to_numeric(df[median_col], errors="coerce")
        logger.info(f"Colonne revenu détectée : {median_col}")
    else:
        # Cherche toute colonne numérique plausible (valeur > 5000 → revenu en €)
        for col in df.columns:
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.median() and 5000 < numeric.median() < 200000:
                result["revenu_median"] = numeric
                logger.info(f"Colonne revenu inférée par valeur : {col}")
                break
        else:
            logger.warning("Aucune colonne revenu trouvée.")

    # ── Colonnes optionnelles ─────────────────────────────────────────────────
    for src, dst in [("TP6021", "taux_pauvrete"), ("TP6020", "taux_pauvrete"), ("GI021", "gini"), ("GI020", "gini")]:
        if src in df.columns:
            result[dst] = pd.to_numeric(df[src], errors="coerce")

    # Numéro arrondissement depuis code INSEE (75101 → 1, 75120 → 20)
    result["arrondissement"] = pd.to_numeric(result["code_insee"].str[3:], errors="coerce")
    result = result.dropna(subset=["arrondissement"])
    result["arrondissement"] = result["arrondissement"].astype(int)

    output = SILVER_DIR / "revenus_clean.parquet"
    result.to_parquet(output, index=False)
    logger.info(f"INSEE silver → {output} ({len(result)} lignes)")
    return result


def clean_geojson(path: Path = BRONZE_DIR / "arrondissements.geojson") -> dict:
    """
    Normalise le GeoJSON : uniformise le champ 'arrondissement' dans les propriétés.
    """
    if not path.exists():
        logger.warning(f"GeoJSON absent : {path}")
        return {}

    logger.info("Nettoyage GeoJSON arrondissements...")
    with open(path, encoding="utf-8") as f:
        geojson = json.load(f)

    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        # OpenData Paris peut utiliser 'c_ar', 'l_ar', 'c_arinsee'…
        arr_num = None
        for key in ["c_ar", "arrondissement", "NUM_ARR", "numero"]:
            if key in props:
                try:
                    arr_num = int(props[key])
                    break
                except (ValueError, TypeError):
                    pass
        if arr_num:
            props["arrondissement"] = arr_num

    output = SILVER_DIR / "arrondissements_clean.geojson"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    logger.info(f"GeoJSON silver → {output}")
    return geojson


def clean_crimes_ssmsi(path: Path = BRONZE_DIR / "crimes_paris.csv") -> pd.DataFrame:
    """
    Nettoyage des données SSMSI — calcul du taux de criminalité par arrondissement.
    La base 2025 contient les 20 arrondissements parisiens (75101-75120).
    Méthode : somme des taux/1000 de tous les indicateurs diffusés (hors double-compte AFD)
              pour la dernière année disponible.
    """
    if not path.exists():
        logger.warning(f"Fichier crimes SSMSI absent : {path}")
        return pd.DataFrame()

    logger.info("Nettoyage crimes SSMSI (par arrondissement)...")
    df = pd.read_csv(path, dtype=str, low_memory=False)

    # Filtrer uniquement les 20 arrondissements (75101-75120)
    code_col = next((c for c in df.columns if c.upper().startswith("CODGEO")), None)
    PARIS_ARR_CODES = {f"751{str(i).zfill(2)}" for i in range(1, 21)}
    if code_col:
        df = df[df[code_col].astype(str).isin(PARIS_ARR_CODES)].copy()
    logger.info(f"Lignes arrondissements parisiens : {len(df)}")

    if df.empty:
        logger.warning("Aucune donnée par arrondissement — fallback sur Paris global.")
        return pd.DataFrame(columns=["arrondissement", "crimes_pour_mille", "population_ssmsi"])

    # Année la plus récente
    df["annee"] = pd.to_numeric(df["annee"], errors="coerce")
    annee_max = int(df["annee"].max())
    df = df[df["annee"] == annee_max].copy()
    logger.info(f"Année SSMSI retenue : {annee_max}")

    # Lignes diffusées uniquement
    if "est_diffuse" in df.columns:
        df = df[df["est_diffuse"].astype(str).str.strip() == "diff"].copy()

    # Exclure "Usage de stupéfiants (AFD)" pour éviter le double-compte
    if "indicateur" in df.columns:
        df = df[~df["indicateur"].astype(str).str.contains("AFD", na=False)].copy()

    # Conversion taux_pour_mille (virgule décimale française → point)
    df["taux"] = (
        df["taux_pour_mille"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )

    # Population de référence INSEE (même pour tous les indicateurs d'un arrondissement)
    df["pop"] = pd.to_numeric(df["insee_pop"], errors="coerce")

    # Agrégation par arrondissement : somme des taux sur tous les indicateurs
    result_rows = []
    for code in sorted(PARIS_ARR_CODES):
        arr_num = int(code[3:])
        subset = df[df[code_col] == code]
        if subset.empty:
            continue
        total_taux = subset["taux"].sum()
        pop = subset["pop"].dropna().iloc[0] if subset["pop"].notna().any() else None
        result_rows.append({
            "arrondissement": arr_num,
            "crimes_pour_mille": round(total_taux, 1),
            "population_ssmsi": int(pop) if pop else None,
        })
        logger.info(f"  {arr_num:2d}ème → crimes/1000 : {total_taux:.1f} (pop SSMSI : {pop:.0f})")

    result = pd.DataFrame(result_rows) if result_rows else pd.DataFrame(
        columns=["arrondissement", "crimes_pour_mille", "population_ssmsi"]
    )
    output = SILVER_DIR / "crimes_clean.parquet"
    result.to_parquet(output, index=False)
    logger.info(f"Crimes silver → {output} ({len(result)} arrondissements)")
    return result


def run_cleaning() -> dict:
    """Pipeline de nettoyage complet — Zone Silver."""
    logger.info("=" * 50)
    logger.info("ZONE SILVER — DÉMARRAGE NETTOYAGE")
    logger.info("=" * 50)

    results = {
        "dvf": clean_dvf(),
        "logements_sociaux": clean_logements_sociaux(),
        "revenus": clean_revenus_insee(),
        "crimes": clean_crimes_ssmsi(),
        "geojson": clean_geojson(),
    }

    logger.info("=" * 50)
    logger.info("ZONE SILVER — NETTOYAGE TERMINÉ")
    logger.info("=" * 50)
    return results


if __name__ == "__main__":
    run_cleaning()
