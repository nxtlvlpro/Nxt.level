# NXT8 System Map

> Analysis-only audit. No runtime code was changed. This map is generated from static import analysis and project structure heuristics.

## Scope

- Total Python files scanned: **144**
- Runtime files (`backend/**/*.py`, excluding tests): **63**
- Legacy runtime files: **6**
- Test files: **69**
- Support scripts: **4**
- Embedded third-party Python files: **2**

## Entrypoints used for runtime reachability

- `/app/backend/nxt8_langgraph_ultra.py`
- `/app/backend/server.py`

## Key findings

- Shim files detected: **5**
- Legacy dependencies detected: **5**
- Cyclic import groups detected: **1**
- Unused runtime candidates: **5**

### Shim files

- `/app/backend/agents/hermes_graph_v2.py`
- `/app/backend/agents/hermes_os_graph.py`
- `/app/backend/agents/joker.py`
- `/app/backend/agents/orchestrator.py`
- `/app/backend/agents/personas.py`

### Legacy dependencies

- `/app/backend/agents/hermes_graph_v2.py` → `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
- `/app/backend/agents/hermes_os_graph.py` → `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
- `/app/backend/agents/joker.py` → `/app/backend/agents/legacy/joker_legacy.py`
- `/app/backend/agents/orchestrator.py` → `/app/backend/agents/legacy/orchestrator_legacy.py`
- `/app/backend/agents/personas.py` → `/app/backend/agents/legacy/personas_legacy.py`

### Cyclic import groups

#### Cycle 1
- `/app/backend/agents/hermes.py`
- `/app/backend/agents/hermes_evolution.py`
- `/app/backend/agents/hermes_max_tools_and_coo.py`
- `/app/backend/agents/hermes_tools_audit.py`
- `/app/backend/agents/inter_agent.py`
- `/app/backend/agents/legacy/personas_legacy.py`
- `/app/backend/agents/personas.py`
- `/app/backend/core/approval_gate.py`
- `/app/backend/core/nxt8_graph.py`
- `/app/backend/core/telegram_bot.py`
- `/app/backend/core/whatsapp_bot.py`

### Unused runtime candidates

- `/app/backend/agents/__init__.py`
- `/app/backend/agents/legacy/__init__.py`
- `/app/backend/core/__init__.py`
- `/app/backend/core/memory_manager.py`
- `/app/backend/core/migrations/__init__.py`

## Runtime / Legacy file inventory

| Path | Classification | Imported by | Imports | Runtime used | Confidence |
|---|---|---:|---:|---|---:|
| `/app/backend/agents/__init__.py` | runtime | 0 | 0 | No | 0.72 |
| `/app/backend/agents/_pipeline_hooks.py` | runtime | 2 | 3 | Yes | 0.96 |
| `/app/backend/agents/agent_charter.py` | runtime | 5 | 0 | Yes | 0.96 |
| `/app/backend/agents/ai_mentor.py` | runtime | 5 | 1 | Yes | 0.96 |
| `/app/backend/agents/attachments.py` | runtime | 1 | 2 | Yes | 0.96 |
| `/app/backend/agents/classifier.py` | runtime | 1 | 1 | Yes | 0.96 |
| `/app/backend/agents/cross_dept.py` | runtime | 1 | 3 | Yes | 0.96 |
| `/app/backend/agents/diagnostics.py` | runtime | 5 | 1 | Yes | 0.96 |
| `/app/backend/agents/digest.py` | runtime | 2 | 5 | Yes | 0.96 |
| `/app/backend/agents/documents.py` | runtime | 3 | 3 | Yes | 0.96 |
| `/app/backend/agents/hermes.py` | runtime | 18 | 17 | Yes | 0.96 |
| `/app/backend/agents/hermes_coo.py` | runtime | 2 | 1 | Yes | 0.96 |
| `/app/backend/agents/hermes_directive.py` | runtime | 2 | 0 | Yes | 0.96 |
| `/app/backend/agents/hermes_evolution.py` | runtime | 5 | 2 | Yes | 0.96 |
| `/app/backend/agents/hermes_graph_v2.py` | runtime | 1 | 1 | Yes | 0.96 |
| `/app/backend/agents/hermes_max_tools_and_coo.py` | runtime | 4 | 1 | Yes | 0.96 |
| `/app/backend/agents/hermes_os_graph.py` | runtime | 1 | 1 | Yes | 0.96 |
| `/app/backend/agents/hermes_proxy.py` | runtime | 1 | 0 | Yes | 0.96 |
| `/app/backend/agents/hermes_tools_audit.py` | runtime | 6 | 2 | Yes | 0.96 |
| `/app/backend/agents/inter_agent.py` | runtime | 5 | 3 | Yes | 0.96 |
| `/app/backend/agents/joker.py` | runtime | 3 | 1 | Yes | 0.96 |
| `/app/backend/agents/legacy/__init__.py` | legacy | 0 | 0 | No | 0.76 |
| `/app/backend/agents/legacy/hermes_graph_v2_legacy.py` | legacy | 1 | 3 | Yes | 0.99 |
| `/app/backend/agents/legacy/hermes_os_graph_legacy.py` | legacy | 1 | 4 | Yes | 0.99 |
| `/app/backend/agents/legacy/joker_legacy.py` | legacy | 1 | 2 | Yes | 0.99 |
| `/app/backend/agents/legacy/orchestrator_legacy.py` | legacy | 1 | 5 | Yes | 0.99 |
| `/app/backend/agents/legacy/personas_legacy.py` | legacy | 1 | 15 | Yes | 0.99 |
| `/app/backend/agents/manifests.py` | runtime | 11 | 0 | Yes | 0.96 |
| `/app/backend/agents/market_radar.py` | runtime | 2 | 2 | Yes | 0.96 |
| `/app/backend/agents/memory.py` | runtime | 12 | 1 | Yes | 0.96 |
| `/app/backend/agents/mempalace_bridge.py` | runtime | 5 | 0 | Yes | 0.96 |
| `/app/backend/agents/mentor.py` | runtime | 2 | 1 | Yes | 0.96 |
| `/app/backend/agents/onboarding.py` | runtime | 2 | 3 | Yes | 0.96 |
| `/app/backend/agents/orchestrator.py` | runtime | 1 | 1 | Yes | 0.96 |
| `/app/backend/agents/payments.py` | runtime | 2 | 1 | Yes | 0.96 |
| `/app/backend/agents/persona_prompts.py` | runtime | 5 | 1 | Yes | 0.96 |
| `/app/backend/agents/personas.py` | runtime | 18 | 5 | Yes | 0.96 |
| `/app/backend/agents/prompt_fragments.py` | runtime | 2 | 0 | Yes | 0.96 |
| `/app/backend/agents/prompt_policy_registry.py` | runtime | 5 | 1 | Yes | 0.96 |
| `/app/backend/agents/pulse.py` | runtime | 3 | 2 | Yes | 0.96 |
| `/app/backend/agents/reliability.py` | runtime | 4 | 0 | Yes | 0.96 |
| `/app/backend/agents/roi.py` | runtime | 9 | 1 | Yes | 0.96 |
| `/app/backend/agents/skill_creator.py` | runtime | 1 | 2 | Yes | 0.96 |
| `/app/backend/agents/voice.py` | runtime | 1 | 1 | Yes | 0.96 |
| `/app/backend/channels/__init__.py` | runtime | 1 | 2 | Yes | 0.96 |
| `/app/backend/channels/base.py` | runtime | 3 | 0 | Yes | 0.96 |
| `/app/backend/channels/registry.py` | runtime | 1 | 5 | Yes | 0.96 |
| `/app/backend/channels/webhook.py` | runtime | 1 | 1 | Yes | 0.96 |
| `/app/backend/core/__init__.py` | runtime | 0 | 0 | No | 0.72 |
| `/app/backend/core/access_guard.py` | runtime | 1 | 1 | Yes | 0.96 |
| `/app/backend/core/approval_gate.py` | runtime | 8 | 3 | Yes | 0.96 |
| `/app/backend/core/auth.py` | runtime | 5 | 1 | Yes | 0.96 |
| `/app/backend/core/company_context.py` | runtime | 4 | 1 | Yes | 0.96 |
| `/app/backend/core/complexity_router.py` | runtime | 10 | 0 | Yes | 0.96 |
| `/app/backend/core/db.py` | runtime | 58 | 0 | Yes | 0.96 |
| `/app/backend/core/deepseek.py` | runtime | 20 | 0 | Yes | 0.96 |
| `/app/backend/core/hermes_memory.py` | runtime | 2 | 1 | Yes | 0.96 |
| `/app/backend/core/memory_manager.py` | runtime | 0 | 2 | No | 0.72 |
| `/app/backend/core/migrations/__init__.py` | runtime | 0 | 0 | No | 0.72 |
| `/app/backend/core/migrations/m_tag_memory_with_company_id.py` | runtime | 1 | 1 | Yes | 0.96 |
| `/app/backend/core/nxt8_graph.py` | runtime | 7 | 5 | Yes | 0.96 |
| `/app/backend/core/scheduler.py` | runtime | 3 | 6 | Yes | 0.96 |
| `/app/backend/core/scheduler_lock.py` | runtime | 2 | 1 | Yes | 0.96 |
| `/app/backend/core/share.py` | runtime | 2 | 1 | Yes | 0.96 |
| `/app/backend/core/telegram_bot.py` | runtime | 7 | 3 | Yes | 0.96 |
| `/app/backend/core/tour.py` | runtime | 2 | 1 | Yes | 0.96 |
| `/app/backend/core/whatsapp_bot.py` | runtime | 4 | 3 | Yes | 0.96 |
| `/app/backend/nxt8_langgraph_ultra.py` | runtime | 2 | 1 | Yes | 0.96 |
| `/app/backend/server.py` | runtime | 6 | 47 | Yes | 0.96 |

## Detailed per-file map (runtime + legacy)

### `/app/backend/agents/__init__.py`

- **Path:** `/app/backend/agents/__init__.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - _(no importers detected)_
- **Used in runtime:** `false`
- **Confidence:** `0.72`
- **Confidence basis:** runtime_path, not_reachable_from_runtime_entrypoints

### `/app/backend/agents/_pipeline_hooks.py`

- **Path:** `/app/backend/agents/_pipeline_hooks.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/reliability.py`
  - `/app/backend/agents/roi.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_fix2_voice_roi_and_stream_tokens.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/agent_charter.py`

- **Path:** `/app/backend/agents/agent_charter.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
  - `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/tests/test_charter.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/ai_mentor.py`

- **Path:** `/app/backend/agents/ai_mentor.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_ai_mentor.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/attachments.py`

- **Path:** `/app/backend/agents/attachments.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/documents.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/classifier.py`

- **Path:** `/app/backend/agents/classifier.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/cross_dept.py`

- **Path:** `/app/backend/agents/cross_dept.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/memory.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/diagnostics.py`

- **Path:** `/app/backend/agents/diagnostics.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_detect_bottlenecks_sandbox.py`
  - `/app/backend_test_tenant_isolation.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/digest.py`

- **Path:** `/app/backend/agents/digest.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/pulse.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
  - `/app/backend/core/telegram_bot.py`
  - `/app/backend/core/whatsapp_bot.py`
- **Imported by:**
  - `/app/backend/core/scheduler.py`
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/documents.py`

- **Path:** `/app/backend/agents/documents.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/mempalace_bridge.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/attachments.py`
  - `/app/backend/server.py`
  - `/app/backend_test_tenant_isolation.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes.py`

- **Path:** `/app/backend/agents/hermes.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes_coo.py`

- **Path:** `/app/backend/agents/hermes_coo.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/hermes.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_p0_unification.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes_directive.py`

- **Path:** `/app/backend/agents/hermes_directive.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/tests/test_hermes_evolution.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes_evolution.py`

- **Path:** `/app/backend/agents/hermes_evolution.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
  - `/app/backend/core/telegram_bot.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_hermes_evolution.py`
  - `/app/backend_test_hermes_audit.py`
  - `/app/backend_test_hermes_audit_integration.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes_graph_v2.py`

- **Path:** `/app/backend/agents/hermes_graph_v2.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes_max_tools_and_coo.py`

- **Path:** `/app/backend/agents/hermes_max_tools_and_coo.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/hermes.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/nxt8_langgraph_ultra.py`
  - `/app/backend/tests/test_hermes_ultra.py`
  - `/app/backend/tests/test_p0_unification.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes_os_graph.py`

- **Path:** `/app/backend/agents/hermes_os_graph.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes_proxy.py`

- **Path:** `/app/backend/agents/hermes_proxy.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/hermes_tools_audit.py`

- **Path:** `/app/backend/agents/hermes_tools_audit.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/personas.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_hermes_tools_audit.py`
  - `/app/backend_test_hermes_audit.py`
  - `/app/backend_test_hermes_audit_integration.py`
  - `/app/backend_test_hermes_self_audit_endpoint_simple.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/inter_agent.py`

- **Path:** `/app/backend/agents/inter_agent.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_inter_agent.py`
  - `/app/backend_test_escalate_depth.py`
  - `/app/backend_test_inter_agent_depth.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/joker.py`

- **Path:** `/app/backend/agents/joker.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/legacy/joker_legacy.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/channels/registry.py`
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/legacy/__init__.py`

- **Path:** `/app/backend/agents/legacy/__init__.py`
- **Classification:** `legacy`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - _(no importers detected)_
- **Used in runtime:** `false`
- **Confidence:** `0.76`
- **Confidence basis:** legacy_path, not_reachable_from_runtime_entrypoints

### `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`

- **Path:** `/app/backend/agents/legacy/hermes_graph_v2_legacy.py`
- **Classification:** `legacy`
- **Imports (internal resolved):**
  - `/app/backend/agents/agent_charter.py`
  - `/app/backend/agents/manifests.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/hermes_graph_v2.py`
- **Used in runtime:** `true`
- **Confidence:** `0.99`
- **Confidence basis:** legacy_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/legacy/hermes_os_graph_legacy.py`

- **Path:** `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
- **Classification:** `legacy`
- **Imports (internal resolved):**
  - `/app/backend/agents/agent_charter.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
  - `/app/backend/core/hermes_memory.py`
- **Imported by:**
  - `/app/backend/agents/hermes_os_graph.py`
- **Used in runtime:** `true`
- **Confidence:** `0.99`
- **Confidence basis:** legacy_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/legacy/joker_legacy.py`

- **Path:** `/app/backend/agents/legacy/joker_legacy.py`
- **Classification:** `legacy`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/joker.py`
- **Used in runtime:** `true`
- **Confidence:** `0.99`
- **Confidence basis:** legacy_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/legacy/orchestrator_legacy.py`

- **Path:** `/app/backend/agents/legacy/orchestrator_legacy.py`
- **Classification:** `legacy`
- **Imports (internal resolved):**
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/reliability.py`
  - `/app/backend/agents/roi.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/orchestrator.py`
- **Used in runtime:** `true`
- **Confidence:** `0.99`
- **Confidence basis:** legacy_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/legacy/personas_legacy.py`

- **Path:** `/app/backend/agents/legacy/personas_legacy.py`
- **Classification:** `legacy`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.99`
- **Confidence basis:** legacy_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/manifests.py`

- **Path:** `/app/backend/agents/manifests.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/market_radar.py`

- **Path:** `/app/backend/agents/market_radar.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/memory.py`

- **Path:** `/app/backend/agents/memory.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/mempalace_bridge.py`

- **Path:** `/app/backend/agents/mempalace_bridge.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/documents.py`
  - `/app/backend/agents/hermes.py`
  - `/app/backend/core/memory_manager.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_mempalace_tenant_isolation.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/mentor.py`

- **Path:** `/app/backend/agents/mentor.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/onboarding.py`

- **Path:** `/app/backend/agents/onboarding.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/manifests.py`
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/orchestrator.py`

- **Path:** `/app/backend/agents/orchestrator.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/legacy/orchestrator_legacy.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/payments.py`

- **Path:** `/app/backend/agents/payments.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_plan_unification.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/persona_prompts.py`

- **Path:** `/app/backend/agents/persona_prompts.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/prompt_policy_registry.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/tests/test_agent_prompt_safety_rules.py`
  - `/app/backend/tests/test_analyst_proactive_prompt.py`
  - `/app/backend/tests/test_prompt_policy_registry.py`
  - `/app/backend/tests/test_role_boundary_prompts.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/personas.py`

- **Path:** `/app/backend/agents/personas.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/prompt_fragments.py`

- **Path:** `/app/backend/agents/prompt_fragments.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/prompt_policy_registry.py`
  - `/app/backend/tests/test_prompt_policy_registry.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/prompt_policy_registry.py`

- **Path:** `/app/backend/agents/prompt_policy_registry.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/prompt_fragments.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/persona_prompts.py`
  - `/app/backend/core/nxt8_graph.py`
  - `/app/backend/tests/test_agent_prompt_safety_rules.py`
  - `/app/backend/tests/test_prompt_policy_registry.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/pulse.py`

- **Path:** `/app/backend/agents/pulse.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/digest.py`
  - `/app/backend/core/scheduler.py`
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/reliability.py`

- **Path:** `/app/backend/agents/reliability.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/agents/_pipeline_hooks.py`
  - `/app/backend/agents/legacy/orchestrator_legacy.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_reliability_thresholds.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/roi.py`

- **Path:** `/app/backend/agents/roi.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/skill_creator.py`

- **Path:** `/app/backend/agents/skill_creator.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
  - `/app/backend/core/deepseek.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/agents/voice.py`

- **Path:** `/app/backend/agents/voice.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/channels/__init__.py`

- **Path:** `/app/backend/channels/__init__.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/channels/base.py`
  - `/app/backend/channels/registry.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/channels/base.py`

- **Path:** `/app/backend/channels/base.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - `/app/backend/channels/__init__.py`
  - `/app/backend/channels/registry.py`
  - `/app/backend/channels/webhook.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/channels/registry.py`

- **Path:** `/app/backend/channels/registry.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/agents/joker.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/channels/base.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/channels/__init__.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/channels/webhook.py`

- **Path:** `/app/backend/channels/webhook.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/channels/base.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/__init__.py`

- **Path:** `/app/backend/core/__init__.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - _(no importers detected)_
- **Used in runtime:** `false`
- **Confidence:** `0.72`
- **Confidence basis:** runtime_path, not_reachable_from_runtime_entrypoints

### `/app/backend/core/access_guard.py`

- **Path:** `/app/backend/core/access_guard.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/manifests.py`
- **Imported by:**
  - `/app/backend/core/nxt8_graph.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/approval_gate.py`

- **Path:** `/app/backend/core/approval_gate.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/auth.py`

- **Path:** `/app/backend/core/auth.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_admin_guard.py`
  - `/app/backend/tests/test_auth.py`
  - `/app/backend/tests/test_multi_tenancy.py`
  - `/app/backend_test_tenant_isolation.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/company_context.py`

- **Path:** `/app/backend/core/company_context.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/legacy/personas_legacy.py`
  - `/app/backend/agents/personas.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_company_context.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/complexity_router.py`

- **Path:** `/app/backend/core/complexity_router.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/db.py`

- **Path:** `/app/backend/core/db.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/deepseek.py`

- **Path:** `/app/backend/core/deepseek.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/hermes_memory.py`

- **Path:** `/app/backend/core/hermes_memory.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/legacy/hermes_os_graph_legacy.py`
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/memory_manager.py`

- **Path:** `/app/backend/core/memory_manager.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/memory.py`
  - `/app/backend/agents/mempalace_bridge.py`
- **Imported by:**
  - _(no importers detected)_
- **Used in runtime:** `false`
- **Confidence:** `0.72`
- **Confidence basis:** runtime_path, not_reachable_from_runtime_entrypoints

### `/app/backend/core/migrations/__init__.py`

- **Path:** `/app/backend/core/migrations/__init__.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - _(none resolved)_
- **Imported by:**
  - _(no importers detected)_
- **Used in runtime:** `false`
- **Confidence:** `0.72`
- **Confidence basis:** runtime_path, not_reachable_from_runtime_entrypoints

### `/app/backend/core/migrations/m_tag_memory_with_company_id.py`

- **Path:** `/app/backend/core/migrations/m_tag_memory_with_company_id.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/nxt8_graph.py`

- **Path:** `/app/backend/core/nxt8_graph.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/scheduler.py`

- **Path:** `/app/backend/core/scheduler.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/scheduler_lock.py`

- **Path:** `/app/backend/core/scheduler_lock.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/core/scheduler.py`
  - `/app/backend/tests/test_scheduler_lock.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/share.py`

- **Path:** `/app/backend/core/share.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_share.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/telegram_bot.py`

- **Path:** `/app/backend/core/telegram_bot.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/tour.py`

- **Path:** `/app/backend/core/tour.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_tour.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/core/whatsapp_bot.py`

- **Path:** `/app/backend/core/whatsapp_bot.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/hermes.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/core/db.py`
- **Imported by:**
  - `/app/backend/agents/digest.py`
  - `/app/backend/core/approval_gate.py`
  - `/app/backend/server.py`
  - `/app/backend/tests/test_whatsapp_bot.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/nxt8_langgraph_ultra.py`

- **Path:** `/app/backend/nxt8_langgraph_ultra.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
  - `/app/backend/agents/hermes_max_tools_and_coo.py`
- **Imported by:**
  - `/app/backend/server.py`
  - `/app/backend/tests/test_hermes_ultra.py`
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

### `/app/backend/server.py`

- **Path:** `/app/backend/server.py`
- **Classification:** `runtime`
- **Imports (internal resolved):**
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
- **Used in runtime:** `true`
- **Confidence:** `0.96`
- **Confidence basis:** runtime_path, has_importers, reachable_from_entrypoint

## Non-runtime partitions

- Test files: **69**
- Support scripts: **4**
- Embedded third-party files: **2**

### Tests

- `/app/backend/tests/__init__.py`
- `/app/backend/tests/backend_test.py`
- `/app/backend/tests/conftest.py`
- `/app/backend/tests/quality/__init__.py`
- `/app/backend/tests/quality/test_no_legacy_source_disabled.py`
- `/app/backend/tests/quality/test_no_silent_exceptions.py`
- `/app/backend/tests/test_admin_guard.py`
- `/app/backend/tests/test_agent_prompt_safety_rules.py`
- `/app/backend/tests/test_ai_mentor.py`
- `/app/backend/tests/test_analyst_findings_actions.py`
- `/app/backend/tests/test_analyst_findings_endpoint.py`
- `/app/backend/tests/test_analyst_proactive_prompt.py`
- `/app/backend/tests/test_analyst_self_scan_scheduler.py`
- `/app/backend/tests/test_approval_gate.py`
- `/app/backend/tests/test_auth.py`
- `/app/backend/tests/test_charter.py`
- `/app/backend/tests/test_company_context.py`
- `/app/backend/tests/test_complexity_router.py`
- `/app/backend/tests/test_detect_bottlenecks_sandbox.py`
- `/app/backend/tests/test_fix2_voice_roi_and_stream_tokens.py`
- `/app/backend/tests/test_hermes_evolution.py`
- `/app/backend/tests/test_hermes_self_audit_endpoint.py`
- `/app/backend/tests/test_hermes_tools_audit.py`
- `/app/backend/tests/test_hermes_ultra.py`
- `/app/backend/tests/test_inter_agent.py`
- `/app/backend/tests/test_llm_unavailable.py`
- `/app/backend/tests/test_manifests.py`
- `/app/backend/tests/test_memory_m3_session_limits.py`
- `/app/backend/tests/test_memory_tenant_isolation.py`
- `/app/backend/tests/test_mempalace.py`
- `/app/backend/tests/test_mempalace_tenant_isolation.py`
- `/app/backend/tests/test_multi_tenancy.py`
- `/app/backend/tests/test_onboarding.py`
- `/app/backend/tests/test_p0_unification.py`
- `/app/backend/tests/test_p1_documents_and_hermes_tools.py`
- `/app/backend/tests/test_p2_hermes_migration.py`
- `/app/backend/tests/test_plan_unification.py`
- `/app/backend/tests/test_prompt_policy_registry.py`
- `/app/backend/tests/test_reliability_thresholds.py`
- `/app/backend/tests/test_roi_sanity.py`
- `/app/backend/tests/test_roi_tenant_isolation.py`
- `/app/backend/tests/test_role_boundary_prompts.py`
- `/app/backend/tests/test_scheduler_lock.py`
- `/app/backend/tests/test_share.py`
- `/app/backend/tests/test_share_ssr.py`
- `/app/backend/tests/test_telegram_bot.py`
- `/app/backend/tests/test_tour.py`
- `/app/backend/tests/test_web_search_sanitization.py`
- `/app/backend/tests/test_whatsapp_bot.py`
- `/app/backend_test.py`
- `/app/backend_test_analyst_client_manager.py`
- `/app/backend_test_bookkeeper_marketer_compliance.py`
- `/app/backend_test_complexity_router_edge_cases.py`
- `/app/backend_test_complexity_router_verification.py`
- `/app/backend_test_escalate_depth.py`
- `/app/backend_test_hermes_audit.py`
- `/app/backend_test_hermes_audit_integration.py`
- `/app/backend_test_hermes_self_audit_endpoint.py`
- `/app/backend_test_hermes_self_audit_endpoint_simple.py`
- `/app/backend_test_inter_agent_depth.py`
- `/app/backend_test_nxt8_graph_router_integration.py`
- `/app/backend_test_project_coord.py`
- `/app/backend_test_tenant_isolation.py`
- `/app/test_debug_intent.py`
- `/app/test_debug_router.py`
- `/app/test_debug_sensitivity.py`
- `/app/test_tool_invocation.py`
- `/app/tests/__init__.py`
- `/app/tests/tests/__init__.py`

### Support

- `/app/scripts/add_cookies_legal_keys.py`
- `/app/scripts/merge_translations.py`
- `/app/scripts/translate_i18n.py`
- `/app/verify_audit.py`

### Embedded third-party

- `/app/frontend/node_modules/flatted/python/flatted.py`
- `/app/frontend/node_modules/shell-quote/print.py`
