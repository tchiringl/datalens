#!/usr/bin/env bash
# DataHub POC — one-shot setup script
# Usage: bash scripts/setup.sh

set -euo pipefail
CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'

info()  { echo -e "${CYAN}[setup]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}    $*"; }
fail()  { echo -e "${RED}[fail]${NC}  $*"; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1. Copy .env if missing
if [[ ! -f .env ]]; then
  cp .env.example .env
  info "Copied .env.example → .env  (edit secrets before re-running)"
else
  ok ".env already exists"
fi

# 2. Check Docker is running
docker info &>/dev/null || fail "Docker is not running. Start Docker Desktop first."
ok "Docker is running"

# 3. Check available memory (warn if < 12 GB)
DOCKER_MEM=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)
DOCKER_MEM_GB=$(( DOCKER_MEM / 1024 / 1024 / 1024 ))
if [[ "$DOCKER_MEM_GB" -lt 12 ]]; then
  echo -e "${RED}[warn]${NC}  Docker has ${DOCKER_MEM_GB} GB RAM — recommend ≥12 GB. Adjust in Docker Desktop → Settings → Resources."
else
  ok "Docker memory: ${DOCKER_MEM_GB} GB"
fi

# 4. Build images
info "Building Docker images (this may take a few minutes on first run)..."
docker compose build --parallel
ok "Images built"

# 5. Start services
info "Starting all services..."
docker compose up -d
ok "Services started"

# 6. Wait for PostgreSQL
info "Waiting for PostgreSQL to be healthy..."
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U datahub &>/dev/null; then
    ok "PostgreSQL is ready"; break
  fi
  [[ $i -eq 30 ]] && fail "PostgreSQL did not become ready in 60s"
  sleep 2
done

# 7. Wait for Trino
info "Waiting for Trino to be healthy..."
for i in $(seq 1 40); do
  if curl -sf http://localhost:8080/v1/info &>/dev/null; then
    ok "Trino is ready"; break
  fi
  [[ $i -eq 40 ]] && fail "Trino did not become ready in 80s"
  sleep 2
done

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   DataHub POC is running!                        ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Frontend      →  http://localhost:3000          ║${NC}"
echo -e "${GREEN}║  API docs      →  http://localhost:8000/docs     ║${NC}"
echo -e "${GREEN}║  Airflow       →  http://localhost:8082          ║${NC}"
echo -e "${GREEN}║  OpenMetadata  →  http://localhost:8585          ║${NC}"
echo -e "${GREEN}║  MinIO console →  http://localhost:9001          ║${NC}"
echo -e "${GREEN}║  Trino UI      →  http://localhost:8080          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
info "Run 'bash scripts/validate.sh' to verify the full stack."
