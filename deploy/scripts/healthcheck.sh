#!/usr/bin/env bash
# =====================================================================
# NXT8 — post-deploy smoke test
# Usage: bash deploy/scripts/healthcheck.sh [domain]
# Если domain не задан — используем 127.0.0.1:8001 (для локальной проверки).
# =====================================================================
set -uo pipefail

DOMAIN="${1:-}"
if [[ -n "${DOMAIN}" ]]; then
  BASE="https://${DOMAIN}"
else
  BASE="http://127.0.0.1:8001"
fi

echo "==> Healthcheck against ${BASE}"
echo

FAIL=0

check() {
  local label="$1"; local cmd="$2"; local expect="$3"
  local out
  out=$(eval "${cmd}" 2>&1) || true
  if echo "${out}" | grep -q "${expect}"; then
    echo "   ✅ ${label}"
  else
    echo "   ❌ ${label}"
    echo "      cmd: ${cmd}"
    echo "      out: ${out:0:300}"
    FAIL=$((FAIL+1))
  fi
}

# --- Core ---
check "/api/health → status=ok"           "curl -s --max-time 10 ${BASE}/api/health"                     '"status":"ok"'
check "/api/health → mongo connected"     "curl -s --max-time 10 ${BASE}/api/health"                     '"mongo":true'
check "/api/health → LLM live (or mock)"  "curl -s --max-time 10 ${BASE}/api/health"                     '"deepseek"'

# --- Seed (idempotent) ---
check "/api/seed (idempotent)"            "curl -s -X POST --max-time 30 ${BASE}/api/seed"               '"memories"'

# --- Personas API ---
check "/api/personas list"                "curl -s --max-time 10 ${BASE}/api/personas"                   '"hermes"'
check "/api/personas/bookkeeper requires pro plan (HTTP 402 on basic)" \
      "curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST ${BASE}/api/personas/bookkeeper/chat -H 'Content-Type: application/json' -d '{\"message\":\"test\",\"plan_id\":\"basic\"}'" \
      "402"

# --- Chat (mock-safe) ---
check "/api/chat responds"                "curl -s -X POST --max-time 30 ${BASE}/api/chat -H 'Content-Type: application/json' -d '{\"message\":\"hello\"}'" \
                                          '"content"'

# --- MemPalace ---
check "/api/mempalace/health"             "curl -s --max-time 15 ${BASE}/api/mempalace/health"           '"ok":true'

# --- Voice availability ---
check "/api/voice/health"                 "curl -s --max-time 5 ${BASE}/api/health"                      '"voice"'

echo
if [[ "${FAIL}" -eq 0 ]]; then
  echo "==> ✅ All smoke checks passed."
  exit 0
else
  echo "==> ❌ ${FAIL} smoke checks failed."
  exit 1
fi
