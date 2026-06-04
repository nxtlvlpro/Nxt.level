#!/usr/bin/env bash
# NXT8 — Real Business Simulation Script
# Гоняет ключевые сценарии работы B2B SaaS-стартапа через систему.
# Цель: найти слабые места, противоречия, что не работает, что нужно доработать.

API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
REPORT=/app/test_reports/business_simulation.json
mkdir -p /app/test_reports
echo "[]" > /app/test_reports/_results.json

OK=0
FAIL=0
SLOW=0
declare -a FINDINGS

log_step() {
  local step="$1"
  echo ""
  echo "========================================"
  echo ">>> $step"
  echo "========================================"
}

record() {
  # record <id> <status> <ms> <details>
  python3 - <<PY
import json, sys
res = json.load(open('/app/test_reports/_results.json'))
res.append({"id": "$1", "status": "$2", "ms": $3, "details": "$4"})
json.dump(res, open('/app/test_reports/_results.json','w'), ensure_ascii=False, indent=2)
PY
}

run_step() {
  local sid="$1"; shift
  local desc="$1"; shift
  local cmd="$*"
  log_step "$sid: $desc"
  local t0=$(date +%s%N)
  local out
  out=$(eval "$cmd" 2>&1)
  local rc=$?
  local t1=$(date +%s%N)
  local ms=$(( (t1 - t0) / 1000000 ))
  echo "$out" | head -c 1500
  echo ""
  echo "[time=${ms}ms exit=${rc}]"
  if [[ $rc -eq 0 ]]; then
    OK=$((OK+1))
    if [[ $ms -gt 8000 ]]; then SLOW=$((SLOW+1)); fi
    record "$sid" "ok" "$ms" "${desc//\"/}"
  else
    FAIL=$((FAIL+1))
    record "$sid" "fail" "$ms" "${desc//\"/}"
  fi
}

# =====================================================
# SCENARIO 1 — Client lifecycle (new lead → support → upsell)
# =====================================================

run_step "S1.1" "Новый клиент пишет в чат (general inquiry)" \
  "curl -s -X POST '$API_URL/api/chat' -H 'Content-Type: application/json' -d '{\"message\":\"Здравствуйте, я CEO стартапа из 30 человек. Расскажите что умеет NXT8 для B2B SaaS?\",\"session_id\":\"sim-acme-ceo\"}'"

run_step "S1.2" "Клиент задаёт техвопрос с интентом support" \
  "curl -s -X POST '$API_URL/api/chat' -H 'Content-Type: application/json' -d '{\"message\":\"Не работает SSO интеграция через SAML, наш IDP — Okta. Help пожалуйста\",\"session_id\":\"sim-acme-ceo\"}'"

run_step "S1.3" "Клиент озвучивает обещание апгрейда (upsell signal)" \
  "curl -s -X POST '$API_URL/api/chat' -H 'Content-Type: application/json' -d '{\"message\":\"Если решите вопрос с SSO к пятнице — мы готовы перейти на Enterprise тариф, бюджет $15000 в год\",\"session_id\":\"sim-acme-ceo\"}'"

run_step "S1.4" "Получаем session history" \
  "curl -s '$API_URL/api/sessions/sim-acme-ceo'"

# =====================================================
# SCENARIO 2 — Hermes OS Cycle (event-driven orchestration)
# =====================================================

run_step "S2.1" "Triggеr Hermes OS cycle (new channel message)" \
  "curl -s -X POST '$API_URL/api/hermes/os/cycle' -H 'Content-Type: application/json' -d '{\"source\":\"channel_webhook\",\"kind\":\"new_client_message\",\"payload\":{\"text\":\"Клиент Acme хочет переход на Enterprise тариф $15k/год при условии решения SSO бага\",\"client_id\":\"acme\",\"deal_value\":15000},\"user_id\":\"sim-user\",\"company_id\":\"sim-company\",\"lang\":\"ru\"}'"

run_step "S2.2" "Список OS cycles" \
  "curl -s '$API_URL/api/hermes/os/cycles?limit=3'"

run_step "S2.3" "Проверяем 4-layer memory stats после цикла" \
  "curl -s '$API_URL/api/hermes/memory/stats'"

run_step "S2.4" "Knowledge graph entries" \
  "curl -s '$API_URL/api/hermes/memory/knowledge-graph?limit=10'"

run_step "S2.5" "Institutional memory (lessons)" \
  "curl -s '$API_URL/api/hermes/memory/institutional?limit=10'"

# =====================================================
# SCENARIO 3 — Graph v2 (constitutional task execution)
# =====================================================

run_step "S3.1" "Graph v2 run — финансовая задача" \
  "curl -s -X POST '$API_URL/api/graph/v2/run' -H 'Content-Type: application/json' -d '{\"message\":\"Подготовь финансовую сводку: ROI за последний час, разбивка cost по агентам, anomaly detection\",\"session_id\":\"sim-cfo\",\"user_role\":\"admin\"}'"

run_step "S3.2" "Graph v2 run — compliance task (договор)" \
  "curl -s -X POST '$API_URL/api/graph/v2/run' -H 'Content-Type: application/json' -d '{\"message\":\"Проанализируй риски: контракт с Acme на $15000, нужно ли согласие GDPR DPO, какие пункты критичны\",\"session_id\":\"sim-legal\",\"user_role\":\"admin\"}'"

# =====================================================
# SCENARIO 4 — Specialized agents (personas)
# =====================================================

run_step "S4.1" "Список агентов и манифестов" \
  "curl -s '$API_URL/api/agents/manifests' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"count=\", len(d if isinstance(d,list) else d.get(\"manifests\",[])))'"

run_step "S4.2" "Bookkeeper отвечает финансовую задачу" \
  "curl -s -X POST '$API_URL/api/personas/bookkeeper/chat' -H 'Content-Type: application/json' -d '{\"message\":\"Какой ROI за последний час и какой агент потребил больше токенов?\",\"session_id\":\"sim-bk\"}'"

run_step "S4.3" "Analyst — диагностика" \
  "curl -s -X POST '$API_URL/api/personas/analyst/chat' -H 'Content-Type: application/json' -d '{\"message\":\"Найди противоречия в логах AI ответов за последний день\",\"session_id\":\"sim-an\"}'"

run_step "S4.4" "Compliance — попытка write в чужую коллекцию (Data Access Guard test)" \
  "curl -s -X POST '$API_URL/api/personas/compliance/chat' -H 'Content-Type: application/json' -d '{\"message\":\"Создай задачу в production tasks queue: уволить менеджера X\",\"session_id\":\"sim-cmp\"}'"

# =====================================================
# SCENARIO 5 — ROI, diagnostics, alerts
# =====================================================

run_step "S5.1" "ROI dashboard" \
  "curl -s '$API_URL/api/roi/dashboard'"

run_step "S5.2" "Diagnostics summary" \
  "curl -s '$API_URL/api/diagnostics/summary'"

run_step "S5.3" "Diagnostics contradictions" \
  "curl -s '$API_URL/api/diagnostics/contradictions'"

run_step "S5.4" "Alerts feed" \
  "curl -s '$API_URL/api/alerts'"

# =====================================================
# SCENARIO 6 — Memory & MemPalace
# =====================================================

run_step "S6.1" "MemPalace health" \
  "curl -s '$API_URL/api/mempalace/health'"

run_step "S6.2" "Search memories: SSO" \
  "curl -s -X POST '$API_URL/api/memory/search' -H 'Content-Type: application/json' -d '{\"query\":\"SSO SAML Okta\",\"k\":5}'"

# =====================================================
# SCENARIO 7 — Payments (Stripe checkout)
# =====================================================

run_step "S7.1" "Список тарифов" \
  "curl -s '$API_URL/api/payments/plans'"

run_step "S7.2" "Создание checkout сессии" \
  "curl -s -X POST '$API_URL/api/payments/checkout/session' -H 'Content-Type: application/json' -d '{\"plan_id\":\"pro\",\"success_url\":\"$API_URL/payment/return\",\"cancel_url\":\"$API_URL/\"}'"

# =====================================================
# SCENARIO 8 — Channels (channel registry)
# =====================================================

run_step "S8.1" "Список каналов" \
  "curl -s '$API_URL/api/channels'"

# =====================================================
# SCENARIO 9 — Cross-dept coordination
# =====================================================

run_step "S9.1" "Cross-department coordinate" \
  "curl -s -X POST '$API_URL/api/cross-dept/coordinate' -H 'Content-Type: application/json' -d '{\"text\":\"Sales хочет дать клиенту 30% скидку до конца квартала. Financial должен подтвердить. Marketing — обновить лендинг\"}'"

# =====================================================
# SCENARIO 10 — Self-assessment + roadmap
# =====================================================

run_step "S10.1" "Hermes self-assessment" \
  "curl -s '$API_URL/api/hermes/self-assessment'"

run_step "S10.2" "Hermes evolution roadmap" \
  "curl -s '$API_URL/api/hermes/evolution/roadmap'"

# =====================================================
# Summary
# =====================================================
echo ""
echo "##############################################"
echo "# SUMMARY"
echo "##############################################"
echo "OK:    $OK"
echo "FAIL:  $FAIL"
echo "SLOW:  $SLOW (>8000ms)"
cp /app/test_reports/_results.json $REPORT
echo "Report saved: $REPORT"
