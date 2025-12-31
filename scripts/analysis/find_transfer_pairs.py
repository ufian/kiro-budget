#!/usr/bin/env python3
"""Find matching transfer pairs between accounts.

This script identifies transactions that are likely internal transfers:
- Same date
- Same absolute amount
- One from debit account (withdrawal)
- One from credit account (payment received)

Usage:
    python scripts/analysis/find_transfer_pairs.py [input_csv]
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime
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


def find_transfer_pairs(transactions: list) -> list:
    """Find matching transfer pairs.
    
    Returns list of (debit_txn, credit_txn) pairs.
    """
    # Group by date and absolute amount
    groups = defaultdict(list)
    
    for txn in transactions:
        key = (txn['date'].strftime('%Y-%m-%d'), str(txn['abs_amount']))
        groups[key].append(txn)
    
    pairs = []
    
    for (date, amount), txns in groups.items():
        if len(txns) < 2:
            continue
        
        # Separate by account type
        debit_txns = [t for t in txns if t['account_type'] == 'debit' and t['amount'] < 0]
        credit_txns = [t for t in txns if t['account_type'] == 'credit' and t['amount'] < 0]
        
        # Also check for positive amounts on credit (payment received)
        credit_payments = [t for t in txns if t['account_type'] == 'credit' and t['amount'] > 0]
        
        # Match debit withdrawals with credit payments
        for debit in debit_txns:
            # Look for matching credit card payment
            for credit in credit_txns:
                if debit['institution'] != credit['institution']:
                    # Different institutions - likely a transfer
                    pairs.append((debit, credit))
                    break
    
    return pairs


def find_potential_transfers(transactions: list) -> dict:
    """Find all potential internal transfer transactions.
    
    Groups transactions by date and amount to find matches.
    """
    # Group by date and absolute amount
    groups = defaultdict(list)
    
    for txn in transactions:
        key = (txn['date'].strftime('%Y-%m-%d'), str(txn['abs_amount']))
        groups[key].append(txn)
    
    # Filter to groups with 2+ transactions
    potential = {k: v for k, v in groups.items() if len(v) >= 2}
    
    return potential


def print_transfer_analysis(transactions: list):
    """Print analysis of potential transfers."""
    
    potential = find_potential_transfers(transactions)
    
    print("=" * 80)
    print("POTENTIAL INTERNAL TRANSFER PAIRS")
    print("=" * 80)
    print()
    
    # Sort by date
    sorted_keys = sorted(potential.keys())
    
    transfer_count = 0
    total_amount = Decimal('0')
    
    for date, amount in sorted_keys:
        txns = potential[(date, amount)]
        
        # Check if this looks like an internal transfer
        institutions = set(t['institution'] for t in txns)
        account_types = set(t['account_type'] for t in txns)
        
        # Skip if all same institution (likely duplicates, not transfers)
        if len(institutions) == 1 and len(txns) == 2:
            # Could be internal transfer within same institution
            signs = [t['amount'] > 0 for t in txns]
            if signs[0] != signs[1]:
                # One positive, one negative - internal transfer
                pass
            else:
                continue
        
        print(f"Date: {date}, Amount: ${amount}")
        print("-" * 60)
        
        for txn in txns:
            sign = "+" if txn['amount'] > 0 else "-"
            print(f"  {sign}${txn['abs_amount']:>10} | {txn['account_type']:6} | "
                  f"{txn['institution']:12} | {txn['description'][:40]}")
        
        print()
        transfer_count += 1
        total_amount += Decimal(amount)
    
    print("=" * 80)
    print(f"Found {transfer_count} potential transfer groups")
    print(f"Total amount involved: ${total_amount:,.2f}")
    print("=" * 80)


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
