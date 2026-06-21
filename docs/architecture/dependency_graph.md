# NXT8 Dependency Graph

> Static dependency graph derived from Python imports. Internal dependencies are resolved heuristically for the `/app` monorepo and especially for the `backend` flat-import style (`agents.*`, `core.*`).

## High-level graph

```text
backend/server.py
 ├─ agents/*
 ├─ core/*
 ├─ channels/*
 └─ nxt8_langgraph_ultra.py

nxt8_langgraph_ultra.py
 └─ agents/hermes_max_tools_and_coo.py

agents/personas.py (shim)
 └─ agents/legacy/personas_legacy.py

agents/orchestrator.py (shim)
 └─ agents/legacy/orchestrator_legacy.py

agents/hermes_graph_v2.py (shim)
 └─ agents/legacy/hermes_graph_v2_legacy.py

agents/hermes_os_graph.py (shim)
 └─ agents/legacy/hermes_os_graph_legacy.py

agents/joker.py (shim)
 └─ agents/legacy/joker_legacy.py
```

## Top import hubs

| File | Imported by count | Notes |
|---|---:|---|
| `/app/backend/core/db.py` | 58 | major shared infra |
| `/app/backend/core/deepseek.py` | 20 |  |
| `/app/backend/agents/hermes.py` | 18 |  |
| `/app/backend/agents/personas.py` | 18 | shim |
| `/app/backend/agents/memory.py` | 12 |  |
| `/app/backend/agents/manifests.py` | 11 |  |
| `/app/backend/core/complexity_router.py` | 10 |  |
| `/app/backend/agents/roi.py` | 9 |  |
| `/app/backend/core/approval_gate.py` | 8 |  |
| `/app/backend/core/nxt8_graph.py` | 7 |  |
| `/app/backend/core/telegram_bot.py` | 7 |  |
| `/app/backend/agents/hermes_tools_audit.py` | 6 |  |
| `/app/backend/server.py` | 6 | entrypoint |
| `/app/backend/agents/agent_charter.py` | 5 |  |
| `/app/backend/agents/ai_mentor.py` | 5 |  |
| `/app/backend/agents/diagnostics.py` | 5 |  |
| `/app/backend/agents/hermes_evolution.py` | 5 |  |
| `/app/backend/agents/inter_agent.py` | 5 |  |
| `/app/backend/agents/mempalace_bridge.py` | 5 |  |
| `/app/backend/agents/persona_prompts.py` | 5 |  |

## Explicit shim → legacy edges

- `/app/backend/agents/hermes_graph_v2.py` → `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
- `/app/backend/agents/hermes_os_graph.py` → `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
- `/app/backend/agents/joker.py` → `/app/backend/agents/legacy/joker_legacy.py`
- `/app/backend/agents/orchestrator.py` → `/app/backend/agents/legacy/orchestrator_legacy.py`
- `/app/backend/agents/personas.py` → `/app/backend/agents/legacy/personas_legacy.py`

## Cycles

### Cycle 1
```text
/app/backend/agents/hermes.py
/app/backend/agents/hermes_evolution.py
/app/backend/agents/hermes_max_tools_and_coo.py
/app/backend/agents/hermes_tools_audit.py
/app/backend/agents/inter_agent.py
/app/backend/agents/legacy/personas_legacy.py
/app/backend/agents/personas.py
/app/backend/core/approval_gate.py
/app/backend/core/nxt8_graph.py
/app/backend/core/telegram_bot.py
/app/backend/core/whatsapp_bot.py
```

## Per-file dependency adjacency (runtime + legacy)

### `/app/backend/agents/__init__.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - _(none)_

### `/app/backend/agents/_pipeline_hooks.py`

- **Imports:**
  - `/app/backend/agents/reliability.py`
  - `/app/backend/agents/roi.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_fix2_voice_roi_and_stream_tokens.py`

### `/app/backend/agents/agent_charter.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
  - `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/tests/test_charter.py`

### `/app/backend/agents/ai_mentor.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_ai_mentor.py`

### `/app/backend/agents/attachments.py`

- **Imports:**
  - `/app/backend/agents/documents.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/agents/classifier.py`

- **Imports:**
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`

### `/app/backend/agents/cross_dept.py`

- **Imports:**
  - `/app/backend/agents/memory.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/agents/diagnostics.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_detect_bottlenecks_sandbox.py`
  - `/app/backend_test_tenant_isolation.py`

### `/app/backend/agents/digest.py`

- **Imports:**
  - `/app/backend/agents/pulse.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
  - `/app/backend/core/telegram_bot.py`
  - `/app/backend/core/whatsapp_bot.py`
- **Imported by:**
  - `/app/backend/core/scheduler.py`
  - `/app/backend/server.py`

### `/app/backend/agents/documents.py`

- **Imports:**
  - `/app/backend/agents/mempalace_bridge.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/attachments.py`
  - `/app/backend/server.py`
  - `/app/backend_test_tenant_isolation.py`

### `/app/backend/agents/hermes.py`

- **Imports:**
  - `/app/backend/agents/agent_charter.py`
  - `/app/backend/agents/ai_mentor.py`
  - `/app/backend/agents/classifier.py`
  - `/app/backend/agents/diagnostics.py`
  - `/app/backend/agents/hermes_directive.py`
  - `/app/backend/agents/hermes_evolution.py`
  - `/app/backend/agents/hermes_tools_audit.py`
  - `/app/backend/agents/inter_agent.py`
  - `/app/backend/agents/joker.py`
  - `/app/backend/agents/manifests.py`
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/mempalace_bridge.py`
  - `/app/backend/agents/onboarding.py`
  - `/app/backend/agents/roi.py`
  - `/app/backend/core/complexity_router.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/hermes_coo.py`
  - `/app/backend/agents/hermes_max_tools_and_coo.py`
  - `/app/backend/agents/inter_agent.py`
  - `/app/backend/channels/registry.py`
  - `/app/backend/core/nxt8_graph.py`
  - `/app/backend/core/telegram_bot.py`
  - `/app/backend/core/whatsapp_bot.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_approval_gate.py`
  - `/app/backend/tests/test_detect_bottlenecks_sandbox.py`
  - `/app/backend/tests/test_hermes_evolution.py`
  - `/app/backend/tests/test_inter_agent.py`
  - `/app/backend/tests/test_p0_unification.py`
  - `/app/backend/tests/test_p1_documents_and_hermes_tools.py`
  - `/app/backend/tests/test_web_search_sanitization.py`
  - `/app/backend_test_escalate_depth.py`
  - `/app/backend_test_hermes_audit.py`
  - `/app/backend_test_hermes_audit_integration.py`

### `/app/backend/agents/hermes_coo.py`

- **Imports:**
  - `/app/backend/agents/hermes.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_p0_unification.py`

### `/app/backend/agents/hermes_directive.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/tests/test_hermes_evolution.py`

### `/app/backend/agents/hermes_evolution.py`

- **Imports:**
  - `/app/backend/core/db.py`
  - `/app/backend/core/telegram_bot.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_hermes_evolution.py`
  - `/app/backend_test_hermes_audit.py`
  - `/app/backend_test_hermes_audit_integration.py`

### `/app/backend/agents/hermes_graph_v2.py`

- **Imports:**
  - `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/agents/hermes_max_tools_and_coo.py`

- **Imports:**
  - `/app/backend/agents/hermes.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/nxt8_langgraph_ultra.py`
  - `/app/backend/tests/test_hermes_ultra.py`
  - `/app/backend/tests/test_p0_unification.py`

### `/app/backend/agents/hermes_os_graph.py`

- **Imports:**
  - `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/agents/hermes_proxy.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/agents/hermes_tools_audit.py`

- **Imports:**
  - `/app/backend/agents/personas.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_hermes_tools_audit.py`
  - `/app/backend_test_hermes_audit.py`
  - `/app/backend_test_hermes_audit_integration.py`
  - `/app/backend_test_hermes_self_audit_endpoint_simple.py`

### `/app/backend/agents/inter_agent.py`

- **Imports:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_inter_agent.py`
  - `/app/backend_test_escalate_depth.py`
  - `/app/backend_test_inter_agent_depth.py`

### `/app/backend/agents/joker.py`

- **Imports:**
  - `/app/backend/agents/legacy/joker_legacy.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/channels/registry.py`
  - `/app/backend/server.py`

### `/app/backend/agents/legacy/__init__.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - _(none)_

### `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`

- **Imports:**
  - `/app/backend/agents/agent_charter.py`
  - `/app/backend/agents/manifests.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/hermes_graph_v2.py`

### `/app/backend/agents/legacy/hermes_os_graph_legacy.py`

- **Imports:**
  - `/app/backend/agents/agent_charter.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
  - `/app/backend/core/hermes_memory.py`
- **Imported by:**
  - `/app/backend/agents/hermes_os_graph.py`

### `/app/backend/agents/legacy/joker_legacy.py`

- **Imports:**
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/joker.py`

### `/app/backend/agents/legacy/orchestrator_legacy.py`

- **Imports:**
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/reliability.py`
  - `/app/backend/agents/roi.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/orchestrator.py`

### `/app/backend/agents/legacy/personas_legacy.py`

- **Imports:**
  - `/app/backend/agents/agent_charter.py`
  - `/app/backend/agents/ai_mentor.py`
  - `/app/backend/agents/diagnostics.py`
  - `/app/backend/agents/hermes_max_tools_and_coo.py`
  - `/app/backend/agents/manifests.py`
  - `/app/backend/agents/market_radar.py`
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/mentor.py`
  - `/app/backend/agents/persona_prompts.py`
  - `/app/backend/agents/prompt_policy_registry.py`
  - `/app/backend/agents/roi.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/core/company_context.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/personas.py`

### `/app/backend/agents/manifests.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/onboarding.py`
  - `/app/backend/core/access_guard.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_approval_gate.py`
  - `/app/backend/tests/test_charter.py`
  - `/app/backend/tests/test_inter_agent.py`
  - `/app/backend/tests/test_manifests.py`
  - `/app/backend/tests/test_plan_unification.py`

### `/app/backend/agents/market_radar.py`

- **Imports:**
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/server.py`

### `/app/backend/agents/memory.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/cross_dept.py`
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/orchestrator_legacy.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/core/memory_manager.py`
  - `/app/backend/core/scheduler.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_hermes_ultra.py`
  - `/app/backend/tests/test_memory_m3_session_limits.py`
  - `/app/backend/tests/test_memory_tenant_isolation.py`
  - `/app/backend/tests/test_multi_tenancy.py`
  - `/app/backend_test_tenant_isolation.py`

### `/app/backend/agents/mempalace_bridge.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/documents.py`
  - `/app/backend/agents/hermes.py`
  - `/app/backend/core/memory_manager.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_mempalace_tenant_isolation.py`

### `/app/backend/agents/mentor.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/server.py`

### `/app/backend/agents/onboarding.py`

- **Imports:**
  - `/app/backend/agents/manifests.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/server.py`

### `/app/backend/agents/orchestrator.py`

- **Imports:**
  - `/app/backend/agents/legacy/orchestrator_legacy.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/agents/payments.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_plan_unification.py`

### `/app/backend/agents/persona_prompts.py`

- **Imports:**
  - `/app/backend/agents/prompt_policy_registry.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/tests/test_agent_prompt_safety_rules.py`
  - `/app/backend/tests/test_analyst_proactive_prompt.py`
  - `/app/backend/tests/test_prompt_policy_registry.py`
  - `/app/backend/tests/test_role_boundary_prompts.py`

### `/app/backend/agents/personas.py`

- **Imports:**
  - `/app/backend/agents/ai_mentor.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/core/company_context.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/nxt8_graph.py`
- **Imported by:**
  - `/app/backend/agents/hermes_tools_audit.py`
  - `/app/backend/agents/inter_agent.py`
  - `/app/backend/channels/registry.py`
  - `/app/backend/core/scheduler.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_agent_prompt_safety_rules.py`
  - `/app/backend/tests/test_analyst_proactive_prompt.py`
  - `/app/backend/tests/test_inter_agent.py`
  - `/app/backend/tests/test_p2_hermes_migration.py`
  - `/app/backend/tests/test_plan_unification.py`
  - `/app/backend/tests/test_prompt_policy_registry.py`
  - `/app/backend/tests/test_role_boundary_prompts.py`
  - `/app/backend_test.py`
  - `/app/backend_test_analyst_client_manager.py`
  - `/app/backend_test_escalate_depth.py`
  - `/app/backend_test_inter_agent_depth.py`
  - `/app/backend_test_project_coord.py`
  - `/app/test_tool_invocation.py`

### `/app/backend/agents/prompt_fragments.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/prompt_policy_registry.py`
  - `/app/backend/tests/test_prompt_policy_registry.py`

### `/app/backend/agents/prompt_policy_registry.py`

- **Imports:**
  - `/app/backend/agents/prompt_fragments.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/persona_prompts.py`
  - `/app/backend/core/nxt8_graph.py`
  - `/app/backend/tests/test_agent_prompt_safety_rules.py`
  - `/app/backend/tests/test_prompt_policy_registry.py`

### `/app/backend/agents/pulse.py`

- **Imports:**
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/digest.py`
  - `/app/backend/core/scheduler.py`
  - `/app/backend/server.py`

### `/app/backend/agents/reliability.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/_pipeline_hooks.py`
  - `/app/backend/agents/legacy/orchestrator_legacy.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_reliability_thresholds.py`

### `/app/backend/agents/roi.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/_pipeline_hooks.py`
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/orchestrator_legacy.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_fix2_voice_roi_and_stream_tokens.py`
  - `/app/backend/tests/test_roi_sanity.py`
  - `/app/backend/tests/test_roi_tenant_isolation.py`
  - `/app/backend_test_tenant_isolation.py`

### `/app/backend/agents/skill_creator.py`

- **Imports:**
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/agents/voice.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/channels/__init__.py`

- **Imports:**
  - `/app/backend/channels/base.py`
  - `/app/backend/channels/registry.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/channels/base.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/channels/__init__.py`
  - `/app/backend/channels/registry.py`
  - `/app/backend/channels/webhook.py`

### `/app/backend/channels/registry.py`

- **Imports:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/joker.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/channels/base.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/channels/__init__.py`

### `/app/backend/channels/webhook.py`

- **Imports:**
  - `/app/backend/channels/base.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/core/__init__.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - _(none)_

### `/app/backend/core/access_guard.py`

- **Imports:**
  - `/app/backend/agents/manifests.py`
- **Imported by:**
  - `/app/backend/core/nxt8_graph.py`

### `/app/backend/core/approval_gate.py`

- **Imports:**
  - `/app/backend/core/db.py`
  - `/app/backend/core/telegram_bot.py`
  - `/app/backend/core/whatsapp_bot.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/pulse.py`
  - `/app/backend/core/telegram_bot.py`
  - `/app/backend/core/whatsapp_bot.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_approval_gate.py`
  - `/app/backend/tests/test_multi_tenancy.py`
  - `/app/backend_test_tenant_isolation.py`

### `/app/backend/core/auth.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_admin_guard.py`
  - `/app/backend/tests/test_auth.py`
  - `/app/backend/tests/test_multi_tenancy.py`
  - `/app/backend_test_tenant_isolation.py`

### `/app/backend/core/company_context.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_company_context.py`

### `/app/backend/core/complexity_router.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/core/nxt8_graph.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_complexity_router.py`
  - `/app/backend_test_complexity_router_edge_cases.py`
  - `/app/backend_test_complexity_router_verification.py`
  - `/app/backend_test_nxt8_graph_router_integration.py`
  - `/app/test_debug_intent.py`
  - `/app/test_debug_router.py`
  - `/app/test_debug_sensitivity.py`

### `/app/backend/core/db.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/_pipeline_hooks.py`
  - `/app/backend/agents/ai_mentor.py`
  - `/app/backend/agents/attachments.py`
  - `/app/backend/agents/cross_dept.py`
  - `/app/backend/agents/diagnostics.py`
  - `/app/backend/agents/digest.py`
  - `/app/backend/agents/documents.py`
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/hermes_evolution.py`
  - `/app/backend/agents/hermes_tools_audit.py`
  - `/app/backend/agents/inter_agent.py`
  - `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
  - `/app/backend/agents/legacy/joker_legacy.py`
  - `/app/backend/agents/legacy/orchestrator_legacy.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/market_radar.py`
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/mentor.py`
  - `/app/backend/agents/onboarding.py`
  - `/app/backend/agents/payments.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/agents/pulse.py`
  - `/app/backend/agents/roi.py`
  - `/app/backend/agents/skill_creator.py`
  - `/app/backend/agents/voice.py`
  - `/app/backend/channels/registry.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/core/auth.py`
  - `/app/backend/core/company_context.py`
  - `/app/backend/core/hermes_memory.py`
  - `/app/backend/core/migrations/m_tag_memory_with_company_id.py`
  - `/app/backend/core/scheduler.py`
  - `/app/backend/core/scheduler_lock.py`
  - `/app/backend/core/share.py`
  - `/app/backend/core/telegram_bot.py`
  - `/app/backend/core/tour.py`
  - `/app/backend/core/whatsapp_bot.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_admin_guard.py`
  - `/app/backend/tests/test_ai_mentor.py`
  - `/app/backend/tests/test_approval_gate.py`
  - `/app/backend/tests/test_auth.py`
  - `/app/backend/tests/test_fix2_voice_roi_and_stream_tokens.py`
  - `/app/backend/tests/test_hermes_ultra.py`
  - `/app/backend/tests/test_memory_m3_session_limits.py`
  - `/app/backend/tests/test_memory_tenant_isolation.py`
  - `/app/backend/tests/test_multi_tenancy.py`
  - `/app/backend/tests/test_p0_unification.py`
  - `/app/backend/tests/test_roi_sanity.py`
  - `/app/backend/tests/test_roi_tenant_isolation.py`
  - `/app/backend/tests/test_scheduler_lock.py`
  - `/app/backend/tests/test_share.py`
  - `/app/backend/tests/test_tour.py`
  - `/app/backend_test_escalate_depth.py`
  - `/app/backend_test_hermes_audit.py`
  - `/app/backend_test_hermes_self_audit_endpoint.py`
  - `/app/backend_test_project_coord.py`
  - `/app/backend_test_tenant_isolation.py`

### `/app/backend/core/deepseek.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/classifier.py`
  - `/app/backend/agents/cross_dept.py`
  - `/app/backend/agents/digest.py`
  - `/app/backend/agents/documents.py`
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
  - `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
  - `/app/backend/agents/legacy/joker_legacy.py`
  - `/app/backend/agents/legacy/orchestrator_legacy.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/market_radar.py`
  - `/app/backend/agents/onboarding.py`
  - `/app/backend/agents/skill_creator.py`
  - `/app/backend/core/nxt8_graph.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_fix2_voice_roi_and_stream_tokens.py`
  - `/app/backend/tests/test_llm_unavailable.py`
  - `/app/backend_test_complexity_router_verification.py`
  - `/app/scripts/add_cookies_legal_keys.py`
  - `/app/scripts/translate_i18n.py`

### `/app/backend/core/hermes_memory.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
  - `/app/backend/server.py`

### `/app/backend/core/memory_manager.py`

- **Imports:**
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/mempalace_bridge.py`
- **Imported by:**
  - _(none)_

### `/app/backend/core/migrations/__init__.py`

- **Imports:**
  - _(none resolved)_
- **Imported by:**
  - _(none)_

### `/app/backend/core/migrations/m_tag_memory_with_company_id.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`

### `/app/backend/core/nxt8_graph.py`

- **Imports:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/prompt_policy_registry.py`
  - `/app/backend/core/access_guard.py`
  - `/app/backend/core/complexity_router.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/personas.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_complexity_router.py`
  - `/app/backend/tests/test_prompt_policy_registry.py`
  - `/app/backend_test_complexity_router_verification.py`
  - `/app/backend_test_nxt8_graph_router_integration.py`
  - `/app/backend_test_project_coord.py`

### `/app/backend/core/scheduler.py`

- **Imports:**
  - `/app/backend/agents/digest.py`
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/agents/pulse.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/scheduler_lock.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_analyst_self_scan_scheduler.py`
  - `/app/backend/tests/test_memory_m3_session_limits.py`

### `/app/backend/core/scheduler_lock.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/core/scheduler.py`
  - `/app/backend/tests/test_scheduler_lock.py`

### `/app/backend/core/share.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_share.py`

### `/app/backend/core/telegram_bot.py`

- **Imports:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/digest.py`
  - `/app/backend/agents/hermes_evolution.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_telegram_bot.py`
  - `/app/backend_test_hermes_audit.py`
  - `/app/backend_test_hermes_audit_integration.py`

### `/app/backend/core/tour.py`

- **Imports:**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_tour.py`

### `/app/backend/core/whatsapp_bot.py`

- **Imports:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/digest.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_whatsapp_bot.py`

### `/app/backend/nxt8_langgraph_ultra.py`

- **Imports:**
  - `/app/backend/agents/hermes_max_tools_and_coo.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_hermes_ultra.py`

### `/app/backend/server.py`

- **Imports:**
  - `/app/backend/agents/_pipeline_hooks.py`
  - `/app/backend/agents/ai_mentor.py`
  - `/app/backend/agents/attachments.py`
  - `/app/backend/agents/cross_dept.py`
  - `/app/backend/agents/diagnostics.py`
  - `/app/backend/agents/digest.py`
  - `/app/backend/agents/documents.py`
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/hermes_coo.py`
  - `/app/backend/agents/hermes_evolution.py`
  - `/app/backend/agents/hermes_graph_v2.py`
  - `/app/backend/agents/hermes_os_graph.py`
  - `/app/backend/agents/hermes_proxy.py`
  - `/app/backend/agents/hermes_tools_audit.py`
  - `/app/backend/agents/inter_agent.py`
  - `/app/backend/agents/joker.py`
  - `/app/backend/agents/manifests.py`
  - `/app/backend/agents/market_radar.py`
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/mempalace_bridge.py`
  - `/app/backend/agents/mentor.py`
  - `/app/backend/agents/onboarding.py`
  - `/app/backend/agents/orchestrator.py`
  - `/app/backend/agents/payments.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/agents/pulse.py`
  - `/app/backend/agents/reliability.py`
  - `/app/backend/agents/roi.py`
  - `/app/backend/agents/skill_creator.py`
  - `/app/backend/agents/voice.py`
  - `/app/backend/channels/__init__.py`
  - `/app/backend/channels/webhook.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/core/auth.py`
  - `/app/backend/core/company_context.py`
  - `/app/backend/core/complexity_router.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
  - `/app/backend/core/hermes_memory.py`
  - `/app/backend/core/migrations/m_tag_memory_with_company_id.py`
  - `/app/backend/core/nxt8_graph.py`
  - `/app/backend/core/scheduler.py`
  - `/app/backend/core/share.py`
  - `/app/backend/core/telegram_bot.py`
  - `/app/backend/core/tour.py`
  - `/app/backend/core/whatsapp_bot.py`
  - `/app/backend/nxt8_langgraph_ultra.py`
- **Imported by:**
  - `/app/backend/tests/test_admin_guard.py`
  - `/app/backend/tests/test_analyst_findings_actions.py`
  - `/app/backend/tests/test_analyst_findings_endpoint.py`
  - `/app/backend/tests/test_hermes_self_audit_endpoint.py`
  - `/app/backend/tests/test_multi_tenancy.py`
  - `/app/backend_test_hermes_self_audit_endpoint_simple.py`
