"""Validation engine for transaction data and CSV output."""

import csv
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Set, Tuple
from ..models.core import Transaction


class ValidationEngine:
    """Validates parsed transaction data"""
    
    def __init__(self):
        self.required_fields = ['date', 'amount', 'description', 'account', 'institution']
        self.csv_headers = [
            'date', 'amount', 'description', 'account', 'institution', 
            'transaction_id', 'category', 'balance'
        ]
    
    def validate_transaction(self, transaction: Transaction) -> List[str]:
        """Validate individual transaction and return list of errors"""
        errors = []
        
        # Check required fields
        if not isinstance(transaction.date, datetime):
            errors.append("Invalid date: must be datetime object")
        
        if not isinstance(transaction.amount, Decimal):
            errors.append("Invalid amount: must be Decimal object")
        elif transaction.amount == 0:
            errors.append("Warning: Transaction amount is zero")
        
        if not transaction.description or not str(transaction.description).strip():
            errors.append("Description cannot be empty")
        elif len(str(transaction.description).strip()) < 2:
            errors.append("Description too short (minimum 2 characters)")
        
        if not transaction.account or not str(transaction.account).strip():
            errors.append("Account cannot be empty")
        
        if not transaction.institution or not str(transaction.institution).strip():
            errors.append("Institution cannot be empty")
        
        # Validate optional fields if present
        if transaction.balance is not None and not isinstance(transaction.balance, Decimal):
            errors.append("Invalid balance: must be Decimal object or None")
        
        if transaction.transaction_id is not None:
            if not str(transaction.transaction_id).strip():
                errors.append("Transaction ID cannot be empty string (use None instead)")
        
        if transaction.category is not None:
            if not str(transaction.category).strip():
                errors.append("Category cannot be empty string (use None instead)")
        
        # Validate date is reasonable (not too far in past or future)
        if isinstance(transaction.date, datetime):
            current_year = datetime.now().year
            if transaction.date.year < 1900 or transaction.date.year > current_year + 1:
                errors.append(f"Date year {transaction.date.year} seems unreasonable")
        
        # Validate amount is reasonable (not extremely large)
        if isinstance(transaction.amount, Decimal):
            if abs(transaction.amount) > Decimal('1000000'):  # 1 million
                errors.append("Warning: Transaction amount is very large")
        
        return errors
    
    def validate_csv_output(self, csv_path: str) -> List[str]:
        """Validate generated CSV file for data integrity"""
        errors = []
        
        if not os.path.exists(csv_path):
            errors.append(f"CSV file does not exist: {csv_path}")
            return errors
        
        if os.path.getsize(csv_path) == 0:
            errors.append(f"CSV file is empty: {csv_path}")
            return errors
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                # Check headers
                if not reader.fieldnames:
                    errors.append("CSV file has no headers")
                    return errors
                
                if list(reader.fieldnames) != self.csv_headers:
                    errors.append(f"Invalid CSV headers. Expected: {self.csv_headers}, Got: {list(reader.fieldnames)}")
                
                row_count = 0
                seen_transactions = set()
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 because of header
                    row_count += 1
                    
                    # Validate each row
                    row_errors = self._validate_csv_row(row, row_num)
                    errors.extend(row_errors)
                    
                    # Check for duplicate rows (same content)
                    row_key = tuple(sorted(row.items()))
                    if row_key in seen_transactions:
                        errors.append(f"Row {row_num}: Duplicate row detected")
                    else:
                        seen_transactions.add(row_key)
                    
                    # Stop validation if too many errors (performance)
                    if len(errors) > 100:
                        errors.append("Too many errors, stopping validation")
                        break
                
                if row_count == 0:
                    errors.append("CSV file contains no data rows")
                    
        except UnicodeDecodeError:
            errors.append(f"CSV file encoding error: {csv_path}")
        except csv.Error as e:
            errors.append(f"CSV format error: {str(e)}")
        except Exception as e:
            errors.append(f"Error reading CSV file: {str(e)}")
        
        return errors
    
    def _validate_csv_row(self, row: Dict[str, str], row_num: int) -> List[str]:
        """Validate individual CSV row"""
        errors = []
        
        # Check that all expected columns are present
        for header in self.csv_headers:
            if header not in row:
                errors.append(f"Row {row_num}: Missing column '{header}'")
        
        # Validate date format (ISO 8601: YYYY-MM-DD)
        date_str = row.get('date', '').strip()
        if not date_str:
            errors.append(f"Row {row_num}: Date cannot be empty")
        else:
            try:
                parsed_date = datetime.fromisoformat(date_str)
                # Additional date validation
                current_year = datetime.now().year
                if parsed_date.year < 1900 or parsed_date.year > current_year + 1:
                    errors.append(f"Row {row_num}: Date year {parsed_date.year} seems unreasonable")
            except ValueError:
                errors.append(f"Row {row_num}: Invalid date format '{date_str}', expected ISO format (YYYY-MM-DD)")
        
        # Validate amount format (decimal with up to 2 decimal places)
        amount_str = row.get('amount', '').strip()
        if not amount_str:
            errors.append(f"Row {row_num}: Amount cannot be empty")
        else:
            try:
                amount = Decimal(amount_str)
                # Check decimal places (should be 2 for currency)
                if amount.as_tuple().exponent < -2:
                    errors.append(f"Row {row_num}: Amount has more than 2 decimal places: {amount_str}")
                # Check for reasonable amount
                if abs(amount) > Decimal('1000000'):
                    errors.append(f"Row {row_num}: Amount is very large: {amount_str}")
            except InvalidOperation:
                errors.append(f"Row {row_num}: Invalid amount format '{amount_str}', expected decimal number")
        
        # Check required fields are not empty
        required_fields = ['description', 'account', 'institution']
        for field in required_fields:
            value = row.get(field, '').strip()
            if not value:
                errors.append(f"Row {row_num}: {field} cannot be empty")
            elif len(value) < 2 and field == 'description':
                errors.append(f"Row {row_num}: {field} too short (minimum 2 characters)")
        
        # Validate balance if present
        balance_str = row.get('balance', '').strip()
        if balance_str:
            try:
                balance = Decimal(balance_str)
                if balance.as_tuple().exponent < -2:
                    errors.append(f"Row {row_num}: Balance has more than 2 decimal places: {balance_str}")
            except InvalidOperation:
                errors.append(f"Row {row_num}: Invalid balance format '{balance_str}', expected decimal number")
        
        # Validate transaction_id if present
        transaction_id = row.get('transaction_id', '').strip()
        if transaction_id and len(transaction_id) < 3:
            errors.append(f"Row {row_num}: Transaction ID too short: '{transaction_id}'")
        
        return errors
    
    def deduplicate_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        """Remove duplicate transactions based on transaction_id and date"""
        if not transactions:
            return []
        
        seen: Set[Tuple] = set()
        unique_transactions = []
        duplicate_count = 0
        
        for transaction in transactions:
            # Create a key for deduplication
            # Priority 1: Use transaction_id if available
            if transaction.transaction_id and str(transaction.transaction_id).strip():
                key = ('id', str(transaction.transaction_id).strip(), transaction.date.date())
            else:
                # Priority 2: Use combination of date, amount, description, and account
                key = (
                    'combo',
                    transaction.date.date(),
                    transaction.amount,
                    str(transaction.description).strip().lower(),
                    str(transaction.account).strip().lower()
                )
            
            if key not in seen:
                seen.add(key)
                unique_transactions.append(transaction)
            else:
                duplicate_count += 1
        
        # Log duplicate information if any found
        if duplicate_count > 0:
            print(f"Removed {duplicate_count} duplicate transactions")
        
        return unique_transactions
    
    def validate_transaction_list(self, transactions: List[Transaction]) -> Dict[str, any]:
        """Validate a list of transactions and return summary"""
        if not transactions:
            return {
                'valid_count': 0,
                'invalid_count': 0,
                'total_count': 0,
                'errors': ['No transactions to validate'],
                'warnings': []
            }
        
        valid_count = 0
        invalid_count = 0
        all_errors = []
        all_warnings = []
        
        for i, transaction in enumerate(transactions):
            errors = self.validate_transaction(transaction)
            if errors:
                invalid_count += 1
                # Separate warnings from errors
                transaction_errors = [e for e in errors if not e.startswith('Warning:')]
                transaction_warnings = [e for e in errors if e.startswith('Warning:')]
                
                if transaction_errors:
                    all_errors.extend([f"Transaction {i+1}: {error}" for error in transaction_errors])
                if transaction_warnings:
                    all_warnings.extend([f"Transaction {i+1}: {warning}" for warning in transaction_warnings])
                
                # Only count as invalid if there are actual errors (not just warnings)
                if not transaction_errors:
                    valid_count += 1
                    invalid_count -= 1
            else:
                valid_count += 1
        
        return {
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'total_count': len(transactions),
            'errors': all_errors,
            'warnings': all_warnings
        }