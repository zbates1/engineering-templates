# Shared Work

This file coordinates the collaborative work of all AI agents on the project.

## 1. Goal

*A clear, one-sentence statement of the desired outcome.*

**Example:**
> Build a financial analysis system with user authentication, data processing, and report generation capabilities.

---

## 2. To-Do List

*A sequence of tasks to achieve the goal. Agents must claim a task before working on it.*

**Task Statuses:**
- `- [ ] T###: Task Name` (Available)
- `- [WIP:AgentName] T###: Task Name` (Work in Progress - **CLAIMED** - Use actual names: Kyle, Isaac, Greta, etc.)
- `- [x] T###: Task Name` (Completed)

**Task ID Format:** T001-T999 (sequential)

**Example List with Architecture-Aware Tasks:**
- [ ] T001: Create models/user.py:User with properties (id, username, email) and methods (validate(), to_dict()) with tests
- [ ] T002: Create services/auth_service.py:AuthService implementing login(credentials) → User interface with full test coverage
- [ ] T003: Create controllers/user_controller.py handling requests → auth_service → user model flow with integration tests
- [ ] T004: Create services/data_processor.py:DataProcessor implementing process(DataFrame) → ProcessedData with unit/integration tests
- [ ] T005: Create utils/validator.py with validate_data(DataFrame) → ValidationResult used by DataProcessor with tests
- [ ] T006: Implement data export pipeline with complete test coverage for all components
- [ ] T007: Create authentication middleware with tests verifying token validation across components

---

## 3. Action Log

*A record of all actions taken by agents. Each agent must log its action and define the next one.*

**Log Format:**
`[Agent_Name | YYYY-MM-DD HH:MM] Action: [Description of action taken]. Next: [Next task from the list].`

**Agent Names:** Use your actual agent name (Kyle, Isaac, Greta, etc.) not generic "Agent" or "Code"

**Logging Rules - KEEP IT BRIEF:**
- Maximum 15 words per action description
- State WHAT was done, not HOW
- Use format: "Created/Updated/Fixed [file]: [key change]"
- Include task ID in "Next" field (e.g., "Next: T002")
- Omit obvious details (e.g., "per spec", "as required")
- NO filler words or explanations

**✅ GOOD Examples (Brief & Clear / Name included):**
`[Manager Agent | 2025-07-18 09:00] Action: Created architecture.md. Next: Generate tasks.`
`[Kyle | 2025-07-18 10:00] Action: Created models/user.py with tests. All pass. Next: T002.`
`[Isaac | 2025-07-18 10:30] Action: Created auth_service.py: login interface, 5 tests pass. Next: T003.`
`[Greta | 2025-07-18 11:00] Action: Fixed validation bug, tests now pass. Next: T004.`

**❌ BAD Examples (Too Verbose / No name):**
`[Code Agent | TIME] Action: Successfully implemented the authentication service with all required methods including login, logout, and token validation according to the architecture specification. Next: Move on to controller.`
`[Test Agent | TIME] Action: Created comprehensive test suite with 15 unit tests and 8 integration tests covering all edge cases and ensuring 100% code coverage. Next: Run tests.`
`[Code | TIME] Action: ...` 
`[Agent | TIME] Action: ...`