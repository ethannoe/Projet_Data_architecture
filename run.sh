#!/usr/bin/env bash
# Urban Data Explorer — Orchestrateur principal
# Usage : ./run.sh [pipeline|api|all|reset]
set -euo pipefail

# ── Couleurs ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ── Chemins ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
PYTHON="$VENV/bin/python3"
PIP="$VENV/bin/pip"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*" | tee -a "$LOG_FILE"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"; }
err()  { echo -e "${RED}[ERR]${NC} $*" | tee -a "$LOG_FILE"; }

header() {
    echo -e "\n${BOLD}${BLUE}══════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $*${NC}"
    echo -e "${BOLD}${BLUE}══════════════════════════════════════════════════${NC}\n"
}

# ── Environnement virtuel ─────────────────────────────────────────────────────
setup_env() {
    header "ENVIRONNEMENT"

    if [ ! -d "$VENV" ]; then
        log "Création de l'environnement virtuel..."
        python3 -m venv "$VENV"
        ok "Environnement créé : $VENV"
    else
        ok "Environnement virtuel trouvé : $VENV"
    fi

    log "Installation des dépendances..."
    "$PIP" install -r "$SCRIPT_DIR/requirements.txt" -q
    ok "Dépendances installées."
}

# ── Pipeline de données ───────────────────────────────────────────────────────
run_pipeline() {
    header "PIPELINE Bronze → Silver → Gold → SQL/NoSQL"

    mkdir -p "$LOG_DIR"
    log "Lancement du pipeline complet..."
    log "Logs détaillés : $LOG_FILE"

    cd "$SCRIPT_DIR"
    "$PYTHON" run_pipeline.py 2>&1 | tee -a "$LOG_FILE"

    # Vérification des sorties
    GOLD="$SCRIPT_DIR/data/gold/arrondissements_enrichis.json"
    NOSQL="$SCRIPT_DIR/data/nosql/arrondissement_profiles.json"

    if [ -f "$GOLD" ]; then
        NB=$(python3 -c "import json; d=json.load(open('$GOLD')); print(len(d['arrondissements']))" 2>/dev/null || echo "?")
        ok "Gold JSON : $NB arrondissements → $GOLD"
    else
        err "Gold JSON manquant : $GOLD"
        exit 1
    fi

    if [ -f "$NOSQL" ]; then
        ok "NoSQL TinyDB : $NOSQL"
    else
        warn "Profils NoSQL non générés."
    fi

    DB="$SCRIPT_DIR/data/urban_data.db"
    if [ -f "$DB" ]; then
        SIZE=$(du -sh "$DB" | cut -f1)
        ok "SQLite : $DB ($SIZE)"
    else
        warn "Base SQLite non générée."
    fi
}

# ── API FastAPI ───────────────────────────────────────────────────────────────
run_api() {
    header "API FASTAPI"

    PORT="${PORT:-8000}"

    # Tuer un éventuel processus sur ce port
    if lsof -ti tcp:"$PORT" &>/dev/null; then
        warn "Port $PORT déjà utilisé — arrêt du processus existant..."
        lsof -ti tcp:"$PORT" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi

    log "Démarrage de l'API sur http://localhost:$PORT"
    log "Documentation Swagger : http://localhost:$PORT/docs"
    log "Arrêt : Ctrl+C"

    cd "$SCRIPT_DIR"
    "$VENV/bin/uvicorn" api.main:app --host 0.0.0.0 --port "$PORT" --reload
}

# ── Reset ─────────────────────────────────────────────────────────────────────
reset_data() {
    header "RESET DONNÉES GÉNÉRÉES"

    warn "Suppression des données régénérables (Bronze, Silver, SQLite)..."
    rm -rf "$SCRIPT_DIR/data/bronze/"
    rm -rf "$SCRIPT_DIR/data/silver/"
    rm -f  "$SCRIPT_DIR/data/urban_data.db"
    rm -f  "$SCRIPT_DIR"/*.log

    ok "Reset terminé. Les données Gold et NoSQL sont conservées."
    log "Relancer ./run.sh pipeline pour reconstruire depuis les sources."
}

# ── Usage ─────────────────────────────────────────────────────────────────────
usage() {
    echo -e "\n${BOLD}Urban Data Explorer — Orchestrateur${NC}"
    echo ""
    echo "  Usage : ./run.sh [commande]"
    echo ""
    echo "  Commandes :"
    echo -e "    ${GREEN}pipeline${NC}   Exécute Bronze → Silver → Gold → SQL/NoSQL"
    echo -e "    ${GREEN}api${NC}        Démarre l'API FastAPI (port 8000)"
    echo -e "    ${GREEN}all${NC}        Pipeline + API (enchainés)"
    echo -e "    ${GREEN}reset${NC}      Supprime les données régénérables"
    echo ""
    echo "  Exemple :"
    echo "    ./run.sh all          # pipeline complet puis API"
    echo "    PORT=8001 ./run.sh api  # API sur port custom"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

CMD="${1:-all}"

echo -e "\n${BOLD}Urban Data Explorer${NC} — $(date '+%d/%m/%Y %H:%M:%S')\n"

case "$CMD" in
    pipeline)
        setup_env
        run_pipeline
        ;;
    api)
        setup_env
        run_api
        ;;
    all)
        setup_env
        run_pipeline
        run_api
        ;;
    reset)
        reset_data
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        err "Commande inconnue : $CMD"
        usage
        exit 1
        ;;
esac
