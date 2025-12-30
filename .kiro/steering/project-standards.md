---
inclusion: always
---

# Python Project Standards

## Python Environment Requirements
- **Python Version**: Use Python 3.8+ 
- **Virtual Environment**: Always use `./venv` for the virtual environment
- **Activation**: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
- **Dependencies**: Install with `pip install -r requirements.txt` and `pip install -r requirements-dev.txt`

## Project Structure Standards

### Module Organization
All main code should be organized in a `src/` package structure with separate modules for each type of action:

- **`parsers/`** - File format parsers (QFX, CSV, PDF, etc.)
- **`analyzers/`** - Data analysis and processing logic
- **`exporters/`** - Data export functionality
- **`models/`** - Data structures, classes, and domain objects
- **`utils/`** - Utility functions and helper modules

Each module must include an `__init__.py` file for proper Python package structure.

### Testing Structure
- **Location**: All tests must be located in the `tests/` folder
- **Naming Convention**: Test files should follow the `test_*.py` pattern
- **Structure**: Mirror the source code structure in tests (e.g., `tests/parsers/test_qfx_parser.py`)
- **Coverage**: Write comprehensive tests for all functionality

### Scripts Organization
All one-time usage scripts should be located in the `scripts/` folder with each type of script in its own subfolder:

- **`scripts/import/`** - Data import and ingestion scripts
- **`scripts/export/`** - Data export and reporting scripts  
- **`scripts/analysis/`** - One-time analysis and research scripts
- **`scripts/migration/`** - Database migration and data transformation scripts
- **`scripts/setup/`** - Setup, configuration, and initialization scripts

Each subfolder should contain a `README.md` file explaining its purpose and usage.

## Development Workflow
1. Always activate the virtual environment before development work
2. Install the package in development mode: `pip install -e .`
3. Run tests before committing changes: `pytest`
4. Use consistent code formatting: `black src/ tests/ scripts/`
5. Perform type checking: `mypy src/`

## Code Organization Principles
- Keep modules focused on single responsibilities
- Use clear, descriptive names for functions, classes, and variables
- Follow snake_case naming convention for Python files and modules
- Add comprehensive docstrings to all public functions and classes
- Import from appropriate module levels to maintain clean dependencies
- Group related functionality within the same module