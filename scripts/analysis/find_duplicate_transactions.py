#!/usr/bin/env python3
"""Find and analyze duplicate transactions from different data sources.

This script identifies transactions that appear multiple times due to:
- Same transaction in PDF statement and QFX file
- Pending vs posted transactions
- Different merchant name formats for same purchase

Unlike transfer pairs (money moving between accounts), these are true duplicates
of the same spending/income that should be consolidated.

Usage:
    python scripts/analysis/find_duplicate_transactions.py [input_csv]
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


def normalize_merchant_name(description: str) -> str:
    """Normalize merchant names for better duplicate detection."""
    desc = description.lower().strip()
    
    # Remove common prefixes/suffixes
    prefixes_to_remove = [
        'tst* ', 'sq *', 'sp *', 'pos ', 'debit ', 'credit ',
        'purchase ', 'sale ', 'payment ', 'withdrawal ', 'deposit '
    ]
    
    for prefix in prefixes_to_remove:
        if desc.startswith(prefix):
            desc = desc[len(prefix):].strip()
    
    # Remove store numbers and location codes
    import re
    # Remove patterns like "#1029", "#138", "975 NW GILMAN"
    desc = re.sub(r'#\d+', '', desc)
    desc = re.sub(r'\s+\d+\s+[nsew]{1,2}\s+\w+', '', desc, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    desc = ' '.join(desc.split())
    
    return desc


def find_spending_duplicates(transactions: list, max_days: int = 3) -> list:
    """Find duplicate spending transactions from different sources.
    
    Returns list of (txn1, txn2, similarity_score) tuples.
    """
    duplicates = []
    
    # Group transactions by similar amounts (within $1 to handle rounding)
    amount_groups = defaultdict(list)
    
    for txn in transactions:
        # Only look at spending transactions (negative amounts)
        if txn['amount'] >= 0:
            continue
            
        # Group by rounded amount to catch small differences
        amount_key = round(abs(txn['amount']))
        amount_groups[amount_key].append(txn)
    
    # Look for duplicates within each amount group
    for amount, txns in amount_groups.items():
        if len(txns) < 2:
            continue
            
        for i, txn1 in enumerate(txns):
            for txn2 in txns[i+1:]:
                # Skip if same source file (unlikely to be duplicates)
                if txn1.get('source_file') == txn2.get('source_file'):
                    continue
                
                # Check date proximity
                days_diff = abs((txn1['date'] - txn2['date']).days)
                if days_diff > max_days:
                    continue
                
                # Check amount similarity (allow small differences)
                amount_diff = abs(abs(txn1['amount']) - abs(txn2['amount']))
                if amount_diff > Decimal('1.00'):  # Allow up to $1 difference
                    continue
                
                # Check merchant name similarity
                merchant1 = normalize_merchant_name(txn1['description'])
                merchant2 = normalize_merchant_name(txn2['description'])
                
                # Calculate similarity score
                similarity_score = calculate_similarity(merchant1, merchant2)
                
                # If high similarity, consider it a duplicate
                if similarity_score > 0.7:  # 70% similarity threshold
                    duplicates.append((txn1, txn2, similarity_score, days_diff))
    
    return duplicates


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity between two strings using simple word overlap."""
    if not str1 or not str2:
        return 0.0
    
    words1 = set(str1.split())
    words2 = set(str2.split())
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity (intersection over union)
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0


def load_transactions(csv_path: str) -> list:
    """Load transactions from CSV file."""
    transactions = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date = datetime.strptime(row['date'], '%Y-%m-%d')
                amount = Decimal(row['amount'])
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'description': row['description'],
                    'account': row['account'],
                    'account_name': row['account_name'],
                    'account_type': row.get('account_type', 'debit'),
                    'institution': row['institution'],
                    'source_file': row.get('source_file', ''),
                })
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping invalid row: {e}", file=sys.stderr)
    
    return transactions


def analyze_duplicates(transactions: list):
    """Analyze and report duplicate transactions."""
    
    print("=" * 80)
    print("DUPLICATE TRANSACTION ANALYSIS")
    print("=" * 80)
    print()
    
    duplicates = find_spending_duplicates(transactions, max_days=3)
    
    if not duplicates:
        print("✅ No duplicate transactions found!")
        return
    
    print(f"🔍 Found {len(duplicates)} potential duplicate transaction pairs:")
    print()
    
    # Sort by similarity score (highest first)
    duplicates.sort(key=lambda x: x[2], reverse=True)
    
    total_duplicate_amount = Decimal('0')
    
    for i, (txn1, txn2, similarity, days_diff) in enumerate(duplicates, 1):
        print(f"#{i} - Similarity: {similarity:.1%}, Days apart: {days_diff}")
        print(f"  {txn1['date'].strftime('%Y-%m-%d')} ${abs(txn1['amount']):>8,.2f} {txn1['institution']:10} {txn1['description'][:50]}")
        print(f"  {txn2['date'].strftime('%Y-%m-%d')} ${abs(txn2['amount']):>8,.2f} {txn2['institution']:10} {txn2['description'][:50]}")
        
        # Show source files if available
        if txn1.get('source_file') and txn2.get('source_file'):
            file1 = txn1['source_file'].split('/')[-1]  # Just filename
            file2 = txn2['source_file'].split('/')[-1]
            print(f"  Sources: {file1} | {file2}")
        
        print()
        
        # Add to total (use the larger amount to be conservative)
        duplicate_amount = max(abs(txn1['amount']), abs(txn2['amount']))
        total_duplicate_amount += duplicate_amount
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total duplicate pairs found: {len(duplicates)}")
    print(f"Estimated duplicate spending: ${total_duplicate_amount:,.2f}")
    print()
    print("RECOMMENDATIONS:")
    print("• Review high-similarity pairs (>90%) for definite duplicates")
    print("• Check if transactions from PDF and QFX files represent same purchases")
    print("• Consider implementing deduplication in data processing pipeline")
    print("• Manual review recommended for pairs with 70-90% similarity")
    print()


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
    print()
    
    analyze_duplicates(transactions)


if __name__ == '__main__':
    main()