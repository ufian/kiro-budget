#!/usr/bin/env python3
"""Remove PDF vs QFX duplicate transactions from the total CSV file.

This script specifically targets duplicates where the same transaction appears
in both PDF statements and QFX files from the same institution, with slight
variations in merchant names and 1-3 day timing differences.

Usage:
    python scripts/export/remove_pdf_qfx_duplicates.py [input_csv] [output_csv]
"""

import csv
import sys
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


def normalize_merchant_name(description: str) -> str:
    """Normalize merchant names for better duplicate detection."""
    if not description:
        return ""
    
    desc = description.lower().strip()
    
    # Remove common prefixes
    prefixes = ['tst* ', 'sq *', 'sp *', 'pos ', 'debit ', 'credit ']
    for prefix in prefixes:
        if desc.startswith(prefix):
            desc = desc[len(prefix):].strip()
    
    # Remove store numbers and location info
    desc = re.sub(r'#\d+', '', desc)  # Remove "#1029", "#0658"
    desc = re.sub(r'\s+\d+\s+[nsew]{1,2}\s+\w+.*$', '', desc, flags=re.IGNORECASE)  # Remove location
    desc = re.sub(r'\s+[a-z]+\s+wa\s*$', '', desc, flags=re.IGNORECASE)  # Remove "city WA"
    desc = re.sub(r'\s+\(\s*\d*\s*$', '', desc)  # Remove trailing "( 131-27305592 IL"
    
    # Clean up whitespace
    desc = ' '.join(desc.split())
    
    return desc


def find_pdf_qfx_duplicates(transactions: list, max_days: int = 3) -> list:
    """Find duplicates between PDF and QFX files from same institution."""
    duplicates = []
    
    # Group by institution and amount for efficiency
    by_institution_amount = defaultdict(list)
    
    for i, txn in enumerate(transactions):
        # Only look at spending transactions (negative amounts)
        if txn['amount'] >= 0:
            continue
            
        # Group by institution and rounded amount
        key = (txn['institution'].lower(), round(abs(txn['amount']), 2))
        by_institution_amount[key].append((i, txn))
    
    # Look for duplicates within each group
    for (institution, amount), txn_list in by_institution_amount.items():
        if len(txn_list) < 2:
            continue
            
        # Check all pairs in this group
        for i, (idx1, txn1) in enumerate(txn_list):
            for idx2, txn2 in txn_list[i+1:]:
                # Check if one is from PDF and other from QFX
                source1 = txn1.get('source_file', '').lower()
                source2 = txn2.get('source_file', '').lower()
                
                is_pdf_qfx_pair = (
                    ('.pdf.' in source1 and '.qfx.' in source2) or
                    ('.qfx.' in source1 and '.pdf.' in source2)
                )
                
                if not is_pdf_qfx_pair:
                    continue
                
                # Check date proximity
                days_diff = abs((txn1['date'] - txn2['date']).days)
                if days_diff > max_days:
                    continue
                
                # Check exact amount match
                if abs(txn1['amount'] - txn2['amount']) > Decimal('0.01'):
                    continue
                
                # Check merchant name similarity
                merchant1 = normalize_merchant_name(txn1['description'])
                merchant2 = normalize_merchant_name(txn2['description'])
                
                # Calculate similarity
                if merchant1 and merchant2:
                    words1 = set(merchant1.split())
                    words2 = set(merchant2.split())
                    
                    if words1 and words2:
                        intersection = len(words1.intersection(words2))
                        union = len(words1.union(words2))
                        similarity = intersection / union if union > 0 else 0
                        
                        # High similarity threshold for definite duplicates
                        if similarity >= 0.7:
                            # Prefer QFX over PDF (more detailed data)
                            if '.qfx.' in source1:
                                duplicates.append((idx2, txn2, idx1, txn1, similarity, days_diff))  # Remove PDF, keep QFX
                            else:
                                duplicates.append((idx1, txn1, idx2, txn2, similarity, days_diff))  # Remove PDF, keep QFX
    
    return duplicates


def remove_duplicates_from_csv(input_csv: str, output_csv: str):
    """Remove PDF vs QFX duplicates from CSV file."""
    
    print(f"Loading transactions from: {input_csv}")
    
    # Load transactions
    transactions = []
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            try:
                row['date'] = datetime.strptime(row['date'], '%Y-%m-%d')
                row['amount'] = Decimal(row['amount'])
                transactions.append(row)
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping invalid row: {e}")
    
    print(f"Loaded {len(transactions)} transactions")
    
    # Find duplicates
    print("Finding PDF vs QFX duplicates...")
    duplicates = find_pdf_qfx_duplicates(transactions, max_days=3)
    
    if not duplicates:
        print("No PDF vs QFX duplicates found!")
        return
    
    print(f"Found {len(duplicates)} PDF vs QFX duplicate pairs:")
    
    # Show what will be removed
    indices_to_remove = set()
    total_amount_removed = Decimal('0')
    
    for remove_idx, remove_txn, keep_idx, keep_txn, similarity, days_diff in duplicates:
        indices_to_remove.add(remove_idx)
        total_amount_removed += abs(remove_txn['amount'])
        
        print(f"  Removing: {remove_txn['date'].strftime('%Y-%m-%d')} ${abs(remove_txn['amount']):>8,.2f} {remove_txn['description'][:40]}")
        print(f"  Keeping:  {keep_txn['date'].strftime('%Y-%m-%d')} ${abs(keep_txn['amount']):>8,.2f} {keep_txn['description'][:40]}")
        print(f"  Similarity: {similarity:.1%}, Days apart: {days_diff}")
        print()
    
    # Remove duplicates
    filtered_transactions = [
        txn for i, txn in enumerate(transactions) 
        if i not in indices_to_remove
    ]
    
    print(f"Removed {len(indices_to_remove)} duplicate transactions")
    print(f"Total duplicate spending removed: ${total_amount_removed:,.2f}")
    print(f"Final transaction count: {len(filtered_transactions)}")
    
    # Save filtered transactions
    print(f"Saving deduplicated data to: {output_csv}")
    
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for txn in filtered_transactions:
            # Convert back to strings for CSV
            row = txn.copy()
            row['date'] = txn['date'].strftime('%Y-%m-%d')
            row['amount'] = str(txn['amount'])
            writer.writerow(row)
    
    print("Deduplication completed successfully!")


def main():
    # Default paths
    input_csv = 'data/total/all_transactions.csv'
    output_csv = 'data/total/all_transactions_deduplicated.csv'
    
    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
    if len(sys.argv) > 2:
        output_csv = sys.argv[2]
    
    if not Path(input_csv).exists():
        print(f"Error: Input file not found: {input_csv}")
        sys.exit(1)
    
    remove_duplicates_from_csv(input_csv, output_csv)


if __name__ == '__main__':
    main()