"""
 API Backend — Urban Data Explorer
FastAPI — expose les données Gold pour le dashboard frontend
Bases : SQLite (SQL, C1.1) + TinyDB (NoSQL, C1.2)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import logging
import requests as _requests
from typing import Optional


def _int(value: Optional[str], default: Optional[int] = None) -> Optional[int]:
    """Parse un query param string en int, retourne default si invalide."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _float(value: Optional[str], default: Optional[float] = None) -> Optional[float]:
    """Parse un query param string en float, retourne default si invalide."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

logger = logging.getLogger(__name__)


def _init_databases() -> None:
    """Initialise SQLite et TinyDB depuis le Gold JSON si les fichiers DB n'existent pas."""
    try:
        from database.sql_db import DB_PATH, write_gold_to_sql
        from database.nosql_db import PROFILES_PATH, write_profiles

        if not DB_PATH.exists() or not PROFILES_PATH.exists():
            data = load_gold()
            arrs = data["arrondissements"]
            write_gold_to_sql(arrs)
            write_profiles(arrs)
            logger.info("Bases SQL et NoSQL initialisées depuis Gold JSON.")
    except Exception as exc:
        logger.warning(f"Init DB ignorée : {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_databases()
    yield


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="Urban Data Explorer API",
    description=(
        "API REST — marché immobilier parisien arrondissement par arrondissement. "
        "Données Gold servies depuis JSON (endpoints principaux), "
        "SQLite/SQLAlchemy (endpoints /db/*) et TinyDB (endpoints /nosql/*)."
    ),
    version="1.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = []
    for error in exc.errors():
        loc = " → ".join(str(p) for p in error["loc"] if p not in ("body", "query", "path"))
        messages.append(f"{loc}: {error['msg']}" if loc else error["msg"])
    return JSONResponse(
        status_code=400,
        content={"detail": "Paramètres invalides", "erreurs": messages},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

GOLD_DIR = Path(__file__).parent.parent / "data" / "gold"
BRONZE_DIR = Path(__file__).parent.parent / "data" / "bronze"


def load_gold() -> dict:
    path = GOLD_DIR / "arrondissements_enrichis.json"
    if not path.exists():
        raise FileNotFoundError(f"Gold data introuvable : {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_arr(num: int) -> dict:
    data = load_gold()
    for a in data["arrondissements"]:
        if a["num"] == num:
            return a
    raise HTTPException(status_code=404, detail=f"Arrondissement {num} introuvable.")


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
@limiter.limit("60/minute")
def root(request: Request):
    return {"status": "ok", "api": "Urban Data Explorer", "version": "1.0.0"}


@app.get("/health", tags=["health"])
@limiter.limit("60/minute")
def health(request: Request):
    try:
        data = load_gold()
        return {
            "status": "ok",
            "arrondissements_chargés": len(data["arrondissements"]),
            "période": data["metadata"]["periode"],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── Arrondissements ──────────────────────────────────────────────────────────

@app.get("/arrondissements", tags=["arrondissements"])
@limiter.limit("60/minute")
def list_arrondissements(request: Request):
    """Retourne la liste complète des arrondissements avec tous les indicateurs."""
    return load_gold()


@app.get("/arrondissements/{num}", tags=["arrondissements"])
@limiter.limit("60/minute")
def get_arrondissement(request: Request, num: int):
    """Retourne les données complètes pour un arrondissement donné (1-20)."""
    if not 1 <= num <= 20:
        raise HTTPException(status_code=400, detail="Numéro d'arrondissement invalide (1-20).")
    return get_arr(num)


# ── Prix ─────────────────────────────────────────────────────────────────────

@app.get("/prix", tags=["prix"])
@limiter.limit("60/minute")
def get_prix(request: Request, annee: Optional[str] = Query(None, description="Année (2021-2025)")):
    """
    Prix médians par arrondissement.
    Sans paramètre → toutes les années.
    Avec ?annee=2023 → prix 2023 uniquement.
    """
    annee = _int(annee)
    data = load_gold()
    result = []
    for a in data["arrondissements"]:
        entry = {
            "num": a["num"],
            "nom": a["nom"],
            "surnom": a.get("surnom", ""),
        }
        if annee:
            prix = a.get("prix_medians", {}).get(str(annee))
            if prix is None:
                continue
            entry["prix_m2"] = prix
            entry["annee"] = annee
        else:
            entry["prix_medians"] = a.get("prix_medians", {})
        result.append(entry)
    return {"annee": annee, "données": result}


@app.get("/prix/{num}", tags=["prix"])
@limiter.limit("60/minute")
def get_prix_arrondissement(request: Request, num: int):
    """Prix médians par année pour un arrondissement (série temporelle)."""
    a = get_arr(num)
    return {
        "arrondissement": num,
        "nom": a["nom"],
        "prix_medians": a.get("prix_medians", {}),
        "variation_pct": a.get("variation_pct"),
    }


# ── Timeline ─────────────────────────────────────────────────────────────────

@app.get("/timeline", tags=["timeline"])
@limiter.limit("60/minute")
def get_timeline(request: Request, arr: Optional[str] = Query(None, description="Numéro d'arrondissement (1-20)")):
    """
    Évolution temporelle des prix 2021-2025.
    Sans paramètre → moyenne Paris.
    Avec ?arr=6 → arrondissement spécifique.
    """
    arr = _int(arr)
    data = load_gold()

    if arr:
        a = get_arr(arr)
        pm = a.get("prix_medians", {})
        series = [
            {"annee": int(y), "prix_m2": p, "nb_transactions": a.get("nb_transactions", {}).get(y)}
            for y, p in pm.items()
            if p is not None
        ]
        return {"arrondissement": arr, "nom": a["nom"], "serie": sorted(series, key=lambda x: x["annee"])}

    # Moyenne Paris
    annees = ["2021", "2022", "2023", "2024", "2025"]
    series = []
    for annee in annees:
        prices = [
            a["prix_medians"][annee]
            for a in data["arrondissements"]
            if a.get("prix_medians", {}).get(annee)
        ]
        if prices:
            series.append({
                "annee": int(annee),
                "prix_m2_moyen": round(sum(prices) / len(prices), 0),
                "prix_m2_min": min(prices),
                "prix_m2_max": max(prices),
            })
    return {"scope": "Paris", "serie": series}


# ── Comparaison ───────────────────────────────────────────────────────────────

@app.get("/comparaison", tags=["comparaison"])
@limiter.limit("60/minute")
def comparer(
    request: Request,
    arr1: Optional[str] = Query(None, description="Premier arrondissement (1-20)"),
    arr2: Optional[str] = Query(None, description="Deuxième arrondissement (1-20)"),
):
    """Compare deux arrondissements sur tous les indicateurs."""
    n1 = _int(arr1)
    n2 = _int(arr2)
    if n1 is None or n2 is None:
        raise HTTPException(status_code=400, detail="Les paramètres arr1 et arr2 (entiers 1-20) sont requis. Ex: /comparaison?arr1=6&arr2=16")
    a1 = get_arr(n1)
    a2 = get_arr(n2)

    indicateurs = [
        "prix_medians", "logements_sociaux_pct", "revenu_median_uc",
        "population", "densite_hab_km2", "crimes_pour_mille",
        "nb_transactions", "repartition_pieces",
    ]

    return {
        "arrondissement_1": {
            "num": a1["num"],
            "nom": a1["nom"],
            **{k: a1.get(k) for k in indicateurs},
        },
        "arrondissement_2": {
            "num": a2["num"],
            "nom": a2["nom"],
            **{k: a2.get(k) for k in indicateurs},
        },
    }


# ── Logements sociaux ─────────────────────────────────────────────────────────

@app.get("/logements-sociaux", tags=["logements sociaux"])
@limiter.limit("60/minute")
def get_logements_sociaux(request: Request):
    """Part de logements sociaux (%) par arrondissement, triée par taux décroissant."""
    data = load_gold()
    result = sorted(
        [
            {
                "num": a["num"],
                "nom": a["nom"],
                "logements_sociaux_pct": a.get("logements_sociaux_pct"),
                "nb_logements_sociaux": a.get("nb_logements_sociaux"),
            }
            for a in data["arrondissements"]
        ],
        key=lambda x: x["logements_sociaux_pct"] or 0,
        reverse=True,
    )
    return {"données": result}


# ── Indicateurs socio-économiques ────────────────────────────────────────────

@app.get("/indicateurs", tags=["indicateurs"])
@limiter.limit("60/minute")
def get_indicateurs(request: Request):
    """
    Tableau de bord complet : prix, logements sociaux, revenus,
    criminalité, densité par arrondissement.
    """
    data = load_gold()
    result = []
    for a in data["arrondissements"]:
        result.append({
            "num": a["num"],
            "nom": a["nom"],
            "prix_m2_2023": a.get("prix_medians", {}).get("2023"),
            "variation_pct": a.get("variation_pct"),
            "logements_sociaux_pct": a.get("logements_sociaux_pct"),
            "revenu_median_uc": a.get("revenu_median_uc"),
            "population": a.get("population"),
            "densite_hab_km2": a.get("densite_hab_km2"),
            "crimes_pour_mille": a.get("crimes_pour_mille"),
        })
    return {"données": result}


# ── GeoJSON ───────────────────────────────────────────────────────────────────

@app.get("/geojson", tags=["géographie"])
@limiter.limit("60/minute")
def get_geojson(request: Request, indicateur: str = Query("prix_m2_2023", description="Indicateur à inclure dans les propriétés")):
    """
    Retourne le GeoJSON des arrondissements enrichi avec les indicateurs Gold.
    Compatible Mapbox / Leaflet / Deck.gl.
    """
    geojson_path = GOLD_DIR / "arrondissements_enrichis.geojson"
    if not geojson_path.exists():
        geojson_path = BRONZE_DIR / "arrondissements.geojson"
    if not geojson_path.exists():
        geojson_path = Path(__file__).parent.parent / "data" / "silver" / "arrondissements_clean.geojson"

    if not geojson_path.exists():
        _url = (
            "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
            "arrondissements/exports/geojson"
        )
        try:
            resp = _requests.get(_url, timeout=15)
            resp.raise_for_status()
            raw = resp.content
            BRONZE_DIR.mkdir(parents=True, exist_ok=True)
            (BRONZE_DIR / "arrondissements.geojson").write_bytes(raw)
            geojson = resp.json()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"GeoJSON indisponible localement et téléchargement OpenData Paris échoué : {exc}",
            )
    else:
        with open(geojson_path, encoding="utf-8") as f:
            geojson = json.load(f)

    data = load_gold()
    gold_by_arr = {a["num"]: a for a in data["arrondissements"]}

    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        arr_num = props.get("arrondissement") or props.get("c_ar")
        if arr_num:
            try:
                arr_num = int(arr_num)
                gold = gold_by_arr.get(arr_num, {})
                props["arrondissement"] = arr_num
                props["nom"] = gold.get("nom", f"{arr_num}ème")
                props["surnom"] = gold.get("surnom", "")
                props["prix_m2_2023"] = gold.get("prix_medians", {}).get("2023")
                props["prix_m2_2022"] = gold.get("prix_medians", {}).get("2022")
                props["logements_sociaux_pct"] = gold.get("logements_sociaux_pct")
                props["revenu_median_uc"] = gold.get("revenu_median_uc")
                props["crimes_pour_mille"] = gold.get("crimes_pour_mille")
                props["population"] = gold.get("population")
                props["variation_pct"] = gold.get("variation_pct")
            except (ValueError, TypeError):
                pass

    return geojson


# ── Serve frontend (production) ──────────────────────────────────────────────

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


# ═══════════════════════════════════════════════════════════════════════════════
# BASE RELATIONNELLE — SQLite / SQLAlchemy  (C1.1)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/db/arrondissements", tags=["SQL — base relationnelle"])
@limiter.limit("60/minute")
def db_list_arrondissements(request: Request, annee: Optional[int] = Query(None, description="Filtrer sur une année (2021-2025)")):
    """
    Retourne les arrondissements depuis la base SQLite.
    Avec ?annee=2023 → ajoute le prix médian pour cette année.
    Démontre une requête JOIN entre tables arrondissements et prix_historiques.
    """
    try:
        from database.sql_db import query_arrondissements
        return {"source": "SQLite/SQLAlchemy", "données": query_arrondissements(annee)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base SQL indisponible : {exc}")


@app.get("/db/prix", tags=["SQL — base relationnelle"])
@limiter.limit("60/minute")
def db_prix(
    request: Request,
    arrondissement: Optional[int] = Query(None, description="Numéro d'arrondissement (1-20)"),
    annee: Optional[int] = Query(None, description="Année (2021-2025)"),
):
    """
    Requête filtrée sur la table prix_historiques (SQLite).
    Démontre les requêtes paramétrées avec clés étrangères.
    """
    try:
        from database.sql_db import query_prix
        return {"source": "SQLite/SQLAlchemy", "données": query_prix(arrondissement, annee)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base SQL indisponible : {exc}")


@app.get("/db/stats", tags=["SQL — base relationnelle"])
@limiter.limit("60/minute")
def db_stats(request: Request):
    """
    Statistiques agrégées calculées directement en SQL (AVG, MIN, MAX, SUM).
    Démontre des requêtes analytiques sur la base relationnelle.
    """
    try:
        from database.sql_db import query_stats_sql
        return {"source": "SQLite/SQLAlchemy", "stats": query_stats_sql()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base SQL indisponible : {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# BASE NON RELATIONNELLE — TinyDB  
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/nosql/profiles", tags=["NoSQL — base documentaire"])
@limiter.limit("60/minute")
def nosql_all_profiles(request: Request):
    """
    Retourne tous les profils arrondissements depuis TinyDB (document store NoSQL).
    Chaque document est un objet JSON semi-structuré avec champs imbriqués
    (prix_medians, repartition_pieces) — format naturellement NoSQL.
    """
    try:
        from database.nosql_db import get_all_profiles
        return {"source": "TinyDB (NoSQL)", "documents": get_all_profiles()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base NoSQL indisponible : {exc}")


@app.get("/nosql/profiles/{num}", tags=["NoSQL — base documentaire"])
@limiter.limit("60/minute")
def nosql_profile(request: Request, num: int):
    """Retourne le document profil complet d'un arrondissement (TinyDB)."""
    try:
        from database.nosql_db import get_profile
        doc = get_profile(num)
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Profil {num} introuvable.")
        return {"source": "TinyDB (NoSQL)", "document": doc}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base NoSQL indisponible : {exc}")


@app.get("/nosql/search", tags=["NoSQL — base documentaire"])
@limiter.limit("60/minute")
def nosql_search(
    request: Request,
    min_prix: Optional[str] = Query(None, description="Prix/m² minimum"),
    max_prix: Optional[str] = Query(None, description="Prix/m² maximum"),
    annee: Optional[str] = Query("2023", description="Année de référence"),
):
    """
    Recherche documentaire NoSQL par plage de prix pour une année donnée.
    Démontre une requête sur champ imbriqué (prix_medians[annee]) — naturelle en NoSQL.
    """
    annee_int = _int(annee, default=2023)
    min_prix_f = _float(min_prix)
    max_prix_f = _float(max_prix)
    try:
        from database.nosql_db import search_profiles
        results = search_profiles(min_prix_f, max_prix_f, annee_int)
        return {"source": "TinyDB (NoSQL)", "annee": annee_int, "résultats": results}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base NoSQL indisponible : {exc}")


@app.get("/nosql/pipeline-logs", tags=["NoSQL — base documentaire"])
@limiter.limit("60/minute")
def nosql_pipeline_logs(request: Request, limit: Optional[str] = Query("10", description="Nombre de logs à retourner")):
    """
    Retourne les derniers logs d'exécution du pipeline (TinyDB).
    Démontre le stockage de documents à schéma variable (logs d'événements).
    """
    limit_int = _int(limit, default=10)
    try:
        from database.nosql_db import get_pipeline_logs
        return {"source": "TinyDB (NoSQL)", "logs": get_pipeline_logs(limit_int)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base NoSQL indisponible : {exc}")
