#!/usr/bin/env python3
"""Debug script to test duplicate detection logic."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from kiro_budget.parsers.qfx_parser import QFXParser
from kiro_budget.parsers.pdf_parser import PDFParser
from kiro_budget.models.core import ParserConfig
from kiro_budget.utils.error_handler import ErrorHandler
from kiro_budget.utils.duplicate_detector import DuplicateDetector

def test_duplicate_detection():
    """Test duplicate detection on the parsed transactions"""
    
    # Initialize parsers
    config = ParserConfig()
    error_handler = ErrorHandler("logs")
    
    qfx_parser = QFXParser(config, error_handler)
    pdf_parser = PDFParser(config)
    
    # Parse both files
    qfx_file = os.path.join(os.path.dirname(__file__), '..', '..', "raw/chase/Chase8147_Activity20251005_20251104_20251229.QFX")
    pdf_file = os.path.join(os.path.dirname(__file__), '..', '..', "raw/chase/20251104-statements-8147-.pdf")
    
    print("Parsing files...")
    qfx_transactions = qfx_parser.parse(qfx_file)
    pdf_transactions = pdf_parser.parse(pdf_file)
    
    print(f"QFX: {len(qfx_transactions)} transactions")
    print(f"PDF: {len(pdf_transactions)} transactions")
    
    # Test duplicate detection
    duplicate_detector = DuplicateDetector(date_tolerance_days=3, amount_tolerance=0.01)
    
    # Combine all transactions
    all_transactions = qfx_transactions + pdf_transactions
    print(f"Total combined: {len(all_transactions)} transactions")
    
    # Test signature generation for a few transactions
    print("\n=== Testing signature generation ===")
    for i, txn in enumerate(all_transactions[:5]):
        signature = duplicate_detector._generate_transaction_signature(txn)
        normalized_desc = duplicate_detector._normalize_description(txn.description or "")
        print(f"{i+1}. {txn.date.strftime('%Y-%m-%d')} | {txn.amount:8.2f} | {txn.description[:30]:<30} | Sig: {signature} | Norm: '{normalized_desc}'")
    
    # Test duplicate detection with fuzzy matching
    print("\n=== Testing fuzzy duplicate detection ===")
    duplicate_groups_fuzzy = duplicate_detector.detect_duplicates(all_transactions, ignore_transaction_ids=True)
    print(f"Found {len(duplicate_groups_fuzzy)} duplicate groups with fuzzy matching")
    
    if duplicate_groups_fuzzy:
        print("\nFuzzy duplicate groups:")
        for signature, duplicates in list(duplicate_groups_fuzzy.items())[:5]:  # Show first 5 groups
            print(f"\nGroup '{signature}' ({len(duplicates)} transactions):")
            for txn in duplicates:
                source = "QFX" if txn in qfx_transactions else "PDF"
                print(f"  {source}: {txn.date.strftime('%Y-%m-%d')} | {txn.amount:8.2f} | {txn.description}")
    
    # Find duplicates
    print("\n=== Detecting duplicates ===")
    duplicate_groups = duplicate_detector.detect_duplicates(all_transactions)
    print(f"Found {len(duplicate_groups)} duplicate groups")
    
    if duplicate_groups:
        print("\nDuplicate groups:")
        for signature, duplicates in list(duplicate_groups.items())[:5]:  # Show first 5 groups
            print(f"\nGroup '{signature}' ({len(duplicates)} transactions):")
            for txn in duplicates:
                source = "QFX" if txn in qfx_transactions else "PDF"
                print(f"  {source}: {txn.date.strftime('%Y-%m-%d')} | {txn.amount:8.2f} | {txn.description}")
    
    # Test deduplication with fuzzy matching
    print("\n=== Testing fuzzy deduplication ===")
    deduplicated_fuzzy, stats_fuzzy = duplicate_detector.deduplicate_transactions(all_transactions, use_fuzzy_matching=True)
    print(f"Original: {stats_fuzzy['total_input_transactions']} transactions")
    print(f"Duplicate groups: {stats_fuzzy['duplicate_groups_found']}")
    print(f"Duplicates removed: {stats_fuzzy['total_duplicates_removed']}")
    print(f"Final count: {stats_fuzzy['final_transaction_count']}")
    
    # Test deduplication
    print("\n=== Testing deduplication ===")
    deduplicated, stats = duplicate_detector.deduplicate_transactions(all_transactions)
    print(f"Original: {stats['total_input_transactions']} transactions")
    print(f"Duplicate groups: {stats['duplicate_groups_found']}")
    print(f"Duplicates removed: {stats['total_duplicates_removed']}")
    print(f"Final count: {stats['final_transaction_count']}")
    
    # Test specific transaction pairs that should match
    print("\n=== Testing specific matches ===")
    
    # Find TST*MERCURYS COFFEE transactions
    mercurys_qfx = [t for t in qfx_transactions if 'mercurys coffee' in (t.description or "").lower()]
    mercurys_pdf = [t for t in pdf_transactions if 'mercurys coffee' in (t.description or "").lower()]
    
    if mercurys_qfx and mercurys_pdf:
        qfx_txn = mercurys_qfx[0]
        pdf_txn = mercurys_pdf[0]
        
        print(f"QFX Mercury's: {qfx_txn.date} | {qfx_txn.amount} | '{qfx_txn.description}'")
        print(f"PDF Mercury's: {pdf_txn.date} | {pdf_txn.amount} | '{pdf_txn.description}'")
        
        qfx_sig = duplicate_detector._generate_transaction_signature(qfx_txn)
        pdf_sig = duplicate_detector._generate_transaction_signature(pdf_txn)
        
        print(f"QFX signature: {qfx_sig}")
        print(f"PDF signature: {pdf_sig}")
        print(f"Signatures match: {qfx_sig == pdf_sig}")
        
        # Test manual matching
        match_result = duplicate_detector._transactions_match(qfx_txn, pdf_txn)
        print(f"Manual match test: {match_result}")
        
        # Test normalized descriptions
        qfx_norm = duplicate_detector._normalize_description(qfx_txn.description)
        pdf_norm = duplicate_detector._normalize_description(pdf_txn.description)
        print(f"QFX normalized: '{qfx_norm}'")
        print(f"PDF normalized: '{pdf_norm}'")
        print(f"Normalized descriptions match: {qfx_norm == pdf_norm}")

if __name__ == "__main__":
    test_duplicate_detection()