# Technology Stack

## Core Technologies

- **Python**: 3.8+ (supports 3.8-3.14+)
- **Build System**: setuptools with pyproject.toml configuration
- **Package Management**: pip with requirements.txt files
- **Virtual Environment**: `./venv` (required for development)

## Key Dependencies

### Development
- **pytest**: >=7.0.0 - Testing framework with coverage reporting
- **black**: >=22.0.0 - Code formatting (line-length: 88)
- **flake8**: >=5.0.0 - Linting and style checking
- **mypy**: >=1.0.0 - Static type checking

## Common Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

### Development Workflow
```bash
# Run tests with coverage
pytest
# or: make test

# Format code
black src/ tests/ scripts/
# or: make format

# Lint code
flake8 src/ tests/ scripts/
# or: make lint

# Type checking
mypy src/
# or: make type-check

# Clean cache files
make clean
```

### Build System
- Uses modern pyproject.toml configuration
- Editable installation with `pip install -e .`
- Automatic package discovery in src/ layout