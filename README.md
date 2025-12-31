# Kiro Budget

A comprehensive financial data parser and analysis tool that processes multiple file formats (QFX, PDF, CSV) from various financial institutions, automatically detects and removes duplicate transactions, enriches transactions with account metadata, and provides detailed financial reporting.

## Features

- **Multi-Format Support**: Parse QFX/OFX, PDF statements, and CSV files
- **Account Enrichment**: Automatically enriches transactions with account names and types (credit/debit) based on configuration
- **Intelligent Duplicate Detection**: Automatically identifies and merges duplicate transactions across different file formats while preserving enrichment data
- **Institution Support**: Built-in support for Chase, First Tech, Gemini, Apple Card, Revolut, Discover, and other major financial institutions
- **Transaction Import & Consolidation**: Consolidates all processed transactions into a unified dataset with deduplication
- **Monthly Reporting**: Generates detailed HTML reports with spending analysis, proper credit/debit handling, and year-over-year grouping
- **Plugin System**: Extensible architecture for adding custom parsers and processors
- **Data Validation**: Comprehensive validation and error handling
- **Batch Processing**: Process multiple files simultaneously with progress tracking
- **Standardized Output**: Unified CSV format with consistent field mapping and account metadata

## Quick Start

### 1. Setup Environment

```bash
# Clone and navigate to the project
git clone <repository-url>
cd kiro-budget

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install the package in development mode
pip install -e .
```

### 2. Configure Accounts

Create an account configuration file at `raw/accounts.yaml` to define your account names and types:

```yaml
# Account Configuration
chase:
  "8147":
    account_name: "Chase Sapphire"
    account_type: credit

firsttech:
  "0547":
    account_name: "Main Checking"
    account_type: debit

gemini:
  "unknown":
    account_name: "Gemini Trading"
    account_type: credit
```

This configuration ensures transactions are properly categorized as credit or debit accounts, which is essential for accurate financial reporting.

### 3. Prepare Your Data

Place your financial data files in the `raw/` directory organized by institution:

```
raw/
├── chase/
│   ├── statement_2024_01.pdf
│   ├── activity_2024_01.qfx
│   └── transactions.csv
├── firsttech/
│   └── account_data.qfx
└── gemini/
    └── trading_history.csv
```

### 4. Process Your Data

```bash
# Process all files in the raw directory
python -m kiro_budget.cli process

# Process specific directory
python -m kiro_budget.cli process -d raw/chase

# Process specific files
python -m kiro_budget.cli process -f raw/chase/statement.pdf raw/chase/activity.qfx

# Force reprocessing (ignore previous processing history)
python -m kiro_budget.cli process --force

# Generate processing report
python -m kiro_budget.cli process -r processing_report.json
```

### 5. Import and Consolidate Transactions

After processing individual files, consolidate all transactions into a unified dataset:

```bash
# Import and deduplicate all processed transactions
python -m kiro_budget.cli import
```

This creates `data/total/all_transactions.csv` with all transactions deduplicated and enriched with account metadata.

### 6. Generate Reports

Create detailed financial reports:

```bash
# Generate monthly summary report
python scripts/analysis/monthly_summary_report.py
```

This creates an HTML report at `data/reports/monthly_summary.html` with:
- Monthly spending and income breakdown
- Proper credit/debit account handling
- Year-over-year grouping
- Color-coded spending (red) vs income (green)

## Usage Guide

### Command Line Interface

The main interface is through the CLI module:

```bash
python -m kiro_budget.cli <command> [options]
```

#### Available Commands

**`process`** - Process financial data files

Options:
- `-f, --files TEXT`: Specific files to process
- `-d, --directories TEXT`: Directories to process  
- `--force`: Force reprocessing of previously processed files
- `--no-recursive`: Disable recursive directory scanning
- `-r, --report TEXT`: Save processing report to specified file

**`import`** - Import and consolidate all processed transactions

This command:
- Scans all processed CSV files in `data/` subdirectories
- Deduplicates transactions across files using fuzzy matching
- Preserves account enrichment data (account names and types)
- Creates consolidated output at `data/total/all_transactions.csv`

#### Examples

```bash
# Process all files in raw directory
python -m kiro_budget.cli process

# Process only Chase files
python -m kiro_budget.cli process -d raw/chase

# Process specific files with report
python -m kiro_budget.cli process -f raw/chase/statement.pdf -r report.json

# Force reprocess all files (ignore processing history)
python -m kiro_budget.cli process --force

# Process without recursing into subdirectories
python -m kiro_budget.cli process --no-recursive
```

### Supported File Formats

#### QFX/OFX Files
- **Extensions**: `.qfx`, `.ofx`
- **Sources**: Bank downloads, Quicken exports
- **Features**: Full transaction details with IDs, automatic duplicate detection
- **Example**: Chase activity downloads, bank statement exports

#### PDF Statements  
- **Extensions**: `.pdf`
- **Sources**: Bank statements, credit card statements
- **Features**: Text extraction, table parsing, transaction identification
- **Example**: Monthly statements from Chase, Bank of America

#### CSV Files
- **Extensions**: `.csv`
- **Sources**: Manual exports, trading platforms
- **Features**: Flexible column mapping, automatic format detection
- **Example**: Gemini trading history, manual transaction logs

### Output Format

All processed transactions are output in a standardized CSV format:

```csv
date,amount,description,account,account_name,account_type,institution,transaction_id,category,balance
2024-01-15,-52.20,AMAZON MKTPL*ABC123,8147,Chase Sapphire,credit,Chase,20240115123456789,,
2024-01-16,1500.00,PAYROLL DEPOSIT,0547,Main Checking,debit,Firsttech,20240116987654321,,
```

**Fields:**
- `date`: Transaction date (YYYY-MM-DD)
- `amount`: Transaction amount (negative for debits, positive for credits)
- `description`: Transaction description/merchant name
- `account`: Account identifier (last 4 digits or account code)
- `account_name`: Human-readable account name from configuration
- `account_type`: Account type (`credit` or `debit`) from configuration
- `institution`: Financial institution name
- `transaction_id`: Unique transaction ID (when available)
- `category`: Transaction category (optional)
- `balance`: Account balance after transaction (when available)

### Account Configuration

Configure your accounts in `raw/accounts.yaml` to enable proper transaction enrichment:

```yaml
# Account Configuration File
# institution_name:
#   "account_id":
#     account_name: "Display Name"
#     account_type: credit|debit

chase:
  "8147":
    account_name: "Chase Sapphire"
    account_type: credit

firsttech:
  "0547":
    account_name: "Main Checking"
    account_type: debit
  "0596":
    account_name: "Savings"
    account_type: debit

gemini:
  "unknown":  # Gemini CSV files don't include account IDs
    account_name: "Gemini Trading"
    account_type: credit

apple:
  "75e0e545-fb91-45d4-836":
    account_name: "Apple Card"
    account_type: credit
```

**Important Notes:**
- `account_type: credit` for credit cards, loans, and trading accounts
- `account_type: debit` for checking, savings, and cash accounts
- Account IDs should match what appears in your transaction files
- Some institutions (like Gemini) use "unknown" as the account ID

### Duplicate Detection

The tool automatically detects and removes duplicate transactions while preserving account enrichment data using:

- **Transaction IDs**: Exact matching for QFX/OFX files
- **Fuzzy Matching**: Amount + description + date tolerance for cross-format detection
- **Date Tolerance**: 3-day window to handle posting vs transaction date differences
- **Description Normalization**: Handles merchant name variations and location differences
- **Enrichment Preservation**: Maintains account names and types through the deduplication process

### Configuration

#### Custom Configuration

Create a `config.json` file to customize behavior:

```json
{
  "raw_directory": "raw",
  "data_directory": "data", 
  "date_formats": ["%Y-%m-%d", "%m/%d/%Y"],
  "institution_mappings": {
    "chase": "Chase Bank",
    "bofa": "Bank of America"
  }
}
```

See `docs/accounts_configuration.md` for detailed account configuration documentation.

#### Plugin System

Extend functionality with custom plugins:

```python
# plugins/custom_parser.py
from kiro_budget.parsers.base import BaseParser

class CustomBankParser(BaseParser):
    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.custom')
    
    def parse(self, file_path: str) -> List[Transaction]:
        # Custom parsing logic
        pass
```

### Data Organization

#### Input Structure
```
raw/
├── chase/           # Chase bank files
├── firsttech/       # First Tech Credit Union files  
├── gemini/          # Gemini exchange files
└── other/           # Other institution files
```

#### Output Structure
```
data/
├── chase/
│   └── chase_8147_20240101_20240131.csv
├── firsttech/
│   └── firsttech_0547_20240101_20240131.csv
├── total/
│   └── all_transactions.csv              # Consolidated transactions
└── reports/
    ├── monthly_summary.html              # Monthly spending report
    └── processing_report_20240201.json   # Processing statistics
```

## Advanced Usage

### Transaction Import and Consolidation

Import and consolidate all processed transactions:

```bash
# Import all processed CSV files into consolidated dataset
python -m kiro_budget.cli import
```

This command:
- Scans all institution directories in `data/` for CSV files
- Loads and validates transaction data
- Performs cross-file duplicate detection using fuzzy matching
- Preserves account enrichment data through deduplication
- Outputs consolidated file to `data/total/all_transactions.csv`

### Financial Reporting

Generate comprehensive financial reports:

```bash
# Generate monthly summary HTML report
python scripts/analysis/monthly_summary_report.py
```

The monthly report includes:
- **Monthly Breakdown**: Income vs spending by month
- **Account Type Handling**: Proper credit/debit account classification
- **Year Grouping**: Transactions grouped by year with subtotals
- **Color Coding**: Red for spending, green for income/credits
- **Sign Convention**: Negative amounts = money out, positive = money in

### Batch Processing

Process multiple institutions simultaneously:

```bash
# Process all institutions
python -m kiro_budget.cli process

# Process multiple specific directories
python -m kiro_budget.cli process -d raw/chase -d raw/firsttech -d raw/gemini
```

### Error Handling and Logging

The tool provides comprehensive error handling and logging:

- **Processing Logs**: Detailed logs in `logs/` directory
- **Error Reports**: Failed files with error details
- **Validation Warnings**: Data quality issues and suggestions
- **Processing Statistics**: Success rates, duplicate counts, processing times

### Analysis Scripts

Use the included analysis scripts for debugging and financial analysis:

```bash
# Generate monthly spending report
python scripts/analysis/monthly_summary_report.py

# Find potential transfer pairs between accounts
python scripts/analysis/find_transfer_pairs.py

# Debug duplicate detection
python scripts/analysis/debug_dedup.py
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/kiro_budget

# Run specific test file
pytest tests/test_qfx_parser.py
```

### Code Quality

```bash
# Format code
black src/ tests/ scripts/

# Lint code  
flake8 src/ tests/ scripts/

# Type checking
mypy src/
```

### Project Structure

```
kiro-budget/
├── src/kiro_budget/          # Main package
│   ├── parsers/              # File format parsers
│   │   ├── qfx_parser.py     # QFX/OFX parser
│   │   ├── pdf_parser.py     # PDF statement parser
│   │   ├── csv_parser.py     # CSV parser
│   │   └── base.py           # Base parser classes
│   ├── utils/                # Utility modules
│   │   ├── account_config.py      # Account configuration loader
│   │   ├── account_enricher.py    # Transaction enrichment
│   │   ├── importer.py            # Transaction import & consolidation
│   │   ├── duplicate_detector.py  # Duplicate detection
│   │   ├── csv_writer.py          # CSV output handling
│   │   ├── validation.py          # Data validation
│   │   └── config_manager.py      # Configuration management
│   ├── models/               # Data models
│   │   └── core.py           # Transaction and config models
│   └── cli.py                # Command-line interface
├── tests/                    # Test files
├── scripts/analysis/         # Analysis and reporting scripts
├── docs/                     # Documentation
├── examples/                 # Usage examples
├── .kiro/specs/             # Feature specifications
└── raw/                      # Raw financial data (gitignored)
```

## Troubleshooting

### Common Issues

**"No suitable parser found"**
- Ensure file has correct extension (.qfx, .pdf, .csv)
- Check file is not corrupted or empty
- Verify file format matches extension

**"Duplicate transactions not detected"**
- Check date ranges overlap between files
- Verify transaction amounts and descriptions are similar
- Review duplicate detection logs for details

**"Account enrichment not working"**
- Ensure `raw/accounts.yaml` exists and is properly formatted
- Check that institution names match directory names (case-insensitive)
- Verify account IDs match what appears in transaction files
- Run import command after updating account configuration

**"Monthly report shows wrong account types"**
- Check account_type in `raw/accounts.yaml` (should be "credit" or "debit")
- Re-run the import command to regenerate consolidated transactions
- Regenerate the monthly report after import

**"Transactions missing after import"**
- Check for CSV parsing errors in logs
- Verify all institution directories are included in data/ scan
- Look for malformed CSV rows (descriptions with unescaped commas)

### Getting Help

1. Check the logs in `logs/` directory for detailed error information
2. Run analysis scripts to debug specific issues
3. Review the documentation in `docs/` directory
4. Check existing issues and examples

## Contributing

1. Follow the project structure standards in `.kiro/steering/`
2. Add tests for new functionality
3. Update documentation for new features
4. Run code quality checks before submitting