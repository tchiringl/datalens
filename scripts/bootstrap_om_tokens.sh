#!/usr/bin/env bash
# bootstrap_om_tokens.sh — Fetch an OpenMetadata JWT token and inject it into
# all ingestion YAML configs that contain the placeholder "your-jwt-token-here".
#
# Run this AFTER `make up` and AFTER OpenMetadata is healthy:
#   make bootstrap-om
#
# Required env vars (set in .env):
#   OM_USERNAME   e.g. admin@openmetadata.org
#   OM_PASSWORD   (required, no default)

set -euo pipefail

OM_HOST="${OM_HOST:-localhost}"
OM_PORT="${OM_PORT:-8585}"
OM_URL="http://${OM_HOST}:${OM_PORT}"

if [[ -z "${OM_PASSWORD:-}" ]]; then
  echo "ERROR: OM_PASSWORD env var is not set. Set it in your .env file." >&2
  exit 1
fi

USERNAME="${OM_USERNAME:-admin@openmetadata.org}"
ENCODED_PASS=$(echo -n "${OM_PASSWORD}" | base64)

echo "Fetching OpenMetadata JWT token from ${OM_URL} ..."
TOKEN=$(curl -sf \
  -X POST "${OM_URL}/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${USERNAME}\",\"password\":\"${ENCODED_PASS}\"}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['accessToken'])")

if [[ -z "${TOKEN}" ]]; then
  echo "ERROR: Failed to obtain JWT token. Check OM credentials and ensure OM is running." >&2
  exit 1
fi

echo "Token obtained. Injecting into openmetadata/ingestion/*.yml ..."
for cfg in openmetadata/ingestion/*.yml; do
  if grep -q "your-jwt-token-here" "${cfg}"; then
    sed -i "s/your-jwt-token-here/${TOKEN}/g" "${cfg}"
    echo "  Updated: ${cfg}"
  fi
done

echo "Done. OM JWT tokens injected."
