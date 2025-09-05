# Project Architecture

This file defines the system structure, component interactions, and data flow for the project.

## Directory Structure

```
project/
├── src/
│   ├── models/          # Data models and schemas
│   ├── services/        # Business logic and processing
│   ├── controllers/     # Request handlers and orchestration
│   ├── utils/           # Shared utilities and helpers
│   └── main.py          # Application entry point
├── tests/
│   ├── unit/            # Unit tests for individual components
│   └── integration/     # Integration tests for component interactions
├── data/
│   ├── input/           # Input data files
│   └── output/          # Generated output files
└── config/              # Configuration files
```

## Component Map

*Define how components interact with each other. Use arrows to show data flow.*

**Example:**
- `controllers/user_controller.py` → `services/auth_service.py` → `models/user.py`
- `controllers/data_controller.py` → `services/processor.py` → `utils/validator.py` → `models/data.py`
- `main.py` → `controllers/*` → `services/*` → `models/*`

## Interface Definitions

*Specify the public interfaces that components must implement.*

### Service Interfaces

**AuthService**
- `login(credentials: dict) -> User`: Authenticate user and return User object
- `logout(user_id: str) -> bool`: Terminate user session
- `validate_token(token: str) -> bool`: Check if token is valid

**DataProcessor**
- `process(data: DataFrame) -> ProcessedData`: Transform raw data
- `validate(data: DataFrame) -> ValidationResult`: Check data integrity
- `export(data: ProcessedData, format: str) -> str`: Export to specified format

### Model Interfaces

**User**
- Properties: `id`, `username`, `email`, `created_at`
- Methods: `to_dict()`, `from_dict(data)`, `validate()`

**Data**
- Properties: `id`, `content`, `metadata`, `timestamp`
- Methods: `transform()`, `serialize()`, `validate()`

## Data Flow

*Describe how data moves through the system.*

1. **Input Stage**
   - Entry point receives request/data
   - Controller validates and routes

2. **Processing Stage**
   - Service layer applies business logic
   - Models ensure data integrity
   - Utils provide support functions

3. **Output Stage**
   - Results formatted for response
   - Data persisted if needed
   - Response returned to caller

## Integration Points

*Critical points where components must interact correctly.*

- **Authentication Flow**: All controllers must validate auth tokens via AuthService
- **Data Pipeline**: Raw data → Validation → Processing → Export
- **Error Handling**: All services must return standardized error responses
- **Logging**: All components must use central logging utility

## Testing Requirements

- **Unit Tests**: Each component tested in isolation
- **Integration Tests**: Test complete flows (e.g., login → process → export)
- **Data Tests**: Validate transformations with real sample data
- **Error Tests**: Verify error handling across component boundaries