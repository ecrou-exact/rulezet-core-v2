#!/bin/bash
# =============================================================================
#  launch.sh — P'tit Crolle management script
# =============================================================================

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m';  GREEN='\033[0;32m';  YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m';   BOLD='\033[1m'; NC='\033[0m'

# ── Config ────────────────────────────────────────────────────────────────────
VENV_DIR="venv"
BACKUP_DIR="backups"
DB_NAME_DEV="ptitcrolle.sqlite"

# ── Logging helpers ───────────────────────────────────────────────────────────
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()     { echo -e "${RED}[ERR ]${NC}  $*"; }
title()   { echo -e "\n${BOLD}${BLUE}══════  $*  ══════${NC}\n"; }

# ── Find the SQLite file (Flask puts it in instance/ by default) ──────────────
find_db() {
    local name="${1:-$DB_NAME_DEV}"
    for candidate in "instance/$name" "$name" "app/$name"; do
        [ -f "$candidate" ] && { echo "$candidate"; return; }
    done
    echo ""
}

# ── Virtual environment ───────────────────────────────────────────────────────
setup_venv() {
    if [ -n "$VIRTUAL_ENV" ]; then
        ok "Already in virtual environment: $VIRTUAL_ENV"; return 0
    fi
    if [ -d "$VENV_DIR" ]; then
        info "Activating existing virtual environment..."
    else
        info "Creating virtual environment in ./$VENV_DIR ..."
        python3 -m venv "$VENV_DIR"
        ok "Virtual environment created."
    fi
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    ok "Virtual environment activated."
}

require_venv() {
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -d "$VENV_DIR" ]; then
            # shellcheck disable=SC1091
            source "$VENV_DIR/bin/activate"
        else
            err "No virtual environment found. Run './launch.sh --setup' first."
            exit 1
        fi
    fi
}

# =============================================================================
#  Commands
# =============================================================================

# ── Setup (first run) ─────────────────────────────────────────────────────────
cmd_setup() {
    title "First Setup"

    # 1. Venv
    setup_venv

    # 2. Dependencies
    info "Installing dependencies from requirements.txt ..."
    pip install -r requirements.txt
    ok "Dependencies installed."

    # 3. Config
    if [ ! -f "config.py" ]; then
        cp config.py.default config.py
        ok "config.py created from config.py.default."
        warn "Review config.py before going to production (SECRET_KEY, etc.)."
    else
        info "config.py already exists — skipping."
    fi

    # 4. Backup folder
    mkdir -p "$BACKUP_DIR"

    # 5. Init DB
    info "Initialising database ..."
    export FLASKENV="development"
    python3 app.py --init_db
    ok "Database initialised with default roles and admin user."

    echo ""
    ok "All done! Run './launch.sh --start' to start the app."
    info "Default admin credentials: admin@admin.admin / admin"
}

# ── Start ─────────────────────────────────────────────────────────────────────
cmd_start() {
    require_venv
    info "Starting Flask development server ..."
    export FLASKENV="development"
    python3 app.py
}

# ── Tests ─────────────────────────────────────────────────────────────────────
cmd_test() {
    require_venv
    title "Test Suite"
    export FLASKENV="testing"
    pytest "$@"
}

# ── Backup DB ─────────────────────────────────────────────────────────────────
cmd_backup_db() {
    require_venv
    mkdir -p "$BACKUP_DIR"

    local db_path
    db_path=$(find_db "$DB_NAME_DEV")
    if [ -z "$db_path" ]; then
        warn "No development database found ($DB_NAME_DEV). Nothing to back up."
        return 1
    fi

    local timestamp; timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="${BACKUP_DIR}/${DB_NAME_DEV%.sqlite}_${timestamp}.sqlite"
    cp "$db_path" "$backup_file"
    ok "Backup saved → $backup_file"
}

# ── List backups ──────────────────────────────────────────────────────────────
cmd_list_backups() {
    title "Available Backups"
    if [ ! -d "$BACKUP_DIR" ]; then
        info "Backup directory does not exist yet ($BACKUP_DIR/)."; return
    fi
    local files=("$BACKUP_DIR"/*.sqlite)
    if [ ! -f "${files[0]}" ]; then
        info "No backups found in $BACKUP_DIR/."; return
    fi
    ls -lh "$BACKUP_DIR"/*.sqlite
}

# ── Reload DB ─────────────────────────────────────────────────────────────────
cmd_reload_db() {
    require_venv
    title "Reload Database"
    warn "This will DROP all tables and recreate the database from scratch."
    echo ""

    # Offer to back up first
    read -rp "$(echo -e "${YELLOW}Back up current database before reloading? [Y/n]: ${NC}")" bk
    bk="${bk:-Y}"
    if [[ "$bk" =~ ^[Yy]$ ]]; then
        cmd_backup_db || true   # non-fatal if no db yet
    fi

    # Offer to restore from an existing backup instead of fresh reload
    local files=("$BACKUP_DIR"/*.sqlite)
    if [ -d "$BACKUP_DIR" ] && [ -f "${files[0]}" ]; then
        echo ""
        read -rp "$(echo -e "${YELLOW}Restore from an existing backup instead of a fresh reload? [y/N]: ${NC}")" restore
        restore="${restore:-N}"
        if [[ "$restore" =~ ^[Yy]$ ]]; then
            echo ""
            info "Available backups:"
            local i=0
            for f in "$BACKUP_DIR"/*.sqlite; do
                echo -e "  ${BOLD}[$i]${NC}  $f  ($(ls -lh "$f" | awk '{print $5}'))"
                ((i++))
            done
            echo ""
            read -rp "Enter backup number to restore: " num
            local idx=0; local chosen=""
            for f in "$BACKUP_DIR"/*.sqlite; do
                if [ "$idx" -eq "$num" ]; then chosen="$f"; break; fi
                ((idx++))
            done
            if [ -z "$chosen" ]; then
                err "Invalid number."; return 1
            fi
            local db_path; db_path=$(find_db "$DB_NAME_DEV")
            [ -z "$db_path" ] && { mkdir -p instance; db_path="instance/$DB_NAME_DEV"; }
            cp "$chosen" "$db_path"
            ok "Database restored from: $chosen"
            return 0
        fi
    fi

    # Confirm fresh reload
    echo ""
    read -rp "$(echo -e "${RED}Type 'yes' to confirm DROP + recreate: ${NC}")" confirm
    if [ "$confirm" != "yes" ]; then
        info "Aborted."; return 0
    fi

    export FLASKENV="development"
    python3 app.py --recreate_db
    ok "Database reloaded."
}

# ── Migrations ────────────────────────────────────────────────────────────────
cmd_migrate() {
    require_venv
    export FLASKENV="development"
    local msg="${1:-}"
    if [ -n "$msg" ]; then
        info "Creating migration: \"$msg\" ..."
        flask db migrate -m "$msg"
    else
        info "Creating migration (no message) ..."
        flask db migrate
    fi
    ok "Migration file created in migrations/versions/."
    info "Review it, then run './launch.sh --upgrade' to apply."
}

cmd_upgrade() {
    require_venv
    export FLASKENV="development"
    info "Applying pending migrations (upgrade) ..."
    flask db upgrade
    ok "Database upgraded."
}

cmd_downgrade() {
    require_venv
    export FLASKENV="development"
    warn "This will roll back the last migration."
    read -rp "$(echo -e "${YELLOW}Are you sure? [y/N]: ${NC}")" confirm
    confirm="${confirm:-N}"
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        flask db downgrade
        ok "Database downgraded one step."
    else
        info "Aborted."
    fi
}

cmd_migration_info() {
    require_venv
    export FLASKENV="development"
    title "Migration Status"
    info "Current revision:"
    flask db current
    echo ""
    info "Full history:"
    flask db history --verbose
}

# ── Deploy ────────────────────────────────────────────────────────────────────
cmd_deploy() {
    require_venv
    title "Deploy"

    # 1. Backup DB
    info "[1/4] Backing up database ..."
    cmd_backup_db || warn "No database to back up — continuing."

    # 2. Git pull
    echo ""
    info "[2/4] Pulling latest changes ..."
    git pull
    ok "Git pull done."

    # 3. Update dependencies
    echo ""
    info "[3/4] Updating dependencies ..."
    pip install -r requirements.txt
    ok "Dependencies up to date."

    # 4. Check for pending migrations
    echo ""
    info "[4/4] Checking for pending migrations ..."
    export FLASKENV="development"
    local current; current=$(flask db current 2>/dev/null || echo "unknown")
    local head;    head=$(flask db heads  2>/dev/null || echo "unknown")

    if [ "$current" = "$head" ] || [ -z "$head" ]; then
        ok "Database is up to date (revision: $current)."
    else
        warn "Pending migrations detected!"
        info "Current : $current"
        info "Head    : $head"
        read -rp "$(echo -e "${YELLOW}Apply migrations now? [Y/n]: ${NC}")" apply
        apply="${apply:-Y}"
        if [[ "$apply" =~ ^[Yy]$ ]]; then
            flask db upgrade
            ok "Migrations applied."
        else
            warn "Migrations NOT applied — run './launch.sh --upgrade' manually."
        fi
    fi

    echo ""
    ok "Deploy complete. Run './launch.sh --start' to restart the app."
}

# ── Help ──────────────────────────────────────────────────────────────────────
cmd_help() {
    echo -e ""
    echo -e "${BOLD}${BLUE}P'tit Crolle — launch.sh${NC}"
    echo -e "${CYAN}Usage: ./launch.sh [command] [options]${NC}"
    echo -e ""
    echo -e "${BOLD}Setup${NC}"
    echo -e "  ${GREEN}--setup${NC}                        Create venv, install deps, copy config, init DB"
    echo -e ""
    echo -e "${BOLD}App${NC}"
    echo -e "  ${GREEN}--start${NC}                        Start the Flask development server"
    echo -e "  ${GREEN}--test [pytest args]${NC}           Run the test suite (extra args forwarded to pytest)"
    echo -e "  ${GREEN}(no argument)${NC}                  Same as --start"
    echo -e ""
    echo -e "${BOLD}Database${NC}"
    echo -e "  ${GREEN}--backup-db${NC}                    Back up the database to backups/"
    echo -e "  ${GREEN}--list-backups${NC}                 List all saved backups"
    echo -e "  ${GREEN}--reload-db${NC}                    Drop + recreate DB (prompts for backup/restore)"
    echo -e ""
    echo -e "${BOLD}Migrations${NC}"
    echo -e "  ${GREEN}--migrate [\"message\"]${NC}          Auto-detect changes and create a migration file"
    echo -e "  ${GREEN}--upgrade${NC}                      Apply all pending migrations"
    echo -e "  ${GREEN}--downgrade${NC}                    Roll back the last migration"
    echo -e "  ${GREEN}--migration-info${NC}               Show current revision and full history"
    echo -e ""
    echo -e "${BOLD}Deploy${NC}"
    echo -e "  ${GREEN}--deploy${NC}                       Backup → git pull → pip install → check migrations"
    echo -e ""
    echo -e "${BOLD}Help${NC}"
    echo -e "  ${GREEN}--help${NC}                         Show this help"
    echo -e ""
    echo -e "${BOLD}Examples${NC}"
    echo -e "  ${CYAN}./launch.sh --setup${NC}                      # new machine setup"
    echo -e "  ${CYAN}./launch.sh --start${NC}                      # start the app"
    echo -e "  ${CYAN}./launch.sh --migrate \"add posts table\"${NC}   # create a migration"
    echo -e "  ${CYAN}./launch.sh --upgrade${NC}                    # apply migrations"
    echo -e "  ${CYAN}./launch.sh --test -v tests/account/${NC}      # run specific tests"
    echo -e ""
}

# =============================================================================
#  Entry point
# =============================================================================

if [ -z "$1" ]; then
    cmd_start; exit 0
fi

case "$1" in
    --setup)            cmd_setup ;;
    --start)            cmd_start ;;
    --test)             shift; cmd_test "$@" ;;
    --backup-db)        cmd_backup_db ;;
    --list-backups)     cmd_list_backups ;;
    --reload-db)        cmd_reload_db ;;
    --migrate)          shift; cmd_migrate "$1" ;;
    --upgrade)          cmd_upgrade ;;
    --downgrade)        cmd_downgrade ;;
    --migration-info)   cmd_migration_info ;;
    --deploy)           cmd_deploy ;;
    --help)             cmd_help ;;
    *)
        err "Unknown command: $1"
        echo ""
        cmd_help
        exit 1
        ;;
esac
