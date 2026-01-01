# Deep Monthly Report Generation

This steering file describes the complete end-to-end process for generating a comprehensive monthly financial report from raw financial data files.

## Overview

The "deep monthly report" process involves three main stages:
1. **Raw File Processing**: Convert all raw financial files (PDF, QFX, CSV) to standardized CSV format
2. **Data Consolidation**: Build a unified `all_transactions.csv` file with duplicate detection and sign correction
3. **Report Generation**: Create an interactive HTML monthly summary report with transfer pair detection

## Prerequisites

- Virtual environment activated: `source venv/bin/activate`
- All raw financial files placed in `raw/` directory organized by institution
- Account configuration file at `raw/accounts.yaml` (optional but recommended)

## Complete Workflow

### Step 1: Process Raw Files to CSV

Convert all raw financial files in the `raw/` directory to standardized CSV format in the `data/` directory.

```bash
# Process all files in raw directory (recommended)
python -m kiro_budget.cli process

# Alternative: Process specific directories
python -m kiro_budget.cli process -d raw/chase raw/firsttech raw/gemini

# Alternative: Process specific files
python -m kiro_budget.cli process -f raw/chase/statement.pdf raw/chase/activity.qfx

# Force reprocessing (ignore previous processing history)
python -m kiro_budget.cli process --force

# Generate processing report
python -m kiro_budget.cli process -r data/reports/processing_report.json
```

**What this does:**
- Automatically detects file formats (PDF, QFX, CSV)
- Applies appropriate parser for each file type
- Performs automatic sign detection and correction (banking vs credit card convention)
- Enriches transactions with account information from `accounts.yaml`
- Saves processed transactions as CSV files in `data/` directory
- Tracks processing history to avoid reprocessing unchanged files

**Expected Output:**
- Individual CSV files in `data/` directory (e.g., `data/chase_statement_2024-12.csv`)
- Processing logs in `logs/` directory
- Optional processing report in JSON format

### Step 2: Build Consolidated Transaction File

Combine all processed CSV files into a single consolidated file with advanced duplicate detection.

```bash
# Build the consolidated all_transactions.csv file
python scripts/export/build_total_csv.py
```

**What this does:**
- Finds all CSV files in the `data/` directory (excluding existing total files)
- Combines all transactions into a single DataFrame
- Removes exact duplicates based on date, amount, description, account, institution
- Performs advanced fuzzy duplicate detection for PDF vs QFX cross-source duplicates
- Sorts transactions chronologically
- Saves consolidated file as `data/total/all_transactions.csv`
- Generates summary statistics in `data/total/total_stats.json`

**Expected Output:**
- `data/total/all_transactions.csv` - Consolidated transaction file
- `data/total/total_stats.json` - Summary statistics
- Console output showing duplicate removal statistics and data summary

### Step 3: Generate Monthly Summary Report

Create an interactive HTML report with monthly summaries and transfer pair detection.

```bash
# Generate the monthly summary HTML report
python scripts/analysis/monthly_summary_report.py

# Alternative: Specify custom input/output paths
python scripts/analysis/monthly_summary_report.py data/total/all_transactions.csv data/reports/custom_report.html
```

**What this does:**
- Loads the consolidated transaction file
- Identifies and pairs internal transfers (credit card payments, account transfers)
- Classifies transactions into categories: Income, Internal Transfers, External Transfers, Credits/Refunds, Spending
- Aggregates data by month with NET transfer amounts to avoid double-counting
- Generates interactive HTML report with clickable cells for transaction drill-down
- Handles transfer timing lag (transfers may appear in different months)

**Expected Output:**
- `data/reports/monthly_summary.html` - Interactive HTML report
- Console output showing transfer pair detection statistics

## Complete One-Command Workflow

For convenience, you can run all three steps in sequence:

```bash
# Activate virtual environment
source venv/bin/activate

# Step 1: Process all raw files
python -m kiro_budget.cli process --force

# Step 2: Build consolidated CSV
python scripts/export/build_total_csv.py

# Step 3: Generate monthly report
python scripts/analysis/monthly_summary_report.py

# Open the report
open data/reports/monthly_summary.html
```

## Key Features

### Automatic Sign Detection
- Detects credit card vs banking convention automatically
- Applies consistent sign correction: negative = spending, positive = income
- Handles all transaction types uniformly

### Advanced Duplicate Detection
- Removes exact duplicates across all files
- Detects PDF vs QFX duplicates from same institution using fuzzy matching
- Prefers QFX data over PDF data when duplicates are found

### Transfer Pair Detection
- Identifies credit card payment pairs (payment sent ↔ payment received)
- Detects internal account transfers (withdrawal ↔ deposit)
- Consolidates pairs to show NET amounts and avoid double-counting
- Handles timing lag between paired transactions (up to 7 days)

### Interactive Reporting
- Monthly summary table with year subtotals and grand totals
- Clickable cells to drill down into underlying transactions
- Color-coded amounts (red = spending, green = income, blue = transfers)
- Transfer pair annotations showing processing lag
- Responsive design for desktop and mobile viewing

## File Organization

```
kiro-budget/
├── raw/                          # Input: Raw financial files
│   ├── accounts.yaml            # Account configuration
│   ├── chase/                   # Chase bank files
│   ├── firsttech/               # FirstTech Credit Union files
│   ├── gemini/                  # Gemini Credit Card files
│   └── ...
├── data/                        # Output: Processed CSV files
│   ├── chase_statement_2024-12.csv
│   ├── firsttech_activity_2024-12.csv
│   ├── total/
│   │   ├── all_transactions.csv # Consolidated transaction file
│   │   └── total_stats.json     # Summary statistics
│   └── reports/
│       ├── monthly_summary.html # Interactive monthly report
│       └── processing_report.json
└── logs/                        # Processing logs
    ├── parser_YYYYMMDD.jsonl
    └── errors_YYYYMMDD.jsonl
```

## Troubleshooting

### Common Issues

**"No CSV files found"**
- Ensure Step 1 (raw file processing) completed successfully
- Check that CSV files exist in the `data/` directory
- Verify file permissions and paths

**"Input file not found"**
- Ensure Step 2 (build consolidated CSV) completed successfully
- Check that `data/total/all_transactions.csv` exists
- Verify the file path is correct

**"Transfer pairs not detected"**
- This is normal for some data sets
- Transfer pair detection uses specific patterns and timing windows
- Manual review may be needed for unusual transaction descriptions

**"Monthly totals don't balance"**
- Internal transfers may have processing lag (up to 7 days)
- Transfer pairs might appear in different months
- This is expected behavior and documented in the report

### Performance Considerations

- Large datasets (>50K transactions) may take several minutes to process
- Duplicate detection is memory-intensive for very large files
- Consider processing files in smaller batches if memory issues occur

## Customization

### Modifying Transaction Classification
Edit patterns in `scripts/analysis/monthly_summary_report.py`:
- `INCOME_PATTERNS`: Add employer-specific deposit patterns
- `CREDIT_CARD_PAYMENT_PATTERNS`: Add bank-specific payment patterns
- `INTERNAL_TRANSFER_PATTERNS`: Add institution-specific transfer patterns

### Adjusting Transfer Pair Detection
Modify timing windows and matching criteria:
- `max_days` parameter in transfer pair functions
- Amount similarity thresholds for fuzzy matching
- Institution-specific matching patterns

### Custom Report Styling
Modify CSS styles in the HTML template within `generate_html()` function:
- Color schemes and themes
- Table layouts and responsive design
- Modal dialog styling

## Data Privacy and Security

- All processing happens locally - no data is sent to external services
- Raw files remain unchanged in the `raw/` directory
- Processed data is stored locally in the `data/` directory
- HTML reports contain transaction details - handle with appropriate security
- Consider encrypting sensitive financial data at rest