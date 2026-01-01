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
        
        # Check for credit card payments (these should always be transfer_out from bank accounts)
        credit_card_payment_patterns = [
            'credit crd epay', 'credit card epay', 'cardpymt', 'card payment',
            'gsbank payment', 'applecard gsbank', 'chase credit', 'discover payment'
        ]
        
        for pattern in credit_card_payment_patterns:
            if pattern in desc_lower:
                return 'transfer_out'
        
        # Check for income keywords
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
    
    def _should_flip_file_signs(self, analysis: Dict[str, any]) -> bool:
        """Determine if all transaction signs in the file should be flipped.
        
        Args:
            analysis: File sign convention analysis results
            
        Returns:
            True if all signs should be flipped, False if they should remain unchanged
        """
        # Only flip if we detect credit card convention with sufficient confidence
        return (
            analysis['convention'] == 'credit_card' and 
            analysis['confidence'] >= 0.5
        )
    
    def _flip_all_transaction_signs(self, transactions: List[Transaction]) -> List[Transaction]:
        """Flip the sign of all transactions in the list.
        
        Args:
            transactions: List of transactions to flip
            
        Returns:
            List of transactions with all signs flipped
        """
        flipped_transactions = []
        
        for transaction in transactions:
            # Create a copy with flipped sign
            flipped = Transaction(
                date=transaction.date,
                amount=-transaction.amount,  # Flip the sign
                description=transaction.description,
                account=transaction.account,
                institution=transaction.institution,
                transaction_id=transaction.transaction_id,
                category=transaction.category,
                balance=transaction.balance
            )
            flipped_transactions.append(flipped)
        
        return flipped_transactions
    
    def correct_transaction_signs(self, transactions: List[Transaction], 
                                account_config: Optional[AccountConfig] = None) -> List[Transaction]:
        """Correct transaction signs to follow banking convention.
        
        This method makes a single decision for the entire file:
        1. Analyze if the file needs sign correction
        2. If yes: flip ALL transaction signs
        3. If no: keep ALL transactions unchanged
        
        Args:
            transactions: List of transactions to correct
            account_config: Optional account configuration for additional context
            
        Returns:
            List of transactions with corrected signs (all changed or all unchanged)
        """
        if not transactions:
            return transactions
        
        # Step 1: Analyze the file's sign convention
        analysis = self.analyze_file_sign_convention(transactions)
        self.logger.info(f"Sign analysis: {analysis}")
        
        # Step 2: Make a single decision for the entire file
        should_flip_all_signs = self._should_flip_file_signs(analysis)
        
        # Step 3: Apply the decision consistently to all transactions
        if should_flip_all_signs:
            self.logger.info(f"Flipping signs for all {len(transactions)} transactions "
                           f"(detected {analysis['convention']} convention with {analysis['confidence']:.2f} confidence)")
            return self._flip_all_transaction_signs(transactions)
        else:
            self.logger.info(f"Keeping original signs for all {len(transactions)} transactions "
                           f"(detected {analysis['convention']} convention with {analysis['confidence']:.2f} confidence)")
            return transactions
