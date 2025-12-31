# Automatic Transaction Sign Detection

## Overview

The financial data parser now includes automatic sign detection and correction to ensure consistent transaction signs across all file formats. This eliminates the need for manual credit card detection during monthly reports.

## Sign Convention

All processed transactions follow **banking convention**:
- **Spending transactions** (debits): **Negative amounts** (money going out)
- **Income transactions** (credits): **Positive amounts** (money coming in)
- **Transfers out**: **Negative amounts** (money leaving account)
- **Transfers in**: **Positive amounts** (money entering account)

## How It Works

### 1. File Analysis
The system analyzes each file to detect its original sign convention:

- **Banking Convention**: Spending negative, income positive (e.g., bank statements)
- **Credit Card Convention**: Spending positive, income negative (e.g., credit card statements)
- **Mixed/Unknown**: Inconsistent or unclear patterns

### 2. Transaction Classification
Transactions are classified based on description keywords:

**Spending Keywords:**
- `purchase`, `fee`, `interest`, `charge`, `penalty`, `late`
- `withdrawal`, `atm`, `pos`, `debit`, `bill`, `subscription`
- `grocery`, `restaurant`, `gas`, `fuel`, `shopping`, `store`
- `medical`, `insurance`, `rent`, `mortgage`, `loan`, `tax`

**Income Keywords:**
- `deposit`, `credit`, `refund`, `return`, `cashback`, `reward`
- `salary`, `payroll`, `dividend`, `bonus`, `thank you`
- `interest earned`, `adjustment credit`, `reversal`

**Transfer Keywords:**
- Transfer out: `transfer to`, `outgoing transfer`, `wire out`
- Transfer in: `transfer from`, `incoming transfer`, `wire in`

### 3. Confidence-Based Correction
The system calculates confidence based on:
- Ratio of spending transactions with positive amounts
- Ratio of income transactions with positive amounts
- Total number of classified transactions

Only applies corrections when confidence ≥ 20% to avoid incorrect changes.

## Implementation

### Core Components

1. **`TransactionSignDetector`** (`src/kiro_budget/utils/sign_detector.py`)
   - Analyzes file sign conventions
   - Classifies transaction types
   - Applies sign corrections

2. **Parser Integration** (`src/kiro_budget/parsers/`)
   - All parsers (CSV, QFX, PDF) now call `apply_sign_correction()`
   - Automatic integration with existing parsing workflow

3. **Comprehensive Tests** (`tests/test_sign_detector.py`)
   - 13 test cases covering all scenarios
   - 87% code coverage for sign detection module

### Example Results

**Credit Card Statement (Before):**
```
2025-12-24,  26.40, Paris Baguette          # Spending (positive)
2025-12-19, -791.99, Payment Transaction    # Payment (negative)
```

**After Sign Correction:**
```
2025-12-24, -26.40, Paris Baguette          # Spending (negative) ✓
2025-12-19,  791.99, Payment Transaction    # Payment (positive) ✓
```

## Benefits

1. **Eliminates Manual Detection**: No need to manually identify credit card accounts
2. **Consistent Data**: All transactions follow the same sign convention
3. **Simplified Reports**: Monthly reports can assume consistent signs
4. **Automatic Processing**: Works transparently with existing CLI commands
5. **Safe Operation**: Only applies corrections with sufficient confidence

## Usage

The sign detection is automatic and requires no configuration. Simply process files as usual:

```bash
# Process all files with automatic sign detection
python -m kiro_budget.cli process

# Process specific files
python -m kiro_budget.cli process -f raw/chase/statement.pdf

# Force reprocessing with sign detection
python -m kiro_budget.cli process --force
```

## Logging

The system logs sign detection results:

```
INFO - Sign analysis: {
  'convention': 'credit_card', 
  'confidence': 0.7, 
  'spending_positive_ratio': 1.0, 
  'income_positive_ratio': 0.0
}
```

## Configuration

No configuration is required. The system uses built-in keyword lists and confidence thresholds that work well for most financial data formats.

## Backward Compatibility

- Existing processed CSV files remain unchanged
- Files already in banking convention are left as-is
- Low confidence scenarios preserve original signs
- All existing functionality continues to work normally