# Automatic Transaction Sign Detection

## Overview

The financial data parser includes automatic sign detection and correction to ensure consistent transaction signs across all file formats. This eliminates the need for manual credit card detection during monthly reports.

## Sign Convention

All processed transactions follow **banking convention**:
- **Spending transactions** (debits): **Negative amounts** (money going out)
- **Income transactions** (credits): **Positive amounts** (money coming in)
- **Transfers out**: **Negative amounts** (money leaving account)
- **Transfers in**: **Positive amounts** (money entering account)

## How It Works

### Simple Decision Logic

The system follows a clean, binary approach:

1. **Analyze the file** to detect its sign convention
2. **Make a single decision**: Does this file need sign correction?
3. **Apply consistently**: If yes, flip ALL signs; if no, keep ALL unchanged

### File Analysis
The system analyzes each file to detect its original sign convention:

- **Banking Convention**: Spending negative, income positive (e.g., bank statements)
- **Credit Card Convention**: Spending positive, income negative (e.g., credit card statements)
- **Mixed/Unknown**: Inconsistent or unclear patterns

### Transaction Classification
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

### Decision Criteria

**Signs are flipped for ALL transactions when:**
- Credit card convention is detected with ≥50% confidence

**Signs are kept unchanged when:**
- Banking convention is detected (any confidence level)
- Credit card convention detected with <50% confidence
- Mixed or unknown patterns detected

## Implementation

### Core Components

1. **`TransactionSignDetector`** (`src/kiro_budget/utils/sign_detector.py`)
   - `correct_transaction_signs()`: Main entry point with binary decision logic
   - `_should_flip_file_signs()`: Makes the flip/no-flip decision
   - `_flip_all_transaction_signs()`: Flips all signs when needed

2. **Parser Integration** (`src/kiro_budget/parsers/`)
   - All parsers (CSV, QFX, PDF) call `correct_transaction_signs()`
   - Automatic integration with existing parsing workflow

3. **Comprehensive Tests** (`tests/test_sign_detector.py`)
   - 13 test cases covering all scenarios
   - 92% code coverage for sign detection module

### Example Results

**Credit Card Statement (Before):**
```
2025-12-24,  26.40, Paris Baguette          # Spending (positive)
2025-12-19, -791.99, Payment Transaction    # Payment (negative)
2025-12-15,  15.00, Monthly Fee             # Fee (positive)
2025-12-10, 100.00, Unknown Transaction     # Unknown (positive)
```

**After Sign Correction (ALL flipped):**
```
2025-12-24, -26.40, Paris Baguette          # ALL signs flipped ✓
2025-12-19,  791.99, Payment Transaction    # ALL signs flipped ✓
2025-12-15, -15.00, Monthly Fee             # ALL signs flipped ✓
2025-12-10, -100.00, Unknown Transaction    # ALL signs flipped ✓
```

**Banking Statement (No changes):**
```
2025-12-24, -26.40, Grocery Store           # Already correct ✓
2025-12-19, 1500.00, Salary Deposit         # Already correct ✓
2025-12-15, -15.00, Monthly Fee             # Already correct ✓
```

## Benefits

1. **Simple Logic**: Binary decision eliminates complex edge cases
2. **Complete Consistency**: All transactions in a file follow the same rule
3. **Predictable Behavior**: Easy to understand and debug
4. **Eliminates Manual Detection**: No need to manually identify credit card accounts
5. **Automatic Processing**: Works transparently with existing CLI commands
6. **Safe Operation**: Conservative approach - only flips with high confidence

## Usage

The sign detection is automatic and requires no configuration:

```bash
# Process all files with automatic sign detection
python -m kiro_budget.cli process

# Process specific files
python -m kiro_budget.cli process -f raw/chase/statement.pdf

# Force reprocessing with sign detection
python -m kiro_budget.cli process --force
```

## Logging

The system logs its decisions clearly:

```
INFO - Sign analysis: {
  'convention': 'credit_card', 
  'confidence': 0.7, 
  'spending_positive_ratio': 1.0, 
  'income_positive_ratio': 0.0
}
INFO - Flipping signs for all 25 transactions (detected credit_card convention with 0.70 confidence)
```

Or for files that don't need changes:

```
INFO - Keeping original signs for all 15 transactions (detected banking convention with 0.85 confidence)
```

## Configuration

No configuration required. The system uses:
- Built-in keyword lists for transaction classification
- 50% confidence threshold for credit card detection
- Conservative approach that preserves original signs when uncertain

## Backward Compatibility

- Existing processed CSV files remain unchanged
- Files already in banking convention are preserved
- Low confidence scenarios keep original signs
- All existing functionality continues to work normally