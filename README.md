# Kiro Budget

Personal Finance Management Tool for analyzing financial data from various sources.

## Setup

1. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
# For development:
pip install -r requirements-dev.txt
```

3. Install the package in development mode:
```bash
pip install -e .
```

## Project Structure

```
kiro-budget/
├── src/kiro_budget/          # Main package
│   ├── parsers/              # File format parsers (QFX, CSV, PDF)
│   ├── analyzers/            # Data analysis modules
│   ├── exporters/            # Export functionality
│   ├── models/               # Data models
│   └── utils/                # Utility functions
├── tests/                    # Test files
├── scripts/                  # One-time usage scripts
│   ├── import/               # Data import scripts
│   ├── export/               # Data export scripts
│   ├── migration/            # Migration scripts
│   └── analysis/             # Analysis scripts
├── raw/                      # Raw financial data (gitignored)
└── data/                     # Processed data (gitignored)
```

## Usage

The `raw/` folder contains your private financial data and is protected by `.gitignore`.
The `data/` folder is for processed/cleaned data and is also gitignored.

## Development

Run tests:
```bash
pytest
```

Format code:
```bash
black src/ tests/
```

Type checking:
```bash
mypy src/
```