"""QFX/OFX file parser implementation."""

import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

from ofxparse import OfxParser
from ofxparse.ofxparse import OfxParserException

from .base import FileParser, DataTransformer
from ..models.core import Transaction, ParserConfig
from ..utils.error_handler import ErrorHandler, ErrorCategory, handle_file_access_error, handle_parsing_error


logger = logging.getLogger(__name__)


class QFXParser(FileParser):
    """Parser for QFX and OFX files using ofxparse library"""
    
    def __init__(self, config: ParserConfig, error_handler: Optional[ErrorHandler] = None):
        super().__init__(config)
        self.supported_extensions = ['.qfx', '.ofx']
        self.transformer = DataTransformer(config)
        self.error_handler = error_handler or ErrorHandler()
    
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions"""
        return self.supported_extensions
    
    def validate_file(self, file_path: str) -> bool:
        """Validate QFX/OFX file format"""
        try:
            if not os.path.exists(file_path):
                self.error_handler.log_error(
                    f"File does not exist: {file_path}",
                    "FILE_NOT_FOUND",
                    ErrorCategory.FILE_ACCESS,
                    file_path=file_path
                )
                return False
            
            # Check file extension
            _, ext = os.path.splitext(file_path.lower())
            if ext not in self.supported_extensions:
                self.error_handler.log_error(
                    f"Unsupported file extension: {ext}",
                    "UNSUPPORTED_FORMAT",
                    ErrorCategory.FILE_FORMAT,
                    file_path=file_path,
                    context={'supported_extensions': self.supported_extensions}
                )
                return False
            
            # Try to parse the file header to validate format
            try:
                with open(file_path, 'rb') as f:
                    # Read first few lines to check for OFX/QFX markers
                    header = f.read(1024).decode('utf-8', errors='ignore')
                    if 'OFXHEADER' in header or '<OFX>' in header or 'QFXHEADER' in header:
                        return True
                    else:
                        self.error_handler.log_error(
                            f"File does not contain valid OFX/QFX headers",
                            "MALFORMED_FILE",
                            ErrorCategory.FILE_FORMAT,
                            file_path=file_path,
                            context={'header_sample': header[:200]}
                        )
                        return False
            except UnicodeDecodeError as e:
                self.error_handler.log_error(
                    f"File encoding error",
                    "ENCODING_ERROR",
                    ErrorCategory.FILE_FORMAT,
                    file_path=file_path,
                    exception=e
                )
                return False
                
        except Exception as e:
            handle_file_access_error(self.error_handler, file_path, e)
            return False
    
    def parse(self, file_path: str) -> List[Transaction]:
        """Parse QFX/OFX file using ofxparse library"""
        if not self.validate_file(file_path):
            return []
        
        transactions = []
        
        try:
            # Parse the OFX/QFX file
            with open(file_path, 'rb') as f:
                ofx = OfxParser.parse(f)
            
            # Extract institution information
            institution = self.transformer.extract_institution(file_path)
            
            # Process each account in the OFX file
            for account in ofx.accounts:
                account_id = self.extract_account_info(account)
                
                # Process transactions for this account
                for i, ofx_transaction in enumerate(account.statement.transactions):
                    try:
                        transaction = self._convert_ofx_transaction(
                            ofx_transaction, account_id, institution, file_path
                        )
                        transactions.append(transaction)
                    except Exception as e:
                        self.error_handler.log_error(
                            f"Skipping malformed transaction at index {i}",
                            "MALFORMED_FILE",
                            ErrorCategory.DATA_PARSING,
                            file_path=file_path,
                            line_number=i,
                            exception=e,
                            context={'transaction_index': i}
                        )
                        continue
            
            self.error_handler.log_info(
                f"Successfully parsed {len(transactions)} transactions from {file_path}",
                context={
                    'file_path': file_path,
                    'transaction_count': len(transactions),
                    'institution': institution
                }
            )
            
        except OfxParserException as e:
            self.error_handler.log_error(
                f"OFX parsing error: {str(e)}",
                "MALFORMED_FILE",
                ErrorCategory.FILE_FORMAT,
                file_path=file_path,
                exception=e
            )
        except Exception as e:
            handle_file_access_error(self.error_handler, file_path, e)
        
        return transactions
    
    def extract_account_info(self, account) -> str:
        """Extract account information from OFX account data"""
        try:
            # Try to get account ID from various possible fields
            if hasattr(account, 'account_id') and account.account_id:
                account_id = str(account.account_id)
            elif hasattr(account, 'number') and account.number:
                account_id = str(account.number)
            elif hasattr(account, 'routing_number') and account.routing_number:
                account_id = str(account.routing_number)
            else:
                account_id = 'unknown'
            
            # Return last 4 digits if it looks like an account number
            if len(account_id) > 4 and account_id.replace('-', '').isdigit():
                return account_id[-4:]
            
            return account_id
            
        except Exception as e:
            self.error_handler.log_warning(
                f"Error extracting account info: {str(e)}",
                "DATA_TYPE_MISMATCH",
                ErrorCategory.DATA_PARSING,
                context={'account_object': str(account)}
            )
            return 'unknown'
    
    def _convert_ofx_transaction(
        self, 
        ofx_transaction, 
        account_id: str, 
        institution: str, 
        file_path: str
    ) -> Transaction:
        """Convert OFX transaction to unified Transaction format"""
        
        # Extract transaction date
        if hasattr(ofx_transaction, 'date') and ofx_transaction.date:
            transaction_date = ofx_transaction.date
        else:
            raise ValueError("Transaction missing required date field")
        
        # Extract transaction amount
        if hasattr(ofx_transaction, 'amount') and ofx_transaction.amount is not None:
            amount = Decimal(str(ofx_transaction.amount))
        else:
            raise ValueError("Transaction missing required amount field")
        
        # Extract description/memo
        description = ""
        if hasattr(ofx_transaction, 'memo') and ofx_transaction.memo:
            description = self.transformer.clean_description(ofx_transaction.memo)
        elif hasattr(ofx_transaction, 'payee') and ofx_transaction.payee:
            description = self.transformer.clean_description(ofx_transaction.payee)
        
        if not description:
            description = "Unknown transaction"
        
        # Extract transaction ID
        transaction_id = None
        if hasattr(ofx_transaction, 'id') and ofx_transaction.id:
            transaction_id = str(ofx_transaction.id)
        elif hasattr(ofx_transaction, 'fitid') and ofx_transaction.fitid:
            transaction_id = str(ofx_transaction.fitid)
        
        # Extract balance if available
        balance = None
        if hasattr(ofx_transaction, 'balance') and ofx_transaction.balance is not None:
            balance = Decimal(str(ofx_transaction.balance))
        
        # Create and return the unified transaction
        return Transaction(
            date=transaction_date,
            amount=amount,
            description=description,
            account=account_id,
            institution=institution,
            transaction_id=transaction_id,
            category=None,  # Category will be handled by future categorization features
            balance=balance
        )