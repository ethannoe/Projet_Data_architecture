"""
Étape 2 : Ingestion & Collecte des Données
Sources : DVF géolocalisé (data.gouv.fr), OpenData Paris, INSEE, SSMSI
"""
import requests
import pandas as pd
import json
import os
import gzip
import io
import tempfile
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BRONZE_DIR = Path("data/bronze")
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

# Codes INSEE des arrondissements parisiens (75101 → 75120)
PARIS_ARR_CODES = set(f"751{str(i).zfill(2)}" for i in range(1, 21))

HEADERS = {
    "User-Agent": "UrbanDataExplorer/1.0 (projet académique)"
}


def fetch_dvf_par_arrondissement() -> pd.DataFrame:
    """
    Télécharge le fichier DVF géolocalisé national et filtre pour Paris.
    Source : data.gouv.fr — DVF géolocalisé (Jan 2021 – Déc 2025), ~523 MB compressé.
    Filtre : nature_mutation=Vente, type_local=Appartement, code_commune 75101-75120.
    """
    output = BRONZE_DIR / "dvf_paris.csv"

    # Réutilise le fichier existant si déjà téléchargé
    if output.exists() and output.stat().st_size > 1_000_000:
        logger.info(f"DVF Paris déjà présent ({output.stat().st_size // 1024} KB) — chargement direct.")
        return pd.read_csv(output, dtype={"code_commune": str})

    url = (
        "https://static.data.gouv.fr/resources/"
        "demandes-de-valeurs-foncieres-geolocalisees/"
        "20260424-090024/dvf.csv.gz"
    )

    logger.info("DVF → Téléchargement fichier national géolocalisé (streaming)…")

    tmp_path = None
    try:
        resp = requests.get(url, headers=HEADERS, stream=True, timeout=1800)
        resp.raise_for_status()

        # Sauvegarde temporaire sur disque pour éviter l'overflow mémoire
        tmp_fd, tmp_str = tempfile.mkstemp(suffix=".csv.gz")
        tmp_path = Path(tmp_str)
        downloaded = 0
        last_logged = 0
        with os.fdopen(tmp_fd, "wb") as f:
            for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                mb = downloaded / 1024 / 1024
                if int(mb / 20) > last_logged:
                    last_logged = int(mb / 20)
                    logger.info(f"  Téléchargé : {mb:.0f} MB")

        logger.info(f"Téléchargement terminé : {downloaded / 1024 / 1024:.0f} MB")
        logger.info("Filtrage Paris en cours (chunked)…")

        all_chunks = []
        total_rows = 0
        paris_rows = 0

        with gzip.open(tmp_path, "rt", encoding="utf-8") as f:
            for chunk in pd.read_csv(
                f,
                chunksize=200_000,
                dtype={"code_commune": str, "code_departement": str},
                low_memory=False,
            ):
                total_rows += len(chunk)
                paris = chunk[
                    chunk["code_commune"].isin(PARIS_ARR_CODES)
                    & (chunk["nature_mutation"] == "Vente")
                    & (chunk["type_local"] == "Appartement")
                ]
                if len(paris) > 0:
                    all_chunks.append(paris)
                    paris_rows += len(paris)
                if total_rows % 1_000_000 < 200_000:
                    logger.info(
                        f"  Lignes lues : {total_rows:,} | Transactions Paris : {paris_rows:,}"
                    )

        tmp_path.unlink()

        if not all_chunks:
            logger.warning("Aucune transaction DVF Paris trouvée.")
            return pd.DataFrame()

        df = pd.concat(all_chunks, ignore_index=True)
        df["arrondissement"] = df["code_commune"].str[3:].astype(int)
        df.to_csv(output, index=False, encoding="utf-8")
        logger.info(f"DVF Paris → {output} ({len(df):,} transactions, 2021–2025)")
        return df

    except Exception as e:
        logger.error(f"Erreur DVF : {e}")
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        return pd.DataFrame()


def fetch_logements_sociaux() -> pd.DataFrame:
    """
    Logements sociaux financés à Paris — OpenData Paris.
    Dataset : logements-sociaux-finances-a-paris
    """
    logger.info("Logements sociaux → OpenData Paris…")
    url = (
        "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
        "logements-sociaux-finances-a-paris/exports/csv"
        "?delimiter=%2C&list_separator=%2C&quote_all=false&with_bom=true"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        output = BRONZE_DIR / "logements_sociaux.csv"
        output.write_bytes(resp.content)
        df = pd.read_csv(output)
        logger.info(f"Logements sociaux → {len(df)} lignes")
        return df
    except Exception as e:
        logger.error(f"Erreur logements sociaux : {e}")
        return pd.DataFrame()


def fetch_geojson_arrondissements() -> dict:
    """GeoJSON des arrondissements parisiens — OpenData Paris."""
    logger.info("GeoJSON arrondissements → OpenData Paris…")
    url = (
        "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
        "arrondissements/exports/geojson"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        geojson = resp.json()
        output = BRONZE_DIR / "arrondissements.geojson"
        output.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
        logger.info(f"GeoJSON → {len(geojson.get('features', []))} features")
        return geojson
    except Exception as e:
        logger.error(f"Erreur GeoJSON : {e}")
        return {}


def fetch_revenus_insee() -> pd.DataFrame:
    """
    Revenus fiscaux par commune — INSEE via data.gouv.fr.
    Source : Revenu des Français à la commune (2021).
    """
    logger.info("Revenus INSEE → data.gouv.fr…")
    url = (
        "https://static.data.gouv.fr/resources/revenu-des-francais-a-la-commune/"
        "20251210-134014/revenu-des-francais-a-la-commune-1765372688826.csv"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=120)
        resp.raise_for_status()
        raw_path = BRONZE_DIR / "revenus_france.csv"
        raw_path.write_bytes(resp.content)

        # Détection automatique du séparateur
        sample = resp.content[:4096].decode("utf-8", errors="replace")
        sep = ";" if sample.count(";") > sample.count(",") else ","

        df = pd.read_csv(raw_path, sep=sep, encoding="utf-8", dtype=str)
        logger.info(f"INSEE colonnes : {list(df.columns[:12])}")

        # Détection colonne code commune
        code_col = next(
            (
                c
                for c in df.columns
                if c.upper() in ["CODGEO", "CODE_COMMUNE", "COM", "DEPCOM", "CODE.COMMUNE"]
            ),
            None,
        )
        if code_col is None:
            for col in df.columns:
                vals = df[col].dropna().astype(str)
                if vals.str.match(r"^7510\d$|^7511\d$|^7512\d$").sum() >= 3:
                    code_col = col
                    break

        paris_codes = PARIS_ARR_CODES | {"75056"}
        if code_col:
            df_paris = df[df[code_col].astype(str).isin(paris_codes)].copy()
            df_paris.to_csv(BRONZE_DIR / "revenus_paris.csv", index=False, encoding="utf-8")
            logger.info(f"INSEE Paris → {len(df_paris)} lignes (colonne : {code_col})")
            return df_paris
        else:
            logger.warning("Colonne code commune introuvable — fichier entier conservé.")
            df.to_csv(BRONZE_DIR / "revenus_paris.csv", index=False, encoding="utf-8")
            return df

    except Exception as e:
        logger.error(f"Erreur INSEE revenus : {e}")
        return pd.DataFrame()


def fetch_crimes_paris() -> pd.DataFrame:
    """
    Délinquance par commune — SSMSI via data.gouv.fr (fichier gzip).
    Filtre : département 75 (Paris).
    """
    logger.info("Crimes & délits → SSMSI data.gouv.fr (gzip)…")
    url = (
        "https://static.data.gouv.fr/resources/"
        "bases-statistiques-communale-departementale-et-regionale-de-la-delinquance"
        "-enregistree-par-la-police-et-la-gendarmerie-nationales/"
        "20260326-124144/"
        "donnee-data.gouv-2025-geographie2025-produit-le2026-02-03.csv.gz"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=300)
        resp.raise_for_status()

        # SSMSI utilise le séparateur ";" et décimaux français (",")
        with gzip.open(io.BytesIO(resp.content), "rt", encoding="utf-8") as f:
            df = pd.read_csv(f, sep=";", low_memory=False, dtype=str)

        logger.info(f"SSMSI colonnes : {list(df.columns)}")

        # Code commune : CODGEO_2025 (5 chiffres, ex. "75056" pour Paris)
        # Paris est une commune unique (75056) dans la base SSMSI nationale.
        code_col = next(
            (c for c in df.columns if c.upper().startswith("CODGEO")),
            None,
        )
        if code_col:
            df_paris = df[df[code_col].astype(str).str.startswith("75")].copy()
        else:
            logger.warning("Colonne CODGEO introuvable — données complètes gardées.")
            df_paris = df.copy()

        output = BRONZE_DIR / "crimes_paris.csv"
        df_paris.to_csv(output, index=False, encoding="utf-8")
        logger.info(f"Crimes Paris → {output} ({len(df_paris)} lignes)")
        return df_paris

    except Exception as e:
        logger.error(f"Erreur SSMSI : {e}")
        return pd.DataFrame()


def run_ingestion() -> dict:
    """Pipeline d'ingestion complet — Zone Bronze."""
    logger.info("=" * 50)
    logger.info("ZONE BRONZE — DÉMARRAGE INGESTION")
    logger.info(f"Timestamp : {datetime.now().isoformat()}")
    logger.info("=" * 50)

    results = {
        "dvf": fetch_dvf_par_arrondissement(),
        "logements_sociaux": fetch_logements_sociaux(),
        "geojson": fetch_geojson_arrondissements(),
        "revenus": fetch_revenus_insee(),
        "crimes": fetch_crimes_paris(),
    }

    manifest = {
        "timestamp": datetime.now().isoformat(),
        "zone": "bronze",
        "sources": {
            "dvf": {
                "lignes": len(results["dvf"]),
                "statut": "ok" if len(results["dvf"]) > 0 else "erreur",
                "url": "https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres-geolocalisees/20260424-090024/dvf.csv.gz",
                "periode": "2021-2025",
            },
            "logements_sociaux": {
                "lignes": len(results["logements_sociaux"]),
                "statut": "ok" if len(results["logements_sociaux"]) > 0 else "erreur",
                "url": "https://opendata.paris.fr/explore/dataset/logements-sociaux-finances-a-paris/",
            },
            "geojson": {
                "features": len(results["geojson"].get("features", [])),
                "statut": "ok" if results["geojson"] else "erreur",
                "url": "https://opendata.paris.fr/explore/dataset/arrondissements/",
            },
            "revenus_insee": {
                "lignes": len(results["revenus"]),
                "statut": "ok" if len(results["revenus"]) > 0 else "erreur",
                "url": "https://static.data.gouv.fr/resources/revenu-des-francais-a-la-commune/20251210-134014/revenu-des-francais-a-la-commune-1765372688826.csv",
            },
            "crimes": {
                "lignes": len(results["crimes"]),
                "statut": "ok" if len(results["crimes"]) > 0 else "erreur",
                "url": "https://static.data.gouv.fr/resources/bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales/20260326-124144/donnee-data.gouv-2025-geographie2025-produit-le2026-02-03.csv.gz",
            },
        },
    }

    with open(BRONZE_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info("=" * 50)
    logger.info("ZONE BRONZE — INGESTION TERMINÉE")
    logger.info("=" * 50)
    return results


if __name__ == "__main__":
    run_ingestion()
