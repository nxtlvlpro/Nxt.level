#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "Backend-only validation of skill-based migration for analyst and client_manager personas to nxt8_graph in NXT8"

backend:
  - task: "Analyst persona routing to nxt8_graph"
    implemented: true
    working: true
    file: "backend/agents/personas.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ /api/personas/analyst/chat correctly routes to nxt8_graph (not legacy). SKILL_ROUTED_PERSONAS contains 'analyst'. Response contract intact with all required fields (success, provider='nxt8_graph', persona_id, content, session_id, iterations, confidence, tool_traces). Verified via comprehensive backend test."

  - task: "Client_manager persona routing to nxt8_graph"
    implemented: true
    working: true
    file: "backend/agents/personas.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ /api/personas/client_manager/chat correctly routes to nxt8_graph (not legacy). SKILL_ROUTED_PERSONAS contains 'client_manager'. Response contract intact with all required fields (success, provider='nxt8_graph', persona_id, content, session_id, iterations, confidence, tool_traces). Verified via comprehensive backend test."

  - task: "Analyst tool loop (evaluate_action_roi)"
    implemented: true
    working: true
    file: "backend/skills/analyst.md, backend/core/nxt8_graph.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ Analyst skill file has 'evaluate_action_roi' in allowed_tools. Tool loop works correctly - when prompted to evaluate ROI, analyst invokes evaluate_action_roi tool and receives result. Verified in backend logs and audit records. Tool execution: args={'action': 'Запустить reactivation-кампанию по dormant B2B лидам'}, result ok=True."

  - task: "Client_manager tool loop (create_task)"
    implemented: true
    working: true
    file: "backend/skills/client_manager.md, backend/core/nxt8_graph.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ Client_manager skill file has 'create_task' in allowed_tools. Tool loop works correctly - when prompted to create follow-up task, client_manager invokes create_task tool and task is created. Verified in backend logs and audit records. Tool execution: args={'title': 'Follow-up: резюме звонка и слот на завтра — ACME', ...}, result ok=True."

  - task: "Audit records with provider='nxt8_graph'"
    implemented: true
    working: true
    file: "backend/agents/personas.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ persona_requests collection correctly stores provider='nxt8_graph' for both analyst and client_manager. Verified 5 recent analyst records and 4 recent client_manager records all have provider='nxt8_graph'. Older records (pre-migration) correctly show provider='deepseek_direct'. Tool traces are properly stored in audit records."

  - task: "Plan-gate for analyst (headquarters only)"
    implemented: true
    working: true
    file: "backend/agents/legacy/personas_legacy.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ Analyst is only available on 'headquarters' plan. Test with 'team' plan returns success=False with error 'persona analyst недоступна на тарифе team'. Test with 'headquarters' plan returns success=True with provider='nxt8_graph'. Plan-gate correctly preserved."

  - task: "Plan-gate for client_manager (team+)"
    implemented: true
    working: true
    file: "backend/agents/legacy/personas_legacy.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ Client_manager is available on 'team' plan and above. Test with 'personal' plan returns success=False with error 'persona client_manager недоступна на тарифе personal'. Test with 'team' plan returns success=True with provider='nxt8_graph'. Plan-gate correctly preserved."

  - task: "Other personas not affected by migration"
    implemented: true
    working: true
    file: "backend/agents/personas.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ Other personas (bookkeeper, marketer) still use legacy path. Tested bookkeeper and marketer - both return success=True with provider='deepseek_direct' (not 'nxt8_graph'). Only hr_mentor, analyst, and client_manager are in SKILL_ROUTED_PERSONAS set. Migration is selective and does not affect other personas."

  - task: "Skill files validation"
    implemented: true
    working: true
    file: "backend/skills/analyst.md, backend/skills/client_manager.md"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ Both skill files exist and are valid. analyst.md: id='analyst', allowed_tools includes 'evaluate_action_roi'. client_manager.md: id='client_manager', allowed_tools includes 'create_task'. YAML frontmatter is correctly formatted and parseable. Skill files are loaded by nxt8_graph.py load_skill() function."

frontend:
  - task: "Frontend testing not required"
    implemented: false
    working: "NA"
    file: "N/A"
    stuck_count: 0
    priority: "low"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "testing"
        comment: "Frontend testing not required for this backend-only persona migration. Changes are isolated to backend routing logic and skill files."

metadata:
  created_by: "testing_agent"
  version: "1.1"
  test_sequence: 3
  run_ui: false

test_plan:
  current_focus:
    - "Backend-only validation of analyst and client_manager migration to nxt8_graph"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "testing"
    message: "Completed comprehensive backend validation of analyst and client_manager migration to nxt8_graph. All 9 backend tasks verified and working correctly. Created comprehensive test suite in /app/backend_test_analyst_client_manager.py covering: routing verification, response contract validation, tool loop execution (evaluate_action_roi for analyst, create_task for client_manager), audit record verification, plan-gate enforcement, and non-regression of other personas. All tests passed. Backend logs confirm tool invocations working correctly. Database audit records show provider='nxt8_graph' for both personas. No issues found."
