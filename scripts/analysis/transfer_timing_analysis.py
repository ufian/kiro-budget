#!/usr/bin/env python3
"""Analyze internal transfer timing patterns and lag distribution.

This script analyzes the timing patterns of internal transfers to understand:
- Distribution of processing lag (0-3 business days)
- Cross-month transfer impacts
- Unmatched transfers that might be due to timing lag
- Monthly balance discrepancies caused by transfer timing

Usage:
    python scripts/analysis/transfer_timing_analysis.py [input_csv]
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


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
                    'abs_amount': abs(amount),
                    'description': row['description'],
                    'account': row['account'],
                    'account_name': row['account_name'],
                    'account_type': row.get('account_type', 'debit'),
                    'institution': row['institution'],
                })
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping invalid row: {e}", file=sys.stderr)
    
    return transactions


def identify_transfer_transactions(transactions: list) -> list:
    """Identify transactions that are likely internal transfers."""
    transfer_patterns = [
        'transfer to ',
        'transfer from ',
        'to pocket',
        'from pocket',
        'deposit transfer from',
        'withdrawal transfer to',
        'payment thank you',
        'payment received',
        'payment transaction',
        'cardpymt',
        'applecard gsbank payment',
        'gsbank payment',
    ]
    
    transfer_txns = []
    for txn in transactions:
        desc_lower = txn['description'].lower()
        if any(pattern in desc_lower for pattern in transfer_patterns):
            transfer_txns.append(txn)
    
    return transfer_txns


def find_transfer_pairs_with_timing(transactions: list, max_business_days: int = 3) -> tuple:
    """Find transfer pairs and analyze timing patterns.
    
    Returns:
        (matched_pairs, unmatched_transfers, timing_stats)
    """
    transfer_txns = identify_transfer_transactions(transactions)
    
    # Group by absolute amount
    amount_groups = defaultdict(list)
    for txn in transfer_txns:
        amount_groups[str(txn['abs_amount'])].append(txn)
    
    matched_pairs = []
    matched_txn_ids = set()
    timing_stats = defaultdict(int)
    
    for amount, txns in amount_groups.items():
        if len(txns) < 2:
            continue
        
        # Look for potential transfer pairs
        for i, txn1 in enumerate(txns):
            if id(txn1) in matched_txn_ids:
                continue
                
            for txn2 in txns[i+1:]:
                if id(txn2) in matched_txn_ids:
                    continue
                
                # Skip if same institution AND same account (likely duplicates)
                if txn1['institution'] == txn2['institution'] and txn1['account'] == txn2['account']:
                    continue
                
                # Calculate business days between transactions
                days_diff = business_days_between(txn1['date'], txn2['date'])
                
                if days_diff <= max_business_days:
                    # Check if this looks like a transfer pair
                    if (txn1['amount'] < 0 and txn2['amount'] > 0) or \
                       (txn1['amount'] > 0 and txn2['amount'] < 0):
                        
                        # Determine source and destination
                        if txn1['amount'] < 0:
                            source_txn, dest_txn = txn1, txn2
                        else:
                            source_txn, dest_txn = txn2, txn1
                        
                        matched_pairs.append((source_txn, dest_txn, days_diff))
                        matched_txn_ids.add(id(txn1))
                        matched_txn_ids.add(id(txn2))
                        timing_stats[days_diff] += 1
                        break
    
    # Find unmatched transfers
    unmatched_transfers = [
        txn for txn in transfer_txns 
        if id(txn) not in matched_txn_ids
    ]
    
    return matched_pairs, unmatched_transfers, timing_stats


def analyze_cross_month_impacts(matched_pairs: list) -> dict:
    """Analyze how transfer timing affects monthly balances."""
    cross_month_impacts = defaultdict(lambda: {
        'outgoing_this_month': Decimal('0'),
        'incoming_next_month': Decimal('0'),
        'net_impact': Decimal('0'),
        'count': 0
    })
    
    for source_txn, dest_txn, days_diff in matched_pairs:
        source_month = source_txn['date'].strftime('%Y-%m')
        dest_month = dest_txn['date'].strftime('%Y-%m')
        
        if source_month != dest_month:
            # Cross-month transfer
            amount = source_txn['abs_amount']
            
            cross_month_impacts[source_month]['outgoing_this_month'] += amount
            cross_month_impacts[source_month]['net_impact'] -= amount
            cross_month_impacts[source_month]['count'] += 1
            
            cross_month_impacts[dest_month]['incoming_next_month'] += amount
            cross_month_impacts[dest_month]['net_impact'] += amount
    
    return cross_month_impacts


def print_timing_analysis(transactions: list):
    """Print comprehensive transfer timing analysis."""
    
    print("=" * 80)
    print("INTERNAL TRANSFER TIMING ANALYSIS")
    print("=" * 80)
    print()
    
    # Find transfer pairs and timing data
    matched_pairs, unmatched_transfers, timing_stats = find_transfer_pairs_with_timing(transactions)
    
    # Overall statistics
    total_transfers = len(identify_transfer_transactions(transactions))
    matched_count = len(matched_pairs) * 2  # Each pair represents 2 transactions
    unmatched_count = len(unmatched_transfers)
    
    print(f"📊 OVERALL STATISTICS")
    print("-" * 40)
    print(f"Total transfer transactions: {total_transfers}")
    print(f"Matched pairs: {len(matched_pairs)} pairs ({matched_count} transactions)")
    print(f"Unmatched transfers: {unmatched_count}")
    print(f"Match rate: {(matched_count / total_transfers * 100):.1f}%")
    print()
    
    # Timing distribution
    if timing_stats:
        print(f"⏱️  PROCESSING LAG DISTRIBUTION")
        print("-" * 40)
        total_pairs = sum(timing_stats.values())
        
        for days in sorted(timing_stats.keys()):
            count = timing_stats[days]
            percentage = (count / total_pairs) * 100
            lag_desc = "Same day" if days == 0 else f"{days} business day{'s' if days != 1 else ''}"
            print(f"{lag_desc:15}: {count:3d} pairs ({percentage:5.1f}%)")
        print()
    
    # Cross-month impact analysis
    cross_month_impacts = analyze_cross_month_impacts(matched_pairs)
    
    if cross_month_impacts:
        print(f"📅 CROSS-MONTH TRANSFER IMPACTS")
        print("-" * 40)
        print("Months with transfer timing effects:")
        print()
        
        for month in sorted(cross_month_impacts.keys()):
            data = cross_month_impacts[month]
            
            print(f"{month}:")
            if data['outgoing_this_month'] > 0:
                print(f"  Outgoing transfers (delayed receipt): ${data['outgoing_this_month']:,.2f}")
            if data['incoming_next_month'] > 0:
                print(f"  Incoming transfers (from prev month): ${data['incoming_next_month']:,.2f}")
            
            net_impact = data['net_impact']
            if net_impact != 0:
                direction = "understated" if net_impact < 0 else "overstated"
                print(f"  Net monthly impact: ${abs(net_impact):,.2f} ({direction})")
            print()
    
    # Unmatched transfers analysis
    if unmatched_transfers:
        print(f"❓ UNMATCHED TRANSFERS")
        print("-" * 40)
        print(f"Found {len(unmatched_transfers)} unmatched transfer transactions:")
        print("(These might be transfers with >3 day lag, external transfers, or data issues)")
        print()
        
        # Group by month for better analysis
        unmatched_by_month = defaultdict(list)
        for txn in unmatched_transfers:
            month = txn['date'].strftime('%Y-%m')
            unmatched_by_month[month].append(txn)
        
        for month in sorted(unmatched_by_month.keys()):
            txns = unmatched_by_month[month]
            total_amount = sum(abs(txn['amount']) for txn in txns)
            
            print(f"{month}: {len(txns)} transactions, ${total_amount:,.2f} total")
            
            # Show top 3 by amount
            sorted_txns = sorted(txns, key=lambda x: x['abs_amount'], reverse=True)
            for txn in sorted_txns[:3]:
                sign = "+" if txn['amount'] > 0 else "-"
                print(f"  {txn['date'].strftime('%Y-%m-%d')} {sign}${txn['abs_amount']:>8,.2f} "
                      f"{txn['institution']:10} {txn['description'][:35]}")
            
            if len(txns) > 3:
                print(f"  ... and {len(txns) - 3} more")
            print()
    
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if cross_month_impacts:
        print("• Monthly reports may show imbalanced internal transfers due to 3-day processing lag")
        print("• Consider using quarterly or annual summaries for more accurate transfer analysis")
    
    if unmatched_count > matched_count * 0.2:  # More than 20% unmatched
        print("• High number of unmatched transfers detected - review for:")
        print("  - Transfers with >3 business day lag")
        print("  - External transfers misclassified as internal")
        print("  - Missing transaction data")
    
    if timing_stats.get(0, 0) < sum(timing_stats.values()) * 0.5:  # Less than 50% same-day
        print("• Most transfers have processing lag - account for this in cash flow planning")
    
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
    
    print_timing_analysis(transactions)


if __name__ == '__main__':
    main()