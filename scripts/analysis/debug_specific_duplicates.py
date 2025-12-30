#!/usr/bin/env python3
"""Debug specific duplicate cases."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from kiro_budget.parsers.qfx_parser import QFXParser
from kiro_budget.parsers.pdf_parser import PDFParser
from kiro_budget.models.core import ParserConfig
from kiro_budget.utils.error_handler import ErrorHandler
from kiro_budget.utils.duplicate_detector import DuplicateDetector

def debug_specific_cases():
    """Debug specific duplicate cases that should match"""
    
    # Initialize parsers
    config = ParserConfig()
    error_handler = ErrorHandler("logs")
    
    qfx_parser = QFXParser(config, error_handler)
    pdf_parser = PDFParser(config)
    
    # Parse both files
    qfx_file = os.path.join(os.path.dirname(__file__), '..', '..', "raw/chase/Chase8147_Activity20251005_20251104_20251229.QFX")
    pdf_file = os.path.join(os.path.dirname(__file__), '..', '..', "raw/chase/20251104-statements-8147-.pdf")
    
    qfx_transactions = qfx_parser.parse(qfx_file)
    pdf_transactions = pdf_parser.parse(pdf_file)
    
    duplicate_detector = DuplicateDetector(date_tolerance_days=3, amount_tolerance=0.01)
    
    # Find the Amazon NV46R2L51 transactions
    amazon_qfx = [t for t in qfx_transactions if 'nv46r2l51' in (t.description or "").lower()]
    amazon_pdf = [t for t in pdf_transactions if 'nv46r2l51' in (t.description or "").lower()]
    
    if amazon_qfx and amazon_pdf:
        qfx_txn = amazon_qfx[0]
        pdf_txn = amazon_pdf[0]
        
        print("=== Amazon NV46R2L51 Transaction Analysis ===")
        print(f"QFX: {qfx_txn.date} | {qfx_txn.amount} | '{qfx_txn.description}'")
        print(f"PDF: {pdf_txn.date} | {pdf_txn.amount} | '{pdf_txn.description}'")
        
        # Test signatures
        qfx_sig = duplicate_detector._generate_transaction_signature(qfx_txn, ignore_transaction_id=True)
        pdf_sig = duplicate_detector._generate_transaction_signature(pdf_txn, ignore_transaction_id=True)
        
        print(f"QFX fuzzy signature: {qfx_sig}")
        print(f"PDF fuzzy signature: {pdf_sig}")
        print(f"Signatures match: {qfx_sig == pdf_sig}")
        
        # Test normalized descriptions
        qfx_norm = duplicate_detector._normalize_description(qfx_txn.description)
        pdf_norm = duplicate_detector._normalize_description(pdf_txn.description)
        print(f"QFX normalized: '{qfx_norm}'")
        print(f"PDF normalized: '{pdf_norm}'")
        print(f"Normalized descriptions match: {qfx_norm == pdf_norm}")
        
        # Test date difference
        date_diff = abs((qfx_txn.date - pdf_txn.date).days)
        print(f"Date difference: {date_diff} days")
        print(f"Within tolerance: {date_diff <= duplicate_detector.date_tolerance_days}")
        
        # Test amount match
        amount_diff = abs(qfx_txn.amount - pdf_txn.amount)
        print(f"Amount difference: {amount_diff}")
        print(f"Within tolerance: {amount_diff <= duplicate_detector.amount_tolerance}")
        
        # Test manual matching
        match_result = duplicate_detector._transactions_match(qfx_txn, pdf_txn)
        print(f"Manual match test: {match_result}")
        
        # Debug signature generation components
        print("\n=== Signature Generation Debug ===")
        
        # QFX components
        qfx_date_str = qfx_txn.date.strftime("%Y-%m-%d")
        qfx_amount_str = f"{abs(qfx_txn.amount):.2f}"
        qfx_account_str = qfx_txn.account or ""
        qfx_signature_data = f"{qfx_date_str}|{qfx_amount_str}|{qfx_norm}|{qfx_account_str}"
        
        print(f"QFX signature data: '{qfx_signature_data}'")
        
        # PDF components
        pdf_date_str = pdf_txn.date.strftime("%Y-%m-%d")
        pdf_amount_str = f"{abs(pdf_txn.amount):.2f}"
        pdf_account_str = pdf_txn.account or ""
        pdf_signature_data = f"{pdf_date_str}|{pdf_amount_str}|{pdf_norm}|{pdf_account_str}"
        
        print(f"PDF signature data: '{pdf_signature_data}'")

if __name__ == "__main__":
    debug_specific_cases()