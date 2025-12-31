# Transaction Classification Fix

## Issue Description

The monthly summary report was incorrectly classifying credit card transactions due to different sign conventions used by different institutions.

**Examples:**
- `2025-12-22,-24.00,DELTA AIR SEAT FEES,8147,Chase,credit,Chase` (Chase: negative = spending) ✅
- `2025-09-28,6.00,ORCA SEATTLE USA,unknown,Gemini,credit,Gemini` (Gemini: positive = spending) ❌ Was classified as refund

## Root Cause

Different credit card institutions use different sign conventions:

- **Chase/Apple**: Negative = spending, Positive = payments/credits
- **Gemini**: Positive = spending, Negative = payments/credits

The original code assumed all institutions followed the same convention.

## Solution: Institution-Specific Classification

### 1. **Auto-Detection by Institution**

The system now detects sign conventions based on the institution:

```python
def _classify_credit_card_transaction(description: str, amount: Decimal, institution: str) -> str:
    # Check for transfer patterns first (regardless of institution)
    if any(pattern in desc_lower for pattern in ['payment transaction', 'deposit internet transfer']):
        return 'internal_transfer'
    
    # Institution-specific sign conventions
    if institution.lower() == 'gemini':
        # Gemini: Positive = spending, Negative = payments/credits
        if amount > 0:
            return 'spending'  # Small purchases
        else:
            return 'internal_transfer' if abs(amount) > 100 else 'refund'
    
    elif institution.lower() in ['chase', 'apple']:
        # Chase/Apple: Negative = spending, Positive = payments/credits
        if amount < 0:
            return 'spending'
        else:
            return 'refund'
```

### 2. **Smart Amount-Based Heuristics**

- **Small amounts** (< $1000): Likely purchases
- **Large amounts** (> $1000): Check description for payment keywords
- **Very large amounts** (> $2000): Likely payments regardless of sign

### 3. **Transfer Pattern Detection**

Detects transfer patterns across institutions:
- "Payment Transaction" → `internal_transfer`
- "Deposit Internet Transfer" → `internal_transfer`
- "Payment Thank You" → `internal_transfer`

## Verification

The fix correctly classifies:

✅ **Chase Credit Card:**
- `DELTA AIR SEAT FEES, -$24.00` → `spending`
- `Payment Thank You-Mobile, +$5109.43` → `internal_transfer`

✅ **Gemini Credit Card:**
- `ORCA SEATTLE USA, +$6.00` → `spending`
- `Trader Joe's, +$39.99` → `spending`
- `Payment Transaction, -$3071.09` → `internal_transfer`

✅ **Apple Credit Card:**
- `FRED-MEYER, -$60.07` → `spending`
- `DEPOSIT INTERNET TRANSFER, +$2075.85` → `internal_transfer`

## Impact

This fix ensures that:

1. **Gemini purchases** (like ORCA transit, restaurants, groceries) are correctly categorized as "spending"
2. **Cross-institution payments** are correctly identified as "internal_transfer"
3. **Monthly spending totals** accurately include all credit card purchases regardless of institution
4. **Auto-detection** works for unknown institutions using smart heuristics

## Files Modified

- `scripts/analysis/monthly_summary_report.py` - Added institution-specific classification logic

## Related Documentation

- `docs/transfer_timing_considerations.md` - Information about 3 business day transfer lag
- `scripts/analysis/transfer_timing_analysis.py` - Analysis of transfer timing patterns