#!/usr/bin/env python3
"""Find matching transfer pairs between accounts.

This script identifies transactions that are likely internal transfers:
- Same absolute amount
- Within 3 business days (to account for processing lag)
- One from debit account (withdrawal)
- One from credit account (payment received)

Internal transfers may have up to 3 business days of lag between accounts.

Usage:
    python scripts/analysis/find_transfer_pairs.py [input_csv]
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


def load_transactions(csv_path: str) -> list:
    """Load transactions from CSV file."""
    transactions = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            try:
                date = datetime.strptime(row['date'], '%Y-%m-%d')
                amount = Decimal(row['amount'])
                transactions.append({
                    'line': i,
                    'date': date,
                    'amount': amount,
                    'abs_amount': abs(amount),
                    'description': row['description'],
                    'account': row['account'],
                    'account_name': row['account_name'],
                    'account_type': row.get('account_type', 'debit'),
                    'institution': row['institution'],
                })
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping invalid row {i}: {e}", file=sys.stderr)
    
    return transactions


def is_business_day(date):
    """Check if a date is a business day (Monday-Friday)."""
    return date.weekday() < 5


def business_days_between(start_date, end_date):
    """Calculate the number of business days between two dates."""
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        if is_business_day(current_date):
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days


def find_transfer_pairs_with_lag(transactions: list, max_business_days: int = 3) -> list:
    """Find matching transfer pairs accounting for processing lag.
    
    Returns list of (debit_txn, credit_txn, days_lag) tuples.
    """
    # Group transactions by absolute amount
    amount_groups = defaultdict(list)
    
    for txn in transactions:
        amount_groups[str(txn['abs_amount'])].append(txn)
    
    pairs = []
    
    for amount, txns in amount_groups.items():
        if len(txns) < 2:
            continue
        
        # Look for potential transfer pairs within the same amount group
        for i, txn1 in enumerate(txns):
            for txn2 in txns[i+1:]:
                # Skip if same institution AND same account (likely duplicates)
                if txn1['institution'] == txn2['institution'] and txn1['account'] == txn2['account']:
                    continue
                
                # Calculate business days between transactions
                days_diff = business_days_between(txn1['date'], txn2['date'])
                
                if days_diff <= max_business_days:
                    # Check if this looks like a transfer pair
                    # One should be negative (outgoing), one positive (incoming)
                    if (txn1['amount'] < 0 and txn2['amount'] > 0) or \
                       (txn1['amount'] > 0 and txn2['amount'] < 0):
                        
                        # Determine which is the source (outgoing) and destination (incoming)
                        if txn1['amount'] < 0:
                            source_txn, dest_txn = txn1, txn2
                        else:
                            source_txn, dest_txn = txn2, txn1
                        
                        pairs.append((source_txn, dest_txn, days_diff))
    
    return pairs


def find_transfer_pairs(transactions: list) -> list:
    """Find matching transfer pairs (legacy function for backward compatibility).
    
    Returns list of (debit_txn, credit_txn) pairs.
    """
    pairs_with_lag = find_transfer_pairs_with_lag(transactions)
    return [(source, dest) for source, dest, _ in pairs_with_lag]


def find_potential_transfers_with_lag(transactions: list, max_business_days: int = 3) -> dict:
    """Find all potential internal transfer transactions accounting for lag.
    
    Groups transactions by amount and looks for matches within the business day window.
    """
    # Group by absolute amount
    amount_groups = defaultdict(list)
    
    for txn in transactions:
        amount_groups[str(txn['abs_amount'])].append(txn)
    
    # Find potential matches within each amount group
    potential = {}
    
    for amount, txns in amount_groups.items():
        if len(txns) < 2:
            continue
        
        # Look for transactions within the lag window
        matches = []
        for i, txn1 in enumerate(txns):
            for txn2 in txns[i+1:]:
                days_diff = business_days_between(txn1['date'], txn2['date'])
                
                if days_diff <= max_business_days:
                    # Check if signs are opposite (transfer pattern)
                    if (txn1['amount'] < 0 and txn2['amount'] > 0) or \
                       (txn1['amount'] > 0 and txn2['amount'] < 0):
                        
                        # Sort by date for consistent display
                        if txn1['date'] <= txn2['date']:
                            matches.append((txn1, txn2, days_diff))
                        else:
                            matches.append((txn2, txn1, days_diff))
        
        if matches:
            potential[amount] = matches
    
    return potential


def print_transfer_analysis(transactions: list):
    """Print analysis of potential transfers with lag consideration."""
    
    potential = find_potential_transfers_with_lag(transactions)
    
    print("=" * 80)
    print("POTENTIAL INTERNAL TRANSFER PAIRS (with 3-day lag consideration)")
    print("=" * 80)
    print()
    
    # Sort by amount (descending)
    sorted_amounts = sorted(potential.keys(), key=lambda x: Decimal(x), reverse=True)
    
    transfer_count = 0
    total_amount = Decimal('0')
    
    for amount in sorted_amounts:
        matches = potential[amount]
        
        print(f"Amount: ${amount}")
        print("-" * 60)
        
        for txn1, txn2, days_lag in matches:
            # Determine source and destination
            if txn1['amount'] < 0:
                source, dest = txn1, txn2
            else:
                source, dest = txn2, txn1
            
            lag_info = f" ({days_lag} business day{'s' if days_lag != 1 else ''} lag)" if days_lag > 0 else " (same day)"
            
            print(f"  {source['date'].strftime('%Y-%m-%d')} → {dest['date'].strftime('%Y-%m-%d')}{lag_info}")
            print(f"    OUT: ${source['abs_amount']:>10} | {source['account_type']:6} | "
                  f"{source['institution']:12} | {source['description'][:35]}")
            print(f"    IN:  ${dest['abs_amount']:>10} | {dest['account_type']:6} | "
                  f"{dest['institution']:12} | {dest['description'][:35]}")
            print()
            
            transfer_count += 1
            total_amount += Decimal(amount)
    
    print("=" * 80)
    print(f"Found {transfer_count} potential transfer pairs")
    print(f"Total amount involved: ${total_amount:,.2f}")
    print("=" * 80)
    
    # Add summary of lag distribution
    if transfer_count > 0:
        lag_counts = defaultdict(int)
        for matches in potential.values():
            for _, _, days_lag in matches:
                lag_counts[days_lag] += 1
        
        print("\nLag Distribution:")
        for days in sorted(lag_counts.keys()):
            count = lag_counts[days]
            percentage = (count / transfer_count) * 100
            lag_desc = "same day" if days == 0 else f"{days} business day{'s' if days != 1 else ''}"
            print(f"  {lag_desc:15}: {count:3d} pairs ({percentage:5.1f}%)")
        print()


def find_potential_transfers(transactions: list) -> dict:
    """Legacy function for backward compatibility."""
    potential_with_lag = find_potential_transfers_with_lag(transactions)
    
    # Convert to old format for compatibility
    legacy_format = {}
    for amount, matches in potential_with_lag.items():
        for txn1, txn2, _ in matches:
            # Use the earlier date as the key
            date_key = min(txn1['date'], txn2['date']).strftime('%Y-%m-%d')
            key = (date_key, amount)
            if key not in legacy_format:
                legacy_format[key] = []
            legacy_format[key].extend([txn1, txn2])
    
    return legacy_format


def print_credit_card_payments(transactions: list):
    """Print all credit card payment transactions."""
    
    print()
    print("=" * 80)
    print("CREDIT CARD PAYMENT PATTERNS")
    print("=" * 80)
    print()
    
    # Find payment-related transactions
    payment_keywords = ['payment', 'pymt', 'cardpymt', 'thank you']
    
    payments = []
    for txn in transactions:
        desc_lower = txn['description'].lower()
        if any(kw in desc_lower for kw in payment_keywords):
            payments.append(txn)
    
    # Group by description pattern
    patterns = defaultdict(list)
    for txn in payments:
        # Normalize description
        desc = txn['description'].lower()
        if 'thank you' in desc:
            pattern = 'Payment Thank You'
        elif 'cardpymt' in desc:
            pattern = 'CardPymt (withdrawal)'
        elif 'payment transaction' in desc:
            pattern = 'Payment Transaction'
        else:
            pattern = 'Other Payment'
        
        patterns[pattern].append(txn)
    
    for pattern, txns in sorted(patterns.items()):
        print(f"\n{pattern} ({len(txns)} transactions):")
        print("-" * 60)
        
        # Show sample transactions
        for txn in txns[:5]:
            sign = "+" if txn['amount'] > 0 else "-"
            print(f"  {txn['date'].strftime('%Y-%m-%d')} | {sign}${txn['abs_amount']:>10} | "
                  f"{txn['account_type']:6} | {txn['institution']:12} | {txn['description'][:35]}")
        
        if len(txns) > 5:
            print(f"  ... and {len(txns) - 5} more")


def main():
    # Default path
    input_csv = 'data/total/all_transactions.csv'
    
    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
    
    if not Path(input_csv).exists():
        print(f"Error: Input file not found: {input_csv}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Loading transactions from: {input_csv}")
    transactions = load_transactions(input_csv)
    print(f"Loaded {len(transactions)} transactions")
    
    print_transfer_analysis(transactions)
    print_credit_card_payments(transactions)


if __name__ == '__main__':
    main()
