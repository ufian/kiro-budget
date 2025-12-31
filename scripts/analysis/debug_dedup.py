#!/usr/bin/env python3
"""Debug deduplication issue."""

from kiro_budget.utils.duplicate_detector import DuplicateDetector
from kiro_budget.utils.importer import TransactionImporter
from kiro_budget.models.core import Transaction, EnrichedTransaction
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Create importer
importer = TransactionImporter(
    data_directory='kiro-budget/data',
    output_directory='kiro-budget/data/total'
)

# Scan all files
source_files = importer.scan_source_files()
print(f"Found {len(source_files)} source files")

# Load all transactions
all_transactions = []
for file_path in source_files:
    importer.validate_csv_structure(file_path)
    transactions = importer.load_transactions(file_path)
    all_transactions.extend(transactions)
    
print(f"Total transactions loaded: {len(all_transactions)}")

# Find the specific transaction before dedup
target_id = '20251103155031820251103503621000027846827'
matches_before = [t for t in all_transactions if t.transaction_id == target_id]
print(f"Target transaction count BEFORE dedup: {len(matches_before)}")

# Deduplicate
deduped, stats = importer.deduplicate_transactions(all_transactions)
print(f"After dedup: {len(deduped)}")
print(f"Stats: {stats}")

# Find the specific transaction after dedup
matches_after = [t for t in deduped if t.transaction_id == target_id]
print(f"Target transaction count AFTER dedup: {len(matches_after)}")

# Check if there are other duplicates with same transaction_id
from collections import Counter
txn_ids = [t.transaction_id for t in deduped if t.transaction_id]
id_counts = Counter(txn_ids)
duplicated_ids = {k: v for k, v in id_counts.items() if v > 1}
print(f"\nTransaction IDs that appear more than once: {len(duplicated_ids)}")
for tid, count in list(duplicated_ids.items())[:5]:
    print(f"  {tid[:40]}...: {count} times")
