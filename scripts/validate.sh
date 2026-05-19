#!/usr/bin/env bash
# DataHub POC — end-to-end validation script
# Usage: bash scripts/validate.sh

set -uo pipefail
PASS=0; FAIL=0
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

pass() { echo -e "  ${GREEN}[PASS]${NC} $*"; (( PASS++ )); }
fail() { echo -e "  ${RED}[FAIL]${NC} $*"; (( FAIL++ )); }
head() { echo -e "\n${YELLOW}── $* ──${NC}"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ── Infrastructure ──────────────────────────────────────────────────────────
head "Infrastructure"
docker compose ps --format "{{.Name}} {{.Status}}" | while read name status; do
  if echo "$status" | grep -qiE "Up|healthy|running"; then
    pass "$name is up"
  else
    fail "$name — status: $status"
  fi
done

# ── Trino ────────────────────────────────────────────────────────────────────
head "Trino"
if curl -sf http://localhost:8080/v1/info | grep -q '"starting":false'; then
  pass "Trino coordinator ready"
else
  fail "Trino not ready"
fi

TRINO_QUERY_RESULT=$(docker compose exec -T trino trino \
  --execute "SELECT COUNT(*) FROM postgres.public.customers" \
  --output-format TSV 2>/dev/null | tail -1)
if [[ "$TRINO_QUERY_RESULT" =~ ^[0-9]+$ ]] && [[ "$TRINO_QUERY_RESULT" -gt 0 ]]; then
  pass "Trino postgres catalog: queried customers (${TRINO_QUERY_RESULT} rows)"
else
  fail "Trino postgres catalog query failed"
fi

# ── PostgreSQL seed data ─────────────────────────────────────────────────────
head "PostgreSQL Seed Data"
for table in customers orders order_items products stores; do
  COUNT=$(docker compose exec -T postgres psql -U datahub -d retail -t \
    -c "SELECT COUNT(*) FROM $table" 2>/dev/null | tr -d ' ')
  if [[ "$COUNT" =~ ^[0-9]+$ ]] && [[ "$COUNT" -gt 0 ]]; then
    pass "Table '$table': ${COUNT} rows"
  else
    fail "Table '$table': empty or not found"
  fi
done

# DQ issues
NULL_EMAIL=$(docker compose exec -T postgres psql -U datahub -d retail -t \
  -c "SELECT COUNT(*) FROM customers WHERE email IS NULL" 2>/dev/null | tr -d ' ')
[[ "$NULL_EMAIL" -ge 50 ]] && pass "DQ issue: ${NULL_EMAIL} customers with NULL email" \
  || fail "DQ issue: expected ≥50 NULL emails, got ${NULL_EMAIL}"

DUP_CODES=$(docker compose exec -T postgres psql -U datahub -d retail -t \
  -c "SELECT COUNT(*) FROM (SELECT order_code FROM orders GROUP BY order_code HAVING COUNT(*)>1) x" \
  2>/dev/null | tr -d ' ')
[[ "$DUP_CODES" -ge 20 ]] && pass "DQ issue: ${DUP_CODES} duplicate order codes" \
  || fail "DQ issue: expected ≥20 duplicate order codes, got ${DUP_CODES}"

# ── Airflow ──────────────────────────────────────────────────────────────────
head "Airflow"
if curl -sf http://localhost:8082/health | grep -q '"status":"healthy"'; then
  pass "Airflow webserver healthy"
else
  fail "Airflow webserver not healthy"
fi

for dag in dbt_to_om_dag wayfair_mock_ingestion om_profiling_dag; do
  STATUS=$(curl -sf -u admin:admin123 \
    "http://localhost:8082/api/v1/dags/$dag" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print('ok' if not d.get('is_paused') else 'paused')" 2>/dev/null)
  if [[ "$STATUS" == "ok" ]]; then
    pass "DAG '$dag' visible and active"
  elif [[ "$STATUS" == "paused" ]]; then
    pass "DAG '$dag' visible (paused — unpause to run)"
  else
    fail "DAG '$dag' not found"
  fi
done

# ── OpenMetadata ─────────────────────────────────────────────────────────────
head "OpenMetadata"
if curl -sf http://localhost:8585 2>/dev/null | grep -q "OpenMetadata"; then
  pass "OpenMetadata server UI serving at :8585"
else
  fail "OpenMetadata server not responding"
fi

# ── MinIO ────────────────────────────────────────────────────────────────────
head "MinIO"
if curl -sf http://localhost:9000/minio/health/live; then
  pass "MinIO S3 API healthy"
else
  fail "MinIO not healthy"
fi

for bucket in warehouse raw; do
  EXISTS=$(docker compose exec -T minio-init mc ls myminio/$bucket &>/dev/null && echo yes || echo no)
  [[ "$EXISTS" == "yes" ]] && pass "Bucket '$bucket' exists" || fail "Bucket '$bucket' missing"
done

# ── API ──────────────────────────────────────────────────────────────────────
head "FastAPI Backend"
if curl -sf http://localhost:8000/health | grep -q '"status"'; then
  pass "API /health endpoint responding"
else
  fail "API /health not responding"
fi

# ── Frontend ─────────────────────────────────────────────────────────────────
head "Frontend"
if curl -sf http://localhost:3000 | grep -q "DataHub\|html"; then
  pass "Frontend serving at http://localhost:3000"
else
  fail "Frontend not responding"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "  Results: ${GREEN}${PASS} passed${NC}  ${RED}${FAIL} failed${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
[[ "$FAIL" -eq 0 ]] && echo -e "${GREEN}  All checks passed — POC is healthy!${NC}" \
  || echo -e "${RED}  Some checks failed — review output above.${NC}"
echo ""
exit "$FAIL"
