"""Automatic transaction sign detection and correction utility.

This module provides automatic detection of transaction signs based on file analysis
and account types. It ensures consistent sign convention across all parsers:
- Spending transactions (debits) are negative
- Income/deposits (credits) are positive
- Transfers from account are negative
- Transfers to account are positive
"""

import logging
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Set
from collections import Counter
import re

from ..models.core import Transaction, AccountConfig


logger = logging.getLogger(__name__)


class TransactionSignDetector:
    """Detects and corrects transaction signs based on file analysis and account types."""
    
    # Keywords that indicate spending/debit transactions
    SPENDING_KEYWORDS = {
        'purchase', 'fee', 'interest', 'charge', 'penalty', 'late',
        'withdrawal', 'atm', 'pos', 'debit', 'bill', 'subscription', 'grocery',
        'restaurant', 'gas', 'fuel', 'shopping', 'store', 'market', 'pharmacy',
        'medical', 'insurance', 'rent', 'mortgage', 'loan', 'tax', 'fine'
    }
    
    # Keywords that indicate income/credit transactions
    INCOME_KEYWORDS = {
        'deposit', 'credit', 'refund', 'return', 'cashback', 'reward', 'rebate',
        'salary', 'payroll', 'dividend', 'interest earned', 'bonus', 'transfer in',
        'incoming', 'received', 'thank you', 'adjustment credit', 'reversal'
    }
    
    # Keywords that indicate transfers
    TRANSFER_OUT_KEYWORDS = {
        'transfer to', 'transfer out', 'outgoing transfer', 'wire out', 'send',
        'transfer debit'
    }
    
    TRANSFER_IN_KEYWORDS = {
        'transfer from', 'transfer in', 'incoming transfer', 'wire in', 'receive',
        'transfer credit', 'deposit from'
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_file_sign_convention(self, transactions: List[Transaction]) -> Dict[str, any]:
        """Analyze a file's transactions to determine the sign convention used.
        
        Args:
            transactions: List of transactions from a single file
            
        Returns:
            Dict containing analysis results:
            - convention: 'banking' or 'credit_card' or 'mixed' or 'unknown'
            - confidence: float 0-1 indicating confidence in detection
            - spending_positive_ratio: ratio of spending transactions with positive amounts
            - income_positive_ratio: ratio of income transactions with positive amounts
            - total_transactions: total number of transactions analyzed
        """
        if not transactions:
            return {
                'convention': 'unknown',
                'confidence': 0.0,
                'spending_positive_ratio': 0.0,
                'income_positive_ratio': 0.0,
                'total_transactions': 0
            }
        
        spending_amounts = []
        income_amounts = []
        
        for transaction in transactions:
            transaction_type = self._classify_transaction_type(transaction.description)
            
            if transaction_type == 'spending':
                spending_amounts.append(transaction.amount)
            elif transaction_type == 'income':
                income_amounts.append(transaction.amount)
        
        # Calculate ratios
        spending_positive_ratio = 0.0
        if spending_amounts:
            positive_spending = sum(1 for amt in spending_amounts if amt > 0)
            spending_positive_ratio = positive_spending / len(spending_amounts)
        
        income_positive_ratio = 0.0
        if income_amounts:
            positive_income = sum(1 for amt in income_amounts if amt > 0)
            income_positive_ratio = positive_income / len(income_amounts)
        
        # Determine convention based on ratios
        convention, confidence = self._determine_convention(
            spending_positive_ratio, income_positive_ratio,
            len(spending_amounts), len(income_amounts)
        )
        
        return {
            'convention': convention,
            'confidence': confidence,
            'spending_positive_ratio': spending_positive_ratio,
            'income_positive_ratio': income_positive_ratio,
            'total_transactions': len(transactions),
            'spending_count': len(spending_amounts),
            'income_count': len(income_amounts)
        }
    
    def _classify_transaction_type(self, description: str) -> str:
        """Classify transaction type based on description keywords.
        
        Args:
            description: Transaction description text
            
        Returns:
            'spending', 'income', 'transfer_out', 'transfer_in', or 'unknown'
        """
        if not description:
            return 'unknown'
        
        desc_lower = description.lower()
        
        # Check for transfer keywords first (more specific)
        for keyword in self.TRANSFER_OUT_KEYWORDS:
            if keyword in desc_lower:
                return 'transfer_out'
        
        for keyword in self.TRANSFER_IN_KEYWORDS:
            if keyword in desc_lower:
                return 'transfer_in'
        
        # Check for income keywords first (they tend to be more specific)
        for keyword in self.INCOME_KEYWORDS:
            if keyword in desc_lower:
                return 'income'
        
        # Check for spending keywords (use word boundaries for short keywords)
        for keyword in self.SPENDING_KEYWORDS:
            if len(keyword) <= 3:
                # Use word boundaries for short keywords like 'pos', 'atm', 'fee'
                import re
                if re.search(r'\b' + re.escape(keyword) + r'\b', desc_lower):
                    return 'spending'
            else:
                # Use simple substring match for longer keywords
                if keyword in desc_lower:
                    return 'spending'
        
        return 'unknown'
    
    def _determine_convention(self, spending_positive_ratio: float, income_positive_ratio: float,
                            spending_count: int, income_count: int) -> Tuple[str, float]:
        """Determine the sign convention based on spending/income ratios.
        
        Args:
            spending_positive_ratio: Ratio of spending transactions with positive amounts
            income_positive_ratio: Ratio of income transactions with positive amounts
            spending_count: Number of spending transactions
            income_count: Number of income transactions
            
        Returns:
            Tuple of (convention, confidence)
        """
        # Need minimum sample size for reliable detection
        min_sample_size = 3
        total_classified = spending_count + income_count
        
        if total_classified < min_sample_size:
            return 'unknown', 0.0
        
        # Banking convention: spending negative, income positive
        # Credit card convention: spending positive, income negative
        
        # Strong indicators for banking convention
        if (spending_positive_ratio <= 0.2 and income_positive_ratio >= 0.8 and
            spending_count >= 2 and income_count >= 1):
            confidence = min(0.9, 0.4 + (total_classified / 15))  # Higher confidence with more data
            return 'banking', confidence
        
        # Strong indicators for credit card convention
        if (spending_positive_ratio >= 0.8 and income_positive_ratio <= 0.2 and
            spending_count >= 2 and income_count >= 1):
            confidence = min(0.9, 0.4 + (total_classified / 15))
            return 'credit_card', confidence
        
        # Moderate indicators for banking convention
        if spending_positive_ratio <= 0.3 and income_positive_ratio >= 0.6:
            confidence = min(0.7, 0.3 + (total_classified / 20))
            return 'banking', confidence
        
        # Moderate indicators for credit card convention
        if spending_positive_ratio >= 0.7 and income_positive_ratio <= 0.4:
            confidence = min(0.7, 0.3 + (total_classified / 20))
            return 'credit_card', confidence
        
        # Mixed or unclear patterns
        if abs(spending_positive_ratio - 0.5) < 0.3 or abs(income_positive_ratio - 0.5) < 0.3:
            return 'mixed', 0.2
        
        return 'unknown', 0.1
    
    def correct_transaction_signs(self, transactions: List[Transaction], 
                                account_config: Optional[AccountConfig] = None) -> List[Transaction]:
        """Correct transaction signs to follow banking convention.
        
        Args:
            transactions: List of transactions to correct
            account_config: Optional account configuration for additional context
            
        Returns:
            List of transactions with corrected signs
        """
        if not transactions:
            return transactions
        
        # Analyze the file's sign convention
        analysis = self.analyze_file_sign_convention(transactions)
        
        self.logger.info(f"Sign analysis: {analysis}")
        
        # If confidence is too low, don't make changes
        if analysis['confidence'] < 0.2:
            self.logger.warning(f"Low confidence ({analysis['confidence']:.2f}) in sign detection, "
                              f"keeping original signs")
            return transactions
        
        corrected_transactions = []
        
        for transaction in transactions:
            corrected_transaction = self._correct_single_transaction_sign(
                transaction, analysis, account_config
            )
            corrected_transactions.append(corrected_transaction)
        
        return corrected_transactions
    
    def _correct_single_transaction_sign(self, transaction: Transaction, 
                                       analysis: Dict[str, any],
                                       account_config: Optional[AccountConfig] = None) -> Transaction:
        """Correct the sign of a single transaction.
        
        Args:
            transaction: Transaction to correct
            analysis: File sign convention analysis
            account_config: Optional account configuration
            
        Returns:
            Transaction with corrected sign
        """
        # Create a copy to avoid modifying the original
        corrected = Transaction(
            date=transaction.date,
            amount=transaction.amount,
            description=transaction.description,
            account=transaction.account,
            institution=transaction.institution,
            transaction_id=transaction.transaction_id,
            category=transaction.category,
            balance=transaction.balance
        )
        
        # Classify the transaction type
        transaction_type = self._classify_transaction_type(transaction.description)
        
        # Apply sign correction based on detected convention
        if analysis['convention'] == 'credit_card' and analysis['confidence'] >= 0.5:
            corrected.amount = self._apply_credit_card_sign_correction(
                transaction.amount, transaction_type
            )
        elif analysis['convention'] == 'banking':
            # Already in banking convention, but validate
            corrected.amount = self._validate_banking_convention_sign(
                transaction.amount, transaction_type
            )
        
        # Log significant sign changes
        if corrected.amount != transaction.amount:
            self.logger.debug(f"Corrected sign for transaction: {transaction.description[:50]} "
                            f"from {transaction.amount} to {corrected.amount}")
        
        return corrected
    
    def _apply_credit_card_sign_correction(self, amount: Decimal, transaction_type: str) -> Decimal:
        """Apply credit card to banking convention sign correction.
        
        Credit card convention: spending positive, income negative
        Banking convention: spending negative, income positive
        """
        if transaction_type == 'spending':
            # Spending should be negative in banking convention
            return -abs(amount)
        elif transaction_type == 'income':
            # Income should be positive in banking convention
            return abs(amount)
        elif transaction_type == 'transfer_out':
            # Transfer out should be negative
            return -abs(amount)
        elif transaction_type == 'transfer_in':
            # Transfer in should be positive
            return abs(amount)
        else:
            # For unknown types, invert the sign (credit card to banking conversion)
            return -amount
    
    def _validate_banking_convention_sign(self, amount: Decimal, transaction_type: str) -> Decimal:
        """Validate that a transaction follows banking convention.
        
        Only makes corrections if there's a clear mismatch.
        """
        if transaction_type == 'spending' and amount > 0:
            # Spending should be negative
            self.logger.debug(f"Correcting positive spending amount: {amount}")
            return -amount
        elif transaction_type == 'income' and amount < 0:
            # Income should be positive
            self.logger.debug(f"Correcting negative income amount: {amount}")
            return -amount
        elif transaction_type == 'transfer_out' and amount > 0:
            # Transfer out should be negative
            self.logger.debug(f"Correcting positive transfer out amount: {amount}")
            return -amount
        elif transaction_type == 'transfer_in' and amount < 0:
            # Transfer in should be positive
            self.logger.debug(f"Correcting negative transfer in amount: {amount}")
            return -amount
        
        return amount