# Scripts Directory

This directory contains automation scripts for the kiro-budget financial data processing system.

## Main Scripts

### `generate_deep_monthly_report.sh`

**Primary automation script for generating comprehensive monthly financial reports.**

#### Quick Start
```bash
# Generate complete monthly report (recommended)
./scripts/generate_deep_monthly_report.sh

# Force reprocess all files and don't open browser
./scripts/generate_deep_monthly_report.sh --force --no-open

# Show help
./scripts/generate_deep_monthly_report.sh --help
```

#### What It Does
1. **Processes Raw Files** → Converts PDF, QFX, CSV files to standardized format
2. **Consolidates Data** → Combines all files with duplicate detection
3. **Generates Report** → Creates interactive HTML monthly summary

#### Options
- `--force` - Force reprocessing of all raw files (ignore processing history)
- `--no-open` - Don't automatically open the report in browser
- `--help` - Show detailed usage information

#### Prerequisites
- Virtual environment activated: `source venv/bin/activate`
- Raw financial files in `raw/` directory
- Account configuration at `raw/accounts.yaml` (optional)

#### Output Files
- `data/reports/monthly_summary.html` - Interactive monthly report
- `data/total/all_transactions.csv` - Consolidated transaction data
- `data/total/total_stats.json` - Summary statistics

## Analysis Scripts

### `analysis/monthly_summary_report.py`
Generates interactive HTML monthly summary with transfer pair detection.

```bash
python scripts/analysis/monthly_summary_report.py [input_csv] [output_html]
```

### `analysis/find_transfer_pairs.py`
Identifies and analyzes transfer pairs between accounts.

### `analysis/transfer_timing_analysis.py`
Analyzes timing patterns in transfer transactions.

### `analysis/find_duplicate_transactions.py`
Advanced duplicate detection across multiple data sources.

## Export Scripts

### `export/build_total_csv.py`
Combines all processed CSV files into a single consolidated file.

```bash
python scripts/export/build_total_csv.py
```

### `export/remove_pdf_qfx_duplicates.py`
Removes duplicates between PDF and QFX sources from the same institution.

## Usage Patterns

### Daily Processing
```bash
# Process new files only (fast)
./scripts/generate_deep_monthly_report.sh
```

### Monthly Full Refresh
```bash
# Reprocess everything (comprehensive)
./scripts/generate_deep_monthly_report.sh --force
```

### Automated Processing
```bash
# For scripts/automation (no browser opening)
./scripts/generate_deep_monthly_report.sh --no-open
```

### Development/Testing
```bash
# Individual steps for debugging
python -m kiro_budget.cli process
python scripts/export/build_total_csv.py
python scripts/analysis/monthly_summary_report.py
```

## File Organization

```
scripts/
├── README.md                           # This file
├── generate_deep_monthly_report.sh     # Main automation script
├── analysis/                           # Analysis and reporting scripts
│   ├── monthly_summary_report.py
│   ├── find_transfer_pairs.py
│   ├── transfer_timing_analysis.py
│   └── find_duplicate_transactions.py
└── export/                             # Data export and consolidation
    ├── build_total_csv.py
    └── remove_pdf_qfx_duplicates.py
```

## Error Handling

The main script includes comprehensive error handling:
- Validates prerequisites (virtual environment, raw files)
- Checks each step completion before proceeding
- Provides clear error messages and suggestions
- Exits gracefully on any failure

## Performance Notes

- **First run**: Processes all files (~30-60 seconds for typical dataset)
- **Subsequent runs**: Only processes new/changed files (~5-10 seconds)
- **Force refresh**: Reprocesses everything (~30-60 seconds)
- **Large datasets**: 10K+ transactions may take several minutes

## Troubleshooting

### Common Issues

**"Virtual environment not detected"**
```bash
source venv/bin/activate
```

**"No financial files found"**
- Add PDF, QFX, or CSV files to the `raw/` directory
- Organize by institution: `raw/chase/`, `raw/apple/`, etc.

**"Permission denied"**
```bash
chmod +x scripts/generate_deep_monthly_report.sh
```

**"Report not opening"**
- Use `--no-open` flag and manually open `data/reports/monthly_summary.html`
- Check browser permissions for local file access

### Getting Help

1. Run with `--help` flag for detailed usage
2. Check the main project documentation
3. Review log files in `logs/` directory
4. Examine processing state in `.kiro_parser_state/`