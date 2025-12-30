#!/usr/bin/env python3
"""Debug script to compare parsing results from QFX and PDF files."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from kiro_budget.parsers.qfx_parser import QFXParser
from kiro_budget.parsers.pdf_parser import PDFParser
from kiro_budget.models.core import ParserConfig
from kiro_budget.utils.error_handler import ErrorHandler

def compare_parsers():
    """Compare parsing results from both files"""
    
    # Initialize parsers
    config = ParserConfig()
    error_handler = ErrorHandler("logs")  # Use logs directory
    
    qfx_parser = QFXParser(config, error_handler)
    pdf_parser = PDFParser(config)  # PDF parser only takes config
    
    # Parse both files
    qfx_file = os.path.join(os.path.dirname(__file__), '..', '..', "raw/chase/Chase8147_Activity20251005_20251104_20251229.QFX")
    pdf_file = os.path.join(os.path.dirname(__file__), '..', '..', "raw/chase/20251104-statements-8147-.pdf")
    
    print("Parsing QFX file...")
    qfx_transactions = qfx_parser.parse(qfx_file)
    print(f"QFX parser found {len(qfx_transactions)} transactions")
    
    print("\nParsing PDF file...")
    pdf_transactions = pdf_parser.parse(pdf_file)
    print(f"PDF parser found {len(pdf_transactions)} transactions")
    
    # Show first few transactions from each
    print("\n=== QFX Transactions (first 10) ===")
    for i, txn in enumerate(qfx_transactions[:10]):
        print(f"{i+1:2d}. {txn.date} | {txn.amount:8.2f} | {txn.description[:50]:<50} | ID: {txn.transaction_id or 'None'}")
    
    print("\n=== PDF Transactions (first 10) ===")
    for i, txn in enumerate(pdf_transactions[:10]):
        print(f"{i+1:2d}. {txn.date} | {txn.amount:8.2f} | {txn.description[:50]:<50} | ID: {txn.transaction_id or 'None'}")
    
    # Look for potential matches
    print("\n=== Looking for potential matches ===")
    
    # Group by amount to find potential duplicates
    qfx_by_amount = {}
    for txn in qfx_transactions:
        amt = abs(txn.amount)
        if amt not in qfx_by_amount:
            qfx_by_amount[amt] = []
        qfx_by_amount[amt].append(txn)
    
    pdf_by_amount = {}
    for txn in pdf_transactions:
        amt = abs(txn.amount)
        if amt not in pdf_by_amount:
            pdf_by_amount[amt] = []
        pdf_by_amount[amt].append(txn)
    
    # Find common amounts
    common_amounts = set(qfx_by_amount.keys()) & set(pdf_by_amount.keys())
    print(f"Found {len(common_amounts)} amounts that appear in both files")
    
    # Show some examples
    for amt in sorted(list(common_amounts))[:5]:
        print(f"\nAmount: ${amt:.2f}")
        print("  QFX:")
        for txn in qfx_by_amount[amt][:2]:
            print(f"    {txn.date} | {txn.amount:8.2f} | {txn.description[:40]}")
        print("  PDF:")
        for txn in pdf_by_amount[amt][:2]:
            print(f"    {txn.date} | {txn.amount:8.2f} | {txn.description[:40]}")
    
    # Check date ranges
    qfx_dates = [txn.date for txn in qfx_transactions]
    pdf_dates = [txn.date for txn in pdf_transactions]
    
    print(f"\n=== Date Ranges ===")
    print(f"QFX: {min(qfx_dates)} to {max(qfx_dates)}")
    print(f"PDF: {min(pdf_dates)} to {max(pdf_dates)}")
    
    # Check for exact matches by description
    qfx_descriptions = set()
    for txn in qfx_transactions:
        desc = txn.description.lower().strip() if txn.description else ""
        qfx_descriptions.add(desc)
    
    pdf_descriptions = set()
    for txn in pdf_transactions:
        desc = txn.description.lower().strip() if txn.description else ""
        pdf_descriptions.add(desc)
    
    common_descriptions = qfx_descriptions & pdf_descriptions
    print(f"\n=== Description Analysis ===")
    print(f"QFX unique descriptions: {len(qfx_descriptions)}")
    print(f"PDF unique descriptions: {len(pdf_descriptions)}")
    print(f"Common descriptions: {len(common_descriptions)}")
    
    if common_descriptions:
        print("Sample common descriptions:")
        for desc in sorted(list(common_descriptions))[:5]:
            if desc:
                print(f"  '{desc[:50]}'")

if __name__ == "__main__":
    compare_parsers()