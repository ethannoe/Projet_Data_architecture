"""
Base non relationnelle TinyDB — Urban Data Explorer (C1.2)
Document store JSON : profils arrondissements + logs pipeline.

TinyDB est une base orientée documents (NoSQL) pure Python.
Chaque collection est un fichier JSON ; chaque entrée est un document libre.
Cas d'usage : données semi-structurées à schéma variable (prix_medians imbriqués,
repartition_pieces variable, logs d'exécution).
"""
from tinydb import TinyDB, Query
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

NOSQL_DIR = Path(__file__).parent.parent / "data" / "nosql"
NOSQL_DIR.mkdir(parents=True, exist_ok=True)

PROFILES_PATH   = NOSQL_DIR / "arrondissement_profiles.json"
PIPELINE_LOGS_PATH = NOSQL_DIR / "pipeline_logs.json"


def _db(path: Path) -> TinyDB:
    return TinyDB(path, sort_keys=True, indent=2, ensure_ascii=False)


# ── Écriture ────────────────────────────────────────────────────────────────

def write_profiles(arrondissements: list) -> None:
    """
    Stocke chaque arrondissement comme document NoSQL autonome.
    Le format document est naturel pour les objets imbriqués (prix_medians,
    repartition_pieces) qui seraient non-normaux en SQL.
    """
    with _db(PROFILES_PATH) as db:
        db.truncate()
        for a in arrondissements:
            doc = {
                "num":                   a["num"],
                "nom":                   a.get("nom"),
                "surnom":                a.get("surnom"),
                "code_insee":            a.get("code_insee", f"751{str(a['num']).zfill(2)}"),
                "prix_medians":          a.get("prix_medians", {}),
                "variation_pct":         a.get("variation_pct"),
                "logements_sociaux_pct": a.get("logements_sociaux_pct"),
                "revenu_median_uc":      a.get("revenu_median_uc"),
                "crimes_pour_mille":     a.get("crimes_pour_mille"),
                "population":            a.get("population"),
                "superficie_km2":        a.get("superficie_km2"),
                "repartition_pieces":    a.get("repartition_pieces", {}),
                "nb_transactions":       a.get("nb_transactions", {}),
                "updated_at":            datetime.now().isoformat(),
            }
            db.insert(doc)
    logger.info(f"NoSQL → {len(arrondissements)} profils → {PROFILES_PATH}")


def log_pipeline_run(metadata: dict, stats: dict) -> None:
    """Enregistre un run de pipeline (document variable sans schéma fixe)."""
    with _db(PIPELINE_LOGS_PATH) as db:
        db.insert({
            "timestamp":  datetime.now().isoformat(),
            "metadata":   metadata,
            "stats":      stats,
        })
    logger.info(f"NoSQL → Log pipeline enregistré → {PIPELINE_LOGS_PATH}")


# ── Lecture ──────────────────────────────────────────────────────────────────

def get_all_profiles() -> list:
    with _db(PROFILES_PATH) as db:
        return db.all()


def get_profile(num: int) -> dict | None:
    with _db(PROFILES_PATH) as db:
        Arr = Query()
        results = db.search(Arr.num == num)
        return results[0] if results else None


def search_profiles(min_prix: float = None, max_prix: float = None,
                    annee: int = 2023) -> list:
    """Recherche documentaire par plage de prix pour une année (requête NoSQL)."""
    with _db(PROFILES_PATH) as db:
        Arr = Query()
        def prix_match(prix_medians):
            p = prix_medians.get(str(annee))
            if p is None:
                return False
            if min_prix is not None and p < min_prix:
                return False
            if max_prix is not None and p > max_prix:
                return False
            return True
        return db.search(Arr.prix_medians.test(prix_match))


def get_pipeline_logs(limit: int = 10) -> list:
    with _db(PIPELINE_LOGS_PATH) as db:
        logs = db.all()
        return sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
