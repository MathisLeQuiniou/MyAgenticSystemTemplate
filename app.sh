#!/usr/bin/env bash
# One-command launcher.

#   ./app.sh           start everything: MCP tool servers + API + frontend (Ctrl+C stops all)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
NGINX_PORT="${NGINX_PORT:-80}"
export ROOT API_HOST API_PORT NGINX_PORT
export PYTHONUNBUFFERED=1
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
info()      { echo -e "${GREEN}[app]${NC} $*"; }
warning()   { echo -e "${YELLOW}[app]${NC} $*"; }
error()     { echo -e "${RED}[app]${NC} $*"; }
fail()      { error "$*" && exit 1; }

wait_for_port() {
  local host="$1" port="$2" name="$3" i=0
  while ! python -c "import socket,sys; s=socket.socket(); s.settimeout(0.5); sys.exit(s.connect_ex(('$host', $port)))" 2>/dev/null; do
    i=$((i + 1))
    [ "$i" -gt 40 ] && { info "$name not reachable on $host:$port, continuing anyway"; return 0; }
    sleep 1
  done
}

wait_for_file() {
  local timeout="${3:-10}"
  local i=0

  while [ ! -f "$1" ]; do
    i=$((i + 1))

    if [ "$i" -ge $((timeout * 10)) ]; then
      fail "$2 did not become ready within ${timeout} seconds."
    fi

    sleep 0.1
  done
}

require_setup() {
  # check main modules are installed
  command -v python \
    || fail "python not found (install Python >= 3.10)"
  command -v npm \
    || fail "npm not found (install Node.js >= 20.19)"
  command -v nginx \
    || fail "nginx not found (install nginx >= 1.21.0)"

  # check weither dependancies are installed or not
  python -m pip check \
    || fail "Backend dependencies are missing or incompatible. You must do the backend setup first."
  [ -d frontend/node_modules ] || fail "Frontend dependancies missing. You must do the frontend setup first."

  # check that DB exists and is updated
  cd backend/db/
  [ -f alembic.ini ] \
    || fail "alembic.ini not found."
  alembic current \
    || fail "Database is missing or unreachable."
  if ! alembic check ; then
    fail "Database is not up to date. Run: alembic upgrade head"
  fi
  cd ../../
}

# Cleanup: kill processes on exit
PIDS=()
cleanup() {
  echo ""
  info "shutting down.."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  info "done."
}
trap cleanup EXIT INT TERM

LOGS_DIR="$ROOT/tmp/logs"
mkdir -p "$LOGS_DIR"

cmd_start() {
  info "checking setup.."
  require_setup
  info "checking setup complete."
  
  info "starting mcp servers.."
  python -m backend.tool_servers \
    &> "$LOGS_DIR/mcp_servers.log" &
  PIDS+=($!)
  # Wait until the MCP supervisor reports that all servers are ready.
  wait_for_file "$ROOT/tmp/mcp_servers.ready" "MCP servers" 10
  info "logs available at $LOGS_DIR/mcp_servers.log"
  info "starting mcp servers complete"


  info "starting backend api.."
  python -m uvicorn backend.api.main:app \
    --host "$API_HOST" \
    --port "$API_PORT" \
    &> "$LOGS_DIR/backend.log" &
  PIDS+=($!)
  wait_for_port "$API_HOST" "$API_PORT" "API"
  info "logs available at $LOGS_DIR/backend.log"
  info "starting backend api complete."


  info "starting nginx server.."
  # create nginx.conf from nginx.conf.template
  envsubst '${ROOT} ${API_HOST} ${API_PORT} ${NGINX_PORT}' \
    < "$ROOT/nginx/nginx.conf.template" \
    > "$ROOT/nginx/nginx.conf"

  # Validate generated configuration
  nginx -t -c "$ROOT/nginx/nginx.conf" \
    || fail "Generated nginx configuration is invalid."

  # start the server
  nginx -c "$ROOT/nginx/nginx.conf" -g "daemon off;" &>"$LOGS_DIR/nginx.log" &
  PIDS+=($!)
  info "logs available at $LOGS_DIR/nginx.log (see also access.log & error.log)"
  info "starting nginx server complete."
  echo ""
  info "✓ Frontend  http://$API_HOST:$NGINX_PORT/"
  info "✓ API       http://$API_HOST:$API_PORT/docs"
  echo ""
  info "  Ctrl+C to stop everything."
  wait
}

cmd_start
