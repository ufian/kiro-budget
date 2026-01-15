# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kiro Budget is a Python-based personal finance management tool that parses financial data from multiple sources (QFX/OFX, PDF statements, CSV), consolidates transactions with deduplication, and generates financial reports.

## Build and Development Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .

# Run tests
pytest                                      # All tests with coverage
pytest tests/test_qfx_parser.py            # Single test file
pytest tests/test_qfx_parser.py::TestQfxParser::test_parse_basic  # Single test

# Code quality
black src/ tests/ scripts/                  # Format code (line-length: 88)
flake8 src/ tests/ scripts/                 # Lint
mypy src/                                   # Type checking

# Makefile shortcuts
make test       # Run tests
make format     # Format code
make lint       # Run linter
make type-check # Type checking
make clean      # Remove cache files
```

## CLI Commands

The main interface is `python -m kiro_budget.cli <command>`:

```bash
# Core workflow (run in sequence for full report)
python -m kiro_budget.cli process           # Process raw files → CSV
python -m kiro_budget.cli import            # Consolidate CSVs with dedup
python -m kiro_budget.cli categorize        # Add categories to transactions

# Configuration
python -m kiro_budget.cli generate-accounts-template  # Create accounts.yaml template
python -m kiro_budget.cli init-categories            # Create categories.yaml

# Reports
python scripts/analysis/monthly_summary_report.py       # Basic monthly report
python scripts/analysis/monthly_category_report.py      # Category breakdown report

# Full pipeline automation
./scripts/generate_deep_monthly_report.sh               # Process → Import → Report
./scripts/generate_deep_monthly_report.sh --force       # Force reprocess all files
```

## Architecture

### Core Pipeline

1. **Parsers** (`src/kiro_budget/parsers/`) - Convert raw files to Transaction objects
   - `qfx_parser.py` - QFX/OFX bank exports
   - `pdf_parser.py` - PDF bank statements (table extraction)
   - `csv_parser.py` - CSV files with auto-detection
   - `base.py` - `FileParser` abstract base class

2. **Utils** (`src/kiro_budget/utils/`)
   - `account_config.py` / `account_enricher.py` - Load and apply account metadata from `raw/accounts.yaml`
   - `duplicate_detector.py` - Cross-file deduplication (fuzzy matching with date tolerance)
   - `importer.py` - `TransactionImporter` consolidates all CSVs into `data/total/all_transactions.csv`
   - `csv_writer.py` - Standardized CSV output
   - `sign_detector.py` - Automatic sign detection (banking vs credit card convention)

3. **Categorizers** (`src/kiro_budget/categorizers/`) - Transaction categorization subsystem
   - `category_engine.py` - Main orchestrator
   - `pattern_matcher.py` - Rule-based matching (substring, regex, exact)
   - `ml_categorizer.py` - ML model for learning from user feedback
   - `ai_categorizer.py` - External AI service integration (OpenAI, Claude)

4. **Models** (`src/kiro_budget/models/core.py`)
   - `Transaction` - Base transaction dataclass
   - `EnrichedTransaction` - Transaction with account name/type
   - `ProcessingResult` - File processing outcome

### Data Flow

```
raw/{institution}/*.{pdf,qfx,csv}
    ↓ [process command - parsers + sign detection]
data/{institution}/*.csv (per-file, enriched)
    ↓ [import command or build_total_csv.py - deduplication]
data/total/all_transactions.csv (consolidated)
    ↓ [categorize command or add_categories_to_csv.py]
data/total/all_transactions.csv (with categories)
    ↓ [monthly_summary_report.py]
data/reports/monthly_summary.html
```

### Key Configuration Files

- `raw/accounts.yaml` - Map account IDs to human-readable names and types (credit/debit)
- `categories.yaml` - Category definitions and matching patterns
- `parser_config.json` - Optional parser settings

## Project Structure Standards

From `.kiro/steering/project-standards.md`:

- **Source code**: `src/kiro_budget/` with submodules: `parsers/`, `models/`, `utils/`, `categorizers/`
- **Tests**: `tests/` mirroring source structure, files named `test_*.py`
- **Scripts**: `scripts/` with subfolders: `import/`, `export/`, `analysis/`, `debug/`, `migration/`, `setup/`
- Each module must include `__init__.py`

## Testing

Tests are in `tests/` and follow `test_*.py` naming. Pytest is configured in `pyproject.toml`:
- Test path: `tests/`
- Coverage enabled for `src/kiro_budget`
- Categorizer tests are in `tests/categorizers/` subdirectory

## Important Patterns

### Adding a New Parser
Inherit from `FileParser` in `parsers/base.py`:
```python
class MyParser(FileParser):
    def parse(self, file_path: str) -> List[Transaction]: ...
    def get_supported_extensions(self) -> List[str]: ...
    def validate_file(self, file_path: str) -> bool: ...
```

### Transaction Sign Convention
- Negative amounts = money out (expenses)
- Positive amounts = money in (income/credits)
- `account_type: credit` vs `debit` affects report calculations
- Automatic sign detection handles banking vs credit card conventions

### Duplicate Detection
- Transaction IDs take priority for QFX files
- Fuzzy matching with 3-day date tolerance for PDF vs QFX cross-source duplicates
- Prefers QFX data over PDF data when duplicates are found

### Category Configuration (categories.yaml)
```yaml
Category_Name:
  patterns:
  - pattern: MERCHANT_NAME
    confidence: 0.95
    type: substring      # substring, regex, or exact
    specificity: high    # very_high, high, medium, low
```

## Feature Specifications

Detailed specs are in `.kiro/specs/`:
- `financial-data-parser/` - Core parsing requirements
- `account-configuration/` - Account enrichment system
- `transaction-import/` - Consolidation and deduplication
- `transaction-categorization/` - Categorization subsystem
