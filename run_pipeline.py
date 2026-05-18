"""
Urban Data Explorer — Orchestrateur pipeline complet
Exécute les 3 étapes : Bronze → Silver → Gold
"""
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    start = datetime.now()
    logger.info("=" * 60)
    logger.info("URBAN DATA EXPLORER — PIPELINE COMPLET")
    logger.info(f"Démarrage : {start.isoformat()}")
    logger.info("=" * 60)

    # ── Étape 1 : Ingestion (Zone Bronze) ────────────────────────────
    logger.info("\n[1/3] INGESTION — Zone Bronze")
    try:
        from pipeline.ingest import run_ingestion
        results_bronze = run_ingestion()
        dvf_ok = len(results_bronze.get("dvf", [])) > 0
        logger.info(f"  DVF           : {'OK' if dvf_ok else 'FALLBACK GOLD'}")
        logger.info(f"  GeoJSON       : {'OK' if results_bronze.get('geojson') else 'ERREUR'}")
        logger.info(f"  Log. sociaux  : {'OK' if len(results_bronze.get('logements_sociaux', [])) > 0 else 'ERREUR'}")
        logger.info(f"  INSEE revenus : {'OK' if len(results_bronze.get('revenus', [])) > 0 else 'ERREUR'}")
        logger.info(f"  Crimes SSMSI  : {'OK' if len(results_bronze.get('crimes', [])) > 0 else 'ERREUR'}")
    except Exception as e:
        logger.error(f"  Ingestion échouée : {e}")
        logger.warning("  → Poursuite avec données Gold existantes.")

    # ── Étape 2 : Nettoyage (Zone Silver) ────────────────────────────
    logger.info("\n[2/3] NETTOYAGE — Zone Silver")
    try:
        from pipeline.clean import run_cleaning
        run_cleaning()
        logger.info("  Nettoyage terminé.")
    except Exception as e:
        logger.error(f"  Nettoyage échoué : {e}")
        logger.warning("  → Poursuite avec données Gold existantes.")

    # ── Étape 3 : Agrégation (Zone Gold) ─────────────────────────────
    logger.info("\n[3/3] AGRÉGATION — Zone Gold")
    try:
        from pipeline.aggregate import run_aggregation
        arrondissements = run_aggregation()
        logger.info(f"  Gold produit : {len(arrondissements)} arrondissements.")
    except Exception as e:
        logger.error(f"  Agrégation échouée : {e}")
        sys.exit(1)

    # ── Résumé ────────────────────────────────────────────────────────
    duration = (datetime.now() - start).total_seconds()
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE TERMINÉ")
    logger.info(f"Durée totale : {duration:.1f}s")
    logger.info("Données disponibles dans : data/gold/arrondissements_enrichis.json")
    logger.info("Lancer l'API : uvicorn api.main:app --reload --port 8000")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
