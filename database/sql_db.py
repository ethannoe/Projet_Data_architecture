"""
Base relationnelle SQLite — Urban Data Explorer (C1.1)
Schéma : arrondissements, prix_historiques, repartitions_pieces
"""
from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    ForeignKey, UniqueConstraint, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "urban_data.db"
ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=False)


class Base(DeclarativeBase):
    pass


class Arrondissement(Base):
    __tablename__ = "arrondissements"

    num                  = Column(Integer, primary_key=True)
    nom                  = Column(String,  nullable=False)
    surnom               = Column(String)
    code_insee           = Column(String,  unique=True)
    superficie_km2       = Column(Float)
    population           = Column(Integer)
    densite_hab_km2      = Column(Float)
    logements_sociaux_pct = Column(Float)
    nb_logements_sociaux  = Column(Integer)
    revenu_median_uc     = Column(Float)
    crimes_pour_mille    = Column(Float)

    prix   = relationship("PrixHistorique",  back_populates="arrondissement", cascade="all, delete-orphan")
    pieces = relationship("RepartitionPieces", back_populates="arrondissement", cascade="all, delete-orphan")


class PrixHistorique(Base):
    __tablename__ = "prix_historiques"
    __table_args__ = (UniqueConstraint("arrondissement_num", "annee"),)

    id                = Column(Integer, primary_key=True, autoincrement=True)
    arrondissement_num = Column(Integer, ForeignKey("arrondissements.num"), nullable=False)
    annee             = Column(Integer, nullable=False)
    prix_median       = Column(Float)
    nb_transactions   = Column(Integer)

    arrondissement = relationship("Arrondissement", back_populates="prix")


class RepartitionPieces(Base):
    __tablename__ = "repartitions_pieces"
    __table_args__ = (UniqueConstraint("arrondissement_num", "typo"),)

    id                = Column(Integer, primary_key=True, autoincrement=True)
    arrondissement_num = Column(Integer, ForeignKey("arrondissements.num"), nullable=False)
    typo              = Column(String,  nullable=False)
    pct               = Column(Float)

    arrondissement = relationship("Arrondissement", back_populates="pieces")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(ENGINE)
    logger.info(f"SQLite initialisé : {DB_PATH}")


def write_gold_to_sql(arrondissements: list) -> None:
    """Écrit (upsert) tous les arrondissements Gold dans la base relationnelle."""
    init_db()
    with Session(ENGINE) as session:
        for a in arrondissements:
            arr = session.get(Arrondissement, a["num"])
            if arr is None:
                arr = Arrondissement(num=a["num"])
                session.add(arr)

            arr.nom                   = a.get("nom", "")
            arr.surnom                = a.get("surnom", "")
            arr.code_insee            = a.get("code_insee", f"751{str(a['num']).zfill(2)}")
            arr.superficie_km2        = a.get("superficie_km2")
            arr.population            = a.get("population")
            arr.densite_hab_km2       = a.get("densite_hab_km2")
            arr.logements_sociaux_pct = a.get("logements_sociaux_pct")
            arr.nb_logements_sociaux  = a.get("nb_logements_sociaux")
            arr.revenu_median_uc      = a.get("revenu_median_uc")
            arr.crimes_pour_mille     = a.get("crimes_pour_mille")

            prix_data = a.get("prix_medians", {})
            nb_tx     = a.get("nb_transactions", {})
            for annee_str, prix_val in prix_data.items():
                annee_int = int(annee_str)
                ph = session.query(PrixHistorique).filter_by(
                    arrondissement_num=a["num"], annee=annee_int
                ).first()
                if ph is None:
                    ph = PrixHistorique(arrondissement_num=a["num"], annee=annee_int)
                    session.add(ph)
                ph.prix_median     = prix_val
                ph.nb_transactions = nb_tx.get(annee_str) or nb_tx.get(annee_int)

            for typo, pct in a.get("repartition_pieces", {}).items():
                rp = session.query(RepartitionPieces).filter_by(
                    arrondissement_num=a["num"], typo=typo
                ).first()
                if rp is None:
                    rp = RepartitionPieces(arrondissement_num=a["num"], typo=typo)
                    session.add(rp)
                rp.pct = pct

        session.commit()
    logger.info(f"SQL → {len(arrondissements)} arrondissements écrits dans {DB_PATH}")


def query_arrondissements(annee: int = None) -> list[dict]:
    """Retourne tous les arrondissements avec le prix médian pour une année donnée."""
    with Session(ENGINE) as session:
        arrs = session.query(Arrondissement).order_by(Arrondissement.num).all()
        result = []
        for a in arrs:
            row = {
                "num":                   a.num,
                "nom":                   a.nom,
                "surnom":                a.surnom,
                "code_insee":            a.code_insee,
                "superficie_km2":        a.superficie_km2,
                "population":            a.population,
                "densite_hab_km2":       a.densite_hab_km2,
                "logements_sociaux_pct": a.logements_sociaux_pct,
                "revenu_median_uc":      a.revenu_median_uc,
                "crimes_pour_mille":     a.crimes_pour_mille,
            }
            if annee:
                ph = next((p for p in a.prix if p.annee == annee), None)
                row["prix_m2"] = ph.prix_median if ph else None
                row["nb_transactions"] = ph.nb_transactions if ph else None
            else:
                row["prix_medians"] = {
                    str(p.annee): p.prix_median for p in sorted(a.prix, key=lambda x: x.annee)
                }
            result.append(row)
    return result


def query_prix(arrondissement: int = None, annee: int = None) -> list[dict]:
    """Requête filtrée sur les prix historiques."""
    with Session(ENGINE) as session:
        q = session.query(PrixHistorique)
        if arrondissement:
            q = q.filter(PrixHistorique.arrondissement_num == arrondissement)
        if annee:
            q = q.filter(PrixHistorique.annee == annee)
        rows = q.order_by(PrixHistorique.arrondissement_num, PrixHistorique.annee).all()
        return [
            {
                "arrondissement": r.arrondissement_num,
                "annee":          r.annee,
                "prix_median":    r.prix_median,
                "nb_transactions": r.nb_transactions,
            }
            for r in rows
        ]


def query_stats_sql() -> dict:
    """Statistiques agrégées calculées en SQL (démonstration requêtes relationnelles)."""
    with Session(ENGINE) as session:
        total_arr = session.query(Arrondissement).count()
        total_prix = session.query(PrixHistorique).count()

        # Prix médian Paris par année (AVG des médianes arrondissements)
        prix_par_annee = session.execute(text(
            "SELECT annee, ROUND(AVG(prix_median), 0) as prix_moyen, "
            "MIN(prix_median) as prix_min, MAX(prix_median) as prix_max, "
            "SUM(nb_transactions) as total_transactions "
            "FROM prix_historiques WHERE prix_median IS NOT NULL "
            "GROUP BY annee ORDER BY annee"
        )).fetchall()

        # Arrondissement le plus et le moins cher en 2023
        extremes = session.execute(text(
            "SELECT a.num, a.nom, ph.prix_median "
            "FROM arrondissements a JOIN prix_historiques ph ON a.num = ph.arrondissement_num "
            "WHERE ph.annee = 2023 AND ph.prix_median IS NOT NULL "
            "ORDER BY ph.prix_median DESC"
        )).fetchall()

    return {
        "tables": {
            "arrondissements": total_arr,
            "prix_historiques": total_prix,
        },
        "prix_par_annee": [
            {"annee": r[0], "prix_moyen": r[1], "prix_min": r[2], "prix_max": r[3], "transactions": r[4]}
            for r in prix_par_annee
        ],
        "plus_cher_2023":  {"num": extremes[0][0],  "nom": extremes[0][1],  "prix_m2": extremes[0][2]}  if extremes else None,
        "moins_cher_2023": {"num": extremes[-1][0], "nom": extremes[-1][1], "prix_m2": extremes[-1][2]} if extremes else None,
    }
