# Analysis Scripts

This directory contains one-time analysis and debugging scripts used for investigating parser behavior, duplicate detection, and data quality issues.

## Scripts

### `debug_parsers.py`
Compares parsing results between QFX and PDF parsers to identify discrepancies in transaction data, amounts, dates, and descriptions.

**Usage:**
```bash
cd kiro-budget
python scripts/analysis/debug_parsers.py
```

### `debug_duplicates.py`
Tests the duplicate detection logic across multiple file formats to verify that identical transactions are properly identified and merged.

**Usage:**
```bash
cd kiro-budget
python scripts/analysis/debug_duplicates.py
```

### `debug_specific_duplicates.py`
Analyzes specific transaction pairs that should be duplicates to debug signature generation and matching logic.

**Usage:**
```bash
cd kiro-budget
python scripts/analysis/debug_specific_duplicates.py
```

### `debug_pdf_content.py`
Examines PDF file structure and content to understand how transaction data is organized within PDF statements.

**Usage:**
```bash
cd kiro-budget
python scripts/analysis/debug_pdf_content.py
```

### `debug_cli.py`
Tests the CLI processing pipeline to verify that batch processing and duplicate detection are working correctly.

**Usage:**
```bash
cd kiro-budget
python scripts/analysis/debug_cli.py
```

## Notes

- These scripts are designed for development and debugging purposes
- They require the development environment to be set up with all dependencies installed
- Scripts assume they are run from the project root directory
- Output is primarily for console analysis and debugging