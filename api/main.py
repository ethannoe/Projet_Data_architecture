"""
Étape 5 : API Backend — Urban Data Explorer
FastAPI — expose les données Gold pour le dashboard frontend
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import requests as _requests
from typing import Optional

app = FastAPI(
    title="Urban Data Explorer API",
    description="API REST pour explorer le marché immobilier parisien arrondissement par arrondissement.",
    version="1.0.0",
    docs_url="/docs",
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
def root():
    return {"status": "ok", "api": "Urban Data Explorer", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health():
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
def list_arrondissements():
    """Retourne la liste complète des arrondissements avec tous les indicateurs."""
    return load_gold()


@app.get("/arrondissements/{num}", tags=["arrondissements"])
def get_arrondissement(num: int):
    """Retourne les données complètes pour un arrondissement donné (1-20)."""
    if not 1 <= num <= 20:
        raise HTTPException(status_code=400, detail="Numéro d'arrondissement invalide (1-20).")
    return get_arr(num)


# ── Prix ─────────────────────────────────────────────────────────────────────

@app.get("/prix", tags=["prix"])
def get_prix(annee: Optional[int] = Query(None, description="Année (2021-2025)")):
    """
    Prix médians par arrondissement.
    Sans paramètre → toutes les années.
    Avec ?annee=2023 → prix 2023 uniquement.
    """
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
def get_prix_arrondissement(num: int):
    """Prix médians par année pour un arrondissement (série temporelle)."""
    a = get_arr(num)
    return {
        "arrondissement": num,
        "nom": a["nom"],
        "prix_medians": a.get("prix_medians", {}),
        "variation_pct_2023": a.get("variation_pct_2023"),
    }


# ── Timeline ─────────────────────────────────────────────────────────────────

@app.get("/timeline", tags=["timeline"])
def get_timeline(arr: Optional[int] = Query(None, description="Numéro d'arrondissement (1-20)")):
    """
    Évolution temporelle des prix 2021-2025.
    Sans paramètre → moyenne Paris.
    Avec ?arr=6 → arrondissement spécifique.
    """
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
def comparer(
    arr1: int = Query(..., description="Premier arrondissement"),
    arr2: int = Query(..., description="Deuxième arrondissement"),
):
    """Compare deux arrondissements sur tous les indicateurs."""
    a1 = get_arr(arr1)
    a2 = get_arr(arr2)

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
def get_logements_sociaux():
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
def get_indicateurs():
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
            "variation_pct": a.get("variation_pct_2023"),
            "logements_sociaux_pct": a.get("logements_sociaux_pct"),
            "revenu_median_uc": a.get("revenu_median_uc"),
            "population": a.get("population"),
            "densite_hab_km2": a.get("densite_hab_km2"),
            "crimes_pour_mille": a.get("crimes_pour_mille"),
        })
    return {"données": result}


# ── GeoJSON ───────────────────────────────────────────────────────────────────

@app.get("/geojson", tags=["géographie"])
def get_geojson(indicateur: str = Query("prix_m2_2023", description="Indicateur à inclure dans les propriétés")):
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
                props["variation_pct_2023"] = gold.get("variation_pct_2023")
            except (ValueError, TypeError):
                pass

    return geojson


# ── Serve frontend (production) ──────────────────────────────────────────────

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
