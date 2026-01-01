"""Tests for the TransactionSignDetector utility."""

import pytest
from datetime import datetime
from decimal import Decimal

from src.kiro_budget.utils.sign_detector import TransactionSignDetector
from src.kiro_budget.models.core import Transaction, AccountConfig


class TestTransactionSignDetector:
    """Test cases for TransactionSignDetector"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = TransactionSignDetector()
    
    def create_transaction(self, amount: str, description: str) -> Transaction:
        """Helper to create test transactions"""
        return Transaction(
            date=datetime(2024, 1, 15),
            amount=Decimal(amount),
            description=description,
            account="1234",
            institution="test"
        )
    
    def test_classify_transaction_type_spending(self):
        """Test classification of spending transactions"""
        spending_descriptions = [
            "PURCHASE AT GROCERY STORE",
            "ATM WITHDRAWAL",
            "MONTHLY FEE",
            "INTEREST CHARGE",
            "LATE PENALTY",
            "RESTAURANT BILL PAYMENT"
        ]
        
        for desc in spending_descriptions:
            transaction_type = self.detector._classify_transaction_type(desc)
            assert transaction_type == 'spending', f"Failed to classify '{desc}' as spending"
    
    def test_classify_transaction_type_income(self):
        """Test classification of income transactions"""
        income_descriptions = [
            "SALARY DEPOSIT",
            "DIVIDEND PAYMENT", 
            "REFUND FROM STORE",
            "CASHBACK REWARD",
            "INTEREST EARNED",
            "PAYMENT THANK YOU"  # Changed from "THANK YOU PAYMENT"
        ]
        
        for desc in income_descriptions:
            transaction_type = self.detector._classify_transaction_type(desc)
            assert transaction_type == 'income', f"Failed to classify '{desc}' as income"
    
    def test_classify_transaction_type_transfers(self):
        """Test classification of transfer transactions"""
        transfer_out_descriptions = [
            "TRANSFER TO SAVINGS",
            "OUTGOING TRANSFER", 
            "WIRE OUT TO ACCOUNT"
        ]
        
        transfer_in_descriptions = [
            "TRANSFER FROM CHECKING",
            "INCOMING TRANSFER",
            "WIRE IN FROM ACCOUNT",
            "DEPOSIT FROM SAVINGS"
        ]
        
        for desc in transfer_out_descriptions:
            transaction_type = self.detector._classify_transaction_type(desc)
            assert transaction_type == 'transfer_out', f"Failed to classify '{desc}' as transfer_out"
        
        for desc in transfer_in_descriptions:
            transaction_type = self.detector._classify_transaction_type(desc)
            assert transaction_type == 'transfer_in', f"Failed to classify '{desc}' as transfer_in"
    
    def test_analyze_banking_convention_file(self):
        """Test analysis of file following banking convention"""
        transactions = [
            self.create_transaction("-50.00", "GROCERY STORE PURCHASE"),
            self.create_transaction("-25.00", "ATM WITHDRAWAL"),
            self.create_transaction("1000.00", "SALARY DEPOSIT"),
            self.create_transaction("10.00", "INTEREST EARNED"),
            self.create_transaction("-15.00", "MONTHLY FEE")
        ]
        
        analysis = self.detector.analyze_file_sign_convention(transactions)
        
        assert analysis['convention'] == 'banking'
        assert analysis['confidence'] > 0.5
        assert analysis['spending_positive_ratio'] == 0.0  # All spending is negative
        assert analysis['income_positive_ratio'] == 1.0   # All income is positive
    
    def test_analyze_credit_card_convention_file(self):
        """Test analysis of file following credit card convention"""
        transactions = [
            self.create_transaction("50.00", "GROCERY STORE PURCHASE"),
            self.create_transaction("25.00", "ATM WITHDRAWAL"),
            self.create_transaction("-1000.00", "PAYMENT THANK YOU"),
            self.create_transaction("-10.00", "CASHBACK REWARD"),
            self.create_transaction("15.00", "MONTHLY FEE")
        ]
        
        analysis = self.detector.analyze_file_sign_convention(transactions)
        
        assert analysis['convention'] == 'credit_card'
        assert analysis['confidence'] > 0.5
        assert analysis['spending_positive_ratio'] == 1.0  # All spending is positive
        assert analysis['income_positive_ratio'] == 0.0   # All income is negative
    
    def test_analyze_mixed_convention_file(self):
        """Test analysis of file with mixed sign conventions"""
        transactions = [
            self.create_transaction("50.00", "GROCERY STORE PURCHASE"),
            self.create_transaction("-25.00", "ATM WITHDRAWAL"),
            self.create_transaction("1000.00", "SALARY DEPOSIT"),
            self.create_transaction("-10.00", "INTEREST EARNED")
        ]
        
        analysis = self.detector.analyze_file_sign_convention(transactions)
        
        assert analysis['convention'] in ['mixed', 'unknown']
        assert analysis['confidence'] < 0.5
    
    def test_correct_credit_card_to_banking_signs(self):
        """Test correction of credit card convention to banking convention"""
        transactions = [
            self.create_transaction("50.00", "GROCERY STORE PURCHASE"),  # Should become -50.00
            self.create_transaction("25.00", "RESTAURANT BILL"),         # Should become -25.00
            self.create_transaction("-1000.00", "PAYMENT THANK YOU"),    # Should become +1000.00
            self.create_transaction("-10.00", "CASHBACK REWARD"),        # Should become +10.00
            self.create_transaction("15.00", "MONTHLY FEE"),             # Should become -15.00
            self.create_transaction("100.00", "UNKNOWN TRANSACTION")     # Should become -100.00 (all signs flipped)
        ]
        
        corrected = self.detector.correct_transaction_signs(transactions)
        
        # ALL transactions should have their signs flipped (credit card to banking conversion)
        expected_amounts = [
            Decimal('-50.00'),   # Was +50.00
            Decimal('-25.00'),   # Was +25.00
            Decimal('1000.00'),  # Was -1000.00
            Decimal('10.00'),    # Was -10.00
            Decimal('-15.00'),   # Was +15.00
            Decimal('-100.00')   # Was +100.00
        ]
        
        for i, (transaction, expected) in enumerate(zip(corrected, expected_amounts)):
            assert transaction.amount == expected, \
                f"Transaction {i} should be {expected}, got {transaction.amount}: {transaction.description}"
    
    def test_correct_banking_convention_validation(self):
        """Test that banking convention files are left unchanged"""
        transactions = [
            self.create_transaction("-50.00", "GROCERY STORE PURCHASE"),
            self.create_transaction("-25.00", "ATM WITHDRAWAL"),
            self.create_transaction("1000.00", "SALARY DEPOSIT"),
            self.create_transaction("10.00", "INTEREST EARNED")
        ]
        
        corrected = self.detector.correct_transaction_signs(transactions)
        
        # Should remain unchanged since already in banking convention
        for original, corrected_tx in zip(transactions, corrected):
            assert original.amount == corrected_tx.amount, \
                f"Banking convention transaction should not change: {original.description}"
    
    def test_low_confidence_no_changes(self):
        """Test that low confidence analysis doesn't make changes"""
        # Create transactions with unclear patterns
        transactions = [
            self.create_transaction("50.00", "UNKNOWN TRANSACTION"),
            self.create_transaction("-25.00", "MISC CHARGE")
        ]
        
        corrected = self.detector.correct_transaction_signs(transactions)
        
        # Should remain unchanged due to low confidence
        for original, corrected_tx in zip(transactions, corrected):
            assert original.amount == corrected_tx.amount, \
                "Low confidence should not change transaction signs"
    
    def test_empty_transactions_list(self):
        """Test handling of empty transactions list"""
        transactions = []
        corrected = self.detector.correct_transaction_signs(transactions)
        assert corrected == []
    
    def test_single_transaction(self):
        """Test handling of single transaction (should have low confidence)"""
        transactions = [self.create_transaction("50.00", "GROCERY STORE PURCHASE")]
        corrected = self.detector.correct_transaction_signs(transactions)
        
        # Should remain unchanged due to insufficient data
        assert corrected[0].amount == transactions[0].amount
    
    def test_determine_convention_edge_cases(self):
        """Test edge cases in convention determination"""
        # Test with minimum sample size
        spending_positive_ratio = 1.0
        income_positive_ratio = 0.0
        spending_count = 2
        income_count = 2
        
        convention, confidence = self.detector._determine_convention(
            spending_positive_ratio, income_positive_ratio, spending_count, income_count
        )
        
        assert convention == 'credit_card'
        assert confidence > 0.5
        
        # Test with insufficient sample size
        convention, confidence = self.detector._determine_convention(
            1.0, 0.0, 1, 1
        )
        
        assert convention == 'unknown'
        assert confidence == 0.0
    
    def test_flip_all_signs_for_credit_card_file(self):
        """Test that ALL signs are flipped when credit card convention is detected with high confidence."""
        # Create a clear credit card file pattern
        transactions = [
            self.create_transaction("50.00", "GROCERY STORE PURCHASE"),    # Spending positive
            self.create_transaction("25.00", "RESTAURANT BILL"),           # Spending positive  
            self.create_transaction("15.00", "MONTHLY FEE"),               # Spending positive
            self.create_transaction("-1000.00", "PAYMENT THANK YOU"),      # Payment negative
            self.create_transaction("-10.00", "CASHBACK REWARD"),          # Cashback negative
            self.create_transaction("200.00", "SOME UNKNOWN TRANSACTION"), # Unknown transaction
            self.create_transaction("-5.00", "ANOTHER UNKNOWN TRANSACTION") # Unknown transaction
        ]
        
        corrected = self.detector.correct_transaction_signs(transactions)
        
        # ALL transactions should have flipped signs
        expected_amounts = [
            Decimal('-50.00'),   # Was +50.00
            Decimal('-25.00'),   # Was +25.00  
            Decimal('-15.00'),   # Was +15.00
            Decimal('1000.00'),  # Was -1000.00
            Decimal('10.00'),    # Was -10.00
            Decimal('-200.00'),  # Was +200.00 (unknown but flipped)
            Decimal('5.00')      # Was -5.00 (unknown but flipped)
        ]
        
        for i, (transaction, expected) in enumerate(zip(corrected, expected_amounts)):
            assert transaction.amount == expected, \
                f"Transaction {i} should be {expected}, got {transaction.amount}: {transaction.description}"