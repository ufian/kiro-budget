"""CSV file parser implementation with automatic column detection."""

import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

import pandas as pd

from .base import FileParser, DataTransformer
from ..models.core import Transaction, ParserConfig


logger = logging.getLogger(__name__)


class CSVParser(FileParser):
    """Parser for CSV files with automatic column mapping"""
    
    def __init__(self, config: ParserConfig):
        super().__init__(config)
        self.supported_extensions = ['.csv']
        self.transformer = DataTransformer(config)
        
        # Common column name variations for automatic mapping
        self.column_mappings = {
            'date': [
                'date', 'transaction_date', 'posting_date', 'Date', 'Transaction Date',
                'Posting Date', 'trans_date', 'Trans Date', 'DATE', 'TRANSACTION_DATE',
                'transaction date', 'posting date', 'effective_date', 'Effective Date',
                'Transaction Post Date', 'transaction post date', 'TRANSACTION POST DATE',
                'Started Date', 'started date', 'Completed Date', 'completed date'
            ],
            'amount': [
                'amount', 'Amount', 'transaction_amount', 'debit_credit', 'Debit', 'Credit',
                'AMOUNT', 'TRANSACTION_AMOUNT', 'transaction amount', 'Amount ($)', 'Amount($)',
                'debit', 'credit', 'net_amount', 'Net Amount', 'transaction_value', 'value'
            ],
            'description': [
                'description', 'Description', 'memo', 'details', 'Memo', 'Details',
                'DESCRIPTION', 'MEMO', 'DETAILS', 'transaction_description', 'payee',
                'Payee', 'merchant', 'Merchant', 'reference', 'Reference', 'narration',
                'Description of Transaction', 'description of transaction', 'DESCRIPTION OF TRANSACTION',
                'Transaction Description', 'transaction description', 'TRANSACTION DESCRIPTION'
            ],
            'account': [
                'account', 'Account', 'account_number', 'Account Number', 'ACCOUNT',
                'ACCOUNT_NUMBER', 'account number', 'acct', 'Acct', 'account_id', 'Account ID',
                'Product', 'product', 'PRODUCT'
            ],
            'transaction_id': [
                'transaction_id', 'Transaction ID', 'id', 'ID', 'trans_id', 'Trans ID',
                'TRANSACTION_ID', 'reference_number', 'Reference Number', 'check_number',
                'Check Number', 'confirmation', 'Confirmation'
            ],
            'balance': [
                'balance', 'Balance', 'running_balance', 'Running Balance', 'BALANCE',
                'account_balance', 'Account Balance', 'current_balance', 'Current Balance'
            ],
            'transaction_type': [
                'transaction_type', 'Transaction Type', 'type', 'Type', 'trans_type',
                'TRANSACTION_TYPE', 'TYPE', 'transaction type'
            ]
        }
    
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions"""
        return self.supported_extensions
    
    def validate_file(self, file_path: str) -> bool:
        """Validate CSV file format"""
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False
        
        # Check file extension
        _, ext = os.path.splitext(file_path.lower())
        if ext not in self.supported_extensions:
            logger.error(f"Unsupported file extension: {ext}")
            return False
        
        # Try to read the CSV file to validate format
        try:
            # Read just the header to validate CSV structure
            df = pd.read_csv(file_path, nrows=0)
            if len(df.columns) < 2:
                logger.error(f"CSV file has insufficient columns: {file_path}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating CSV file {file_path}: {str(e)}")
            return False
    
    def parse(self, file_path: str) -> List[Transaction]:
        """Parse CSV file with automatic column detection"""
        if not self.validate_file(file_path):
            logger.error(f"File validation failed for: {file_path}")
            return []
        
        transactions = []
        
        try:
            # Read the CSV file
            df = pd.read_csv(file_path)
            
            if df.empty:
                logger.warning(f"CSV file is empty: {file_path}")
                return []
            
            # Detect column mappings
            column_mapping = self.detect_column_mapping(df.columns.tolist())
            
            # Validate that we have the required columns
            if not self._validate_required_columns(column_mapping, file_path):
                return []
            
            # Extract institution and account information
            institution = self.transformer.extract_institution(file_path)
            
            # Process each row
            for index, row in df.iterrows():
                try:
                    transaction = self._convert_csv_row(
                        row, column_mapping, institution, file_path, index
                    )
                    if transaction:
                        transactions.append(transaction)
                except Exception as e:
                    logger.warning(
                        f"Skipping malformed row {index + 1} in {file_path}: {str(e)}"
                    )
                    continue
            
            logger.info(f"Successfully parsed {len(transactions)} transactions from {file_path}")
            
            # Apply automatic sign correction
            transactions = self.apply_sign_correction(transactions)
            
        except Exception as e:
            logger.error(f"Error parsing CSV file {file_path}: {str(e)}")
        
        return transactions
    
    def detect_column_mapping(self, headers: List[str]) -> Dict[str, str]:
        """Automatically detect column mappings or prompt for manual configuration"""
        mapping = {}
        
        # First, check for debit/credit columns specifically
        debit_col = None
        credit_col = None
        
        for header in headers:
            header_lower = header.lower().strip()
            if 'debit' in header_lower and debit_col is None:
                debit_col = header
            elif 'credit' in header_lower and credit_col is None:
                credit_col = header
        
        # If we found both debit and credit columns, use them instead of amount
        if debit_col and credit_col:
            mapping['debit'] = debit_col
            mapping['credit'] = credit_col
            logger.info(f"Detected separate debit/credit columns: {debit_col}, {credit_col}")
        else:
            # Try to automatically map columns based on common naming patterns
            for field, possible_names in self.column_mappings.items():
                for header in headers:
                    if header.strip() in possible_names:
                        mapping[field] = header
                        break
        
        # Map other fields (date, description, etc.) regardless of debit/credit detection
        for field in ['date', 'description', 'account', 'transaction_id', 'balance', 'transaction_type']:
            if field not in mapping:
                possible_names = self.column_mappings.get(field, [])
                for header in headers:
                    if header.strip() in possible_names:
                        mapping[field] = header
                        break
        
        # Check if we have institution-specific mappings in config
        if self.config.column_mappings:
            # Try to find institution-specific mappings
            # This would be enhanced in the future to use file path to determine institution
            for institution, inst_mappings in self.config.column_mappings.items():
                for field, column_name in inst_mappings.items():
                    if column_name in headers:
                        mapping[field] = column_name
        
        # Log the detected mappings
        logger.info(f"Detected column mappings: {mapping}")
        
        return mapping
    
    def _validate_required_columns(self, column_mapping: Dict[str, str], file_path: str) -> bool:
        """Validate that we have the minimum required columns"""
        required_fields = ['date', 'description']
        
        # We need either 'amount' or both 'debit' and 'credit'
        has_amount = 'amount' in column_mapping
        has_debit_credit = 'debit' in column_mapping and 'credit' in column_mapping
        
        if not (has_amount or has_debit_credit):
            logger.error(f"CSV file missing amount information in {file_path}")
            return False
        
        for field in required_fields:
            if field not in column_mapping:
                logger.error(f"CSV file missing required field '{field}' in {file_path}")
                return False
        
        return True
    
    def _convert_csv_row(
        self, 
        row: pd.Series, 
        column_mapping: Dict[str, str], 
        institution: str, 
        file_path: str,
        row_index: int
    ) -> Optional[Transaction]:
        """Convert CSV row to unified Transaction format"""
        
        try:
            # Extract date
            date_col = column_mapping.get('date')
            if not date_col or pd.isna(row[date_col]):
                raise ValueError(f"Missing date in row {row_index + 1}")
            
            date_str = str(row[date_col]).strip()
            transaction_date = self.transformer.normalize_date(date_str)
            
            # Extract amount (handle both single amount column and debit/credit columns)
            amount = self._extract_amount(row, column_mapping, row_index)
            
            # Extract description
            desc_col = column_mapping.get('description')
            if not desc_col or pd.isna(row[desc_col]) or str(row[desc_col]).strip() == '':
                # If description is empty, try to use transaction_type as fallback
                type_col = column_mapping.get('transaction_type')
                if type_col and not pd.isna(row[type_col]):
                    trans_type = str(row[type_col]).strip()
                    # Make transaction type more readable (e.g., "payment_transaction" -> "Payment Transaction")
                    description = trans_type.replace('_', ' ').title()
                else:
                    description = "Unknown transaction"
            else:
                description = self.transformer.clean_description(str(row[desc_col]))
            
            # Extract account information
            account_col = column_mapping.get('account')
            if account_col and not pd.isna(row[account_col]):
                account = self.transformer.extract_account(file_path, {'account': row[account_col]})
            else:
                account = self.transformer.extract_account(file_path, {})
            
            # Extract transaction ID
            transaction_id = None
            id_col = column_mapping.get('transaction_id')
            if id_col and not pd.isna(row[id_col]):
                transaction_id = str(row[id_col]).strip()
            
            # Extract balance
            balance = None
            balance_col = column_mapping.get('balance')
            if balance_col and not pd.isna(row[balance_col]):
                try:
                    balance = self.transformer.normalize_amount(str(row[balance_col]))
                except ValueError:
                    # Balance is optional, so we can continue without it
                    pass
            
            # Create and return the unified transaction
            return Transaction(
                date=transaction_date,
                amount=amount,
                description=description,
                account=account,
                institution=institution,
                transaction_id=transaction_id,
                category=None,  # Category will be handled by future categorization features
                balance=balance
            )
            
        except Exception as e:
            logger.warning(f"Error converting row {row_index + 1}: {str(e)}")
            return None
    
    def _extract_amount(self, row: pd.Series, column_mapping: Dict[str, str], row_index: int) -> Decimal:
        """Extract amount from either single amount column or debit/credit columns"""
        
        # Try single amount column first
        amount_col = column_mapping.get('amount')
        if amount_col and not pd.isna(row[amount_col]):
            amount_str = str(row[amount_col]).strip()
            if amount_str:  # Make sure it's not empty
                return self.transformer.normalize_amount(amount_str)
        
        # Try debit/credit columns
        debit_col = column_mapping.get('debit')
        credit_col = column_mapping.get('credit')
        
        if debit_col and credit_col:
            debit_val = 0
            credit_val = 0
            
            # Extract debit amount
            if not pd.isna(row[debit_col]):
                debit_str = str(row[debit_col]).strip()
                if debit_str and debit_str != '0' and debit_str != '0.00' and debit_str != '':
                    debit_val = float(self.transformer.normalize_amount(debit_str))
            
            # Extract credit amount
            if not pd.isna(row[credit_col]):
                credit_str = str(row[credit_col]).strip()
                if credit_str and credit_str != '0' and credit_str != '0.00' and credit_str != '':
                    credit_val = float(self.transformer.normalize_amount(credit_str))
            
            # Calculate net amount (credits are positive, debits are negative)
            net_amount = credit_val - debit_val
            return Decimal(str(net_amount))
        
        raise ValueError(f"No valid amount found in row {row_index + 1}")