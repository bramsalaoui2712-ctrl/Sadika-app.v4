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

## user_problem_statement: "Je veux une application pour pouvoir parler a mon IA , sur mon téléphone, je veux qu'elle soit intuitive style chatgptt"

## backend:
  - task: "SSE chat streaming endpoint (/api/chat/stream)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 1
    priority: "high"
    needs_retesting: false
    status_history:
      - working: false
        agent: "main"
        comment: "Initial SSE with mock + LLM integration created."
      - working: true
        agent: "main"
        comment: "Provider normalization added (openai/gpt-4o-mini default). Dropped unsupported params for O-series. Expect real content streaming."
      - working: true
        agent: "testing"
        comment: "✅ KERNEL INTEGRATION TESTED: GET /api/chat/stream with provider=kernel&model=local&q=Bonjour&sessionId=test123&mode=public&council=2&truth=1 returns proper SSE sequence (session->content->complete). Kernel traits verified: French text handling, local processing. Regression test passed: OpenAI provider still works with gpt-4o-mini."
  - task: "Chat history endpoint (/api/chat/history)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: false
        agent: "main"
        comment: "Returns messages for a given sessionId after chat."
      - working: true
        agent: "main"
        comment: "Verified persistence logic; needs automated test to confirm."
      - working: true
        agent: "testing"
        comment: "✅ PERSISTENCE VERIFIED: GET /api/chat/history?sessionId=test123 returns 2 messages (user+assistant) after kernel chat stream. History properly persisted in MongoDB."
  - task: "Kernel memory management (/api/kernel/memory)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ KERNEL MEMORY TESTED: GET /api/kernel/memory returns {ok:true, memory:{...}}. POST /api/kernel/memory/approve with {key:'contrainte', value:'local-first; concision'} successfully sets memory and verification confirms key is stored."
  - task: "Kernel feedback endpoint (/api/kernel/feedback)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ FEEDBACK TESTED: POST /api/kernel/feedback with {label:'approve'} returns {ok:true}. Endpoint properly validates label and processes feedback."
  - task: "Kernel mutation endpoint (/api/kernel/mutate)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "testing"
        comment: "✅ MUTATION TESTED: POST /api/kernel/mutate with {trials:3} returns {ok:true, result:{ok:true, baseline:2.45, adopted:false, new_score:2.45}}. Mutation logic working with proper result structure including adopted boolean."

## frontend:
  - task: "Mock-only chat UI with mic+TTS"
    implemented: true
    working: true
    file: "/app/frontend/src/pages/Chat.jsx"
    stuck_count: 1
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "UI created with streaming mock; tested visually. Integration to backend pending."

## metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 1
  run_ui: false

## test_plan:
  current_focus:
    - "All kernel integration tests completed successfully"
  stuck_tasks:
    - 
  test_all: false
  test_priority: "high_first"

## agent_communication:
  - agent: "main"
    message: "Please test backend SSE streaming and history. The SSE stream should emit a 'session' event first, then multiple 'content' chunks, and 'complete'. Use session_id to call /api/chat/history. Note: real LLM may fallback to mock if upstream unavailable; this is expected."
  - agent: "testing"
    message: "✅ ALL KERNEL INTEGRATION TESTS PASSED: 1) Kernel chat stream with French input works perfectly - proper SSE sequence, French text handling, local processing. 2) Chat history persistence verified - user+assistant messages stored correctly. 3) Kernel memory GET/POST operations working. 4) Kernel feedback endpoint functional. 5) Kernel mutation endpoint returns proper result with adopted boolean. 6) OpenAI provider regression test passed - no breaking changes. Backend is fully functional with kernel integration. All routes properly prefixed with /api and backend running on 0.0.0.0:8001 as expected."