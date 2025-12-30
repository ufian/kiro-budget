# Kiro Budget

A comprehensive financial data parser and analysis tool that processes multiple file formats (QFX, PDF, CSV) from various financial institutions, automatically detects and removes duplicate transactions, and outputs clean, standardized CSV data.

## Features

- **Multi-Format Support**: Parse QFX/OFX, PDF statements, and CSV files
- **Intelligent Duplicate Detection**: Automatically identifies and merges duplicate transactions across different file formats
- **Institution Support**: Built-in support for Chase, First Tech, Gemini, and other major financial institutions
- **Plugin System**: Extensible architecture for adding custom parsers and processors
- **Data Validation**: Comprehensive validation and error handling
- **Batch Processing**: Process multiple files simultaneously with progress tracking
- **Standardized Output**: Unified CSV format with consistent field mapping

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

### 2. Prepare Your Data

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

### 3. Process Your Data

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
date,amount,description,account,institution,transaction_id,category,balance
2024-01-15,-52.20,AMAZON MKTPL*ABC123,1234,Chase,20240115123456789,,
2024-01-16,1500.00,PAYROLL DEPOSIT,1234,Chase,20240116987654321,,
```

**Fields:**
- `date`: Transaction date (YYYY-MM-DD)
- `amount`: Transaction amount (negative for debits, positive for credits)
- `description`: Transaction description/merchant name
- `account`: Account identifier
- `institution`: Financial institution name
- `transaction_id`: Unique transaction ID (when available)
- `category`: Transaction category (optional)
- `balance`: Account balance after transaction (when available)

### Duplicate Detection

The tool automatically detects and removes duplicate transactions using:

- **Transaction IDs**: Exact matching for QFX/OFX files
- **Fuzzy Matching**: Amount + description + date tolerance for cross-format detection
- **Date Tolerance**: 3-day window to handle posting vs transaction date differences
- **Description Normalization**: Handles merchant name variations and location differences

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
│   └── chase_1234_20240101_20240131.csv
├── firsttech/
│   └── firsttech_5678_20240101_20240131.csv
└── reports/
    └── processing_report_20240201.json
```

## Advanced Usage

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

Use the included analysis scripts for debugging and investigation:

```bash
# Debug parser behavior
python scripts/analysis/debug_parsers.py

# Test duplicate detection
python scripts/analysis/debug_duplicates.py

# Analyze PDF structure
python scripts/analysis/debug_pdf_content.py
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
│   │   ├── duplicate_detector.py  # Duplicate detection
│   │   ├── csv_writer.py     # CSV output handling
│   │   ├── validation.py     # Data validation
│   │   └── config_manager.py # Configuration management
│   ├── models/               # Data models
│   │   └── core.py           # Transaction and config models
│   └── cli.py                # Command-line interface
├── tests/                    # Test files
├── scripts/analysis/         # Analysis and debug scripts
├── docs/                     # Documentation
├── examples/                 # Usage examples
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

**"PDF parsing failed"**
- Ensure PDF is not password protected
- Check PDF contains readable text (not scanned images)
- Try different PDF files to isolate the issue

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