# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

[make sure your goal is here]

## Architecture & Integration

**CRITICAL: Architecture Enforcement**
The `architecture.md` file is the single source of truth for system structure. You MUST:
1. Read `architecture.md` BEFORE writing any code
2. Place ALL files according to the defined directory structure
3. Implement interfaces EXACTLY as specified
4. Follow the component interaction map for ALL dependencies
5. Verify data flow matches the architecture diagram

**Violations of architecture.md are NOT acceptable:**
- ❌ Creating files outside the defined structure
- ❌ Implementing different interfaces than specified
- ❌ Bypassing defined component interactions
- ❌ Adding dependencies not in the component map

**Component Integration:**
When creating new code:
- Place files according to the directory structure in `architecture.md`
- Implement interfaces exactly as specified in the architecture
- Import dependencies as shown in the component map
- Ensure your code integrates with existing components per the data flow diagram

**Task Interpretation:**
Tasks in `shared_work.md` often specify interactions (e.g., "UserService → User model"). You must:
- Identify all components mentioned in the task
- Read existing implementations of these components
- Ensure proper imports and interface compatibility
- Write integration tests that verify the complete interaction chain

## Agent Workflow & Collaboration

**Search-First Strategy:**
To minimize context usage, ALWAYS search before reading:
1. Use `grep` to find specific patterns in files
2. Use `glob` to locate files by name pattern
3. Only read full files when necessary for implementation
4. Cache file contents after first read - don't re-read static files

Example workflow:
```bash
# GOOD: Search first
grep "class User" src/**/*.py  # Find User class location
grep "[ ]" shared_work.md       # Find available tasks
# Then read only the specific files needed

# BAD: Read everything
# Reading all files without searching first
```

**Task Synchronization & Planning:**
Before starting any work, you must:
1. Read `product_requirements.md` to understand project goals
2. Read `architecture.md` to understand system structure  
3. Check `shared_work.md` for current tasks (ALWAYS read fresh - never cache this file)
4. When creating tasks, specify component interactions (e.g., "Create PaymentService that uses OrderModel and returns Receipt")
5. Ensure tasks reference specific files/modules from `architecture.md`

**Manager Agent Responsibilities:**
When acting as Manager Agent and creating `shared_work.md`:
1. Create `architecture.md` BEFORE generating tasks
2. Generate tasks that explicitly reference architecture components
3. Include integration points in task descriptions
4. Specify which interfaces each task should implement

**Task Format Requirements:**
Tasks must specify:
- Target file location (from `architecture.md`)
- Components it interacts with
- Interfaces it implements/uses
- Integration tests required

Example:
❌ Bad: "Create user authentication"
✅ Good: "Create services/auth.py:AuthService implementing login(credentials) → User, using models/user.py:User"

**Task Continuity:**
You are expected to operate in a continuous loop. After completing a task, you must proactively identify and begin the next task based on the project's needs. Review the instructions and requirements outlined in the other `.md` files within this repository (e.g., `product_requirements.md`, `test_agent.md`) to determine the next logical step. Continue this process until you are explicitly told to stop.

**Collision Avoidance:**
Before starting any new task, you **must** check the `shared_work.md` file. This file acts as a central log to prevent multiple agents from working on the same task simultaneously. Verify that the task you are about to start is not already claimed or in progress by another agent.

**Handling Scope Changes:**
If you detect a scope change initiated by the user (as defined in `change_management_protocol.md`), your highest priority is to pause all other work. You must follow the protocol to re-evaluate the project requirements and update the `shared_work.md` to-do list before resuming any development tasks.

**Code Development & Testing:**
The Code Agent is responsible for BOTH implementation AND testing. Each task must include:
- Implementation of the component/feature
- Unit tests for individual components in isolation  
- Integration tests for interactions between components as specified in `architecture.md`
- Data flow tests to verify data transforms correctly through the component chain
- Test file placement: `tests/unit/[component]/` and `tests/integration/`
- ALL tests must pass before marking a task complete
- Never skip integration tests when a task mentions multiple components
- You should **NEVER** create synthetic test data for the purposes of passing a test. All tests should be run on real data that has been chosen for testing purposes.

**No separate Test Agent:** Testing is integrated into the Code Agent workflow to reduce context and improve efficiency.


## Data Structure

### File Organization
- Main python files organized within the `src/` folder (or as specified in `architecture.md`)
- Tests organized in the `tests/` folder with `unit/` and `integration/` subdirectories
- Results saved to `exports/` and `figures/` subdirectories


### Directory Structure
- Follow the structure defined in `architecture.md`
- `src/`: Core application code
  - `models/`: Data models and schemas
  - `services/`: Business logic
  - `controllers/`: Request handlers
  - `utils/`: Shared utilities
- `tests/`: All test files
  - `unit/`: Component-level tests
  - `integration/`: Cross-component tests
- `data/`: Data files
- `config/`: Configuration files