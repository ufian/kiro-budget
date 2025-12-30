"""PDF parser for extracting transaction data from PDF statements."""

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional

import pdfplumber

from .base import FileParser, DataTransformer
from ..models.core import Transaction, ParserConfig


logger = logging.getLogger(__name__)


class PDFParser(FileParser):
    """Parser for PDF statements using pdfplumber"""
    
    def __init__(self, config: ParserConfig):
        super().__init__(config)
        self.supported_extensions = ['.pdf']
        self.transformer = DataTransformer(config)
        
        # Common patterns for identifying transaction data
        self.date_patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # MM/DD/YYYY or M/D/YYYY
            r'\b\d{1,2}-\d{1,2}-\d{4}\b',  # MM-DD-YYYY or M-D-YYYY
            r'\b\d{4}-\d{1,2}-\d{1,2}\b',  # YYYY-MM-DD or YYYY-M-D
        ]
        
        self.amount_patterns = [
            r'\$?\s*\d{1,3}(?:,\d{3})*\.\d{2}',  # $1,234.56 or 1,234.56
            r'\(\$?\s*\d{1,3}(?:,\d{3})*\.\d{2}\)',  # ($1,234.56) for negative
        ]
    
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions"""
        return self.supported_extensions
    
    def validate_file(self, file_path: str) -> bool:
        """Validate if file can be processed by this parser"""
        try:
            with pdfplumber.open(file_path) as pdf:
                # Check if we can open the PDF and it has at least one page
                if len(pdf.pages) == 0:
                    logger.warning(f"PDF file {file_path} has no pages")
                    return False
                
                # Try to extract some text from the first page
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                
                if not text or len(text.strip()) < 10:
                    logger.warning(f"PDF file {file_path} appears to have no readable text")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error validating PDF file {file_path}: {e}")
            return False
    
    def parse(self, file_path: str) -> List[Transaction]:
        """Parse PDF file using pdfplumber for table extraction"""
        transactions = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                logger.info(f"Processing PDF file: {file_path} with {len(pdf.pages)} pages")
                
                # Extract institution and account info from file path
                institution = self.transformer.extract_institution(file_path)
                
                # Process all pages
                for page_num, page in enumerate(pdf.pages, 1):
                    logger.debug(f"Processing page {page_num} of {file_path}")
                    
                    # Try table extraction first
                    page_transactions = self._extract_from_tables(page, file_path, institution)
                    
                    # If no tables found or tables didn't yield transactions, try text extraction
                    if not page_transactions:
                        page_transactions = self._extract_from_text(page, file_path, institution)
                    
                    transactions.extend(page_transactions)
                
                logger.info(f"Extracted {len(transactions)} transactions from {file_path}")
                
        except Exception as e:
            logger.error(f"Error parsing PDF file {file_path}: {e}")
            # Don't raise exception - return empty list and let error handling deal with it
            
        return transactions
    
    def _extract_from_tables(self, page, file_path: str, institution: str) -> List[Transaction]:
        """Extract transactions from PDF tables"""
        transactions = []
        
        try:
            tables = page.extract_tables()
            
            if not tables:
                logger.debug("No tables found on page")
                return transactions
            
            for table_idx, table in enumerate(tables):
                logger.debug(f"Processing table {table_idx + 1} with {len(table)} rows")
                
                if not table or len(table) < 2:  # Need at least header + 1 data row
                    continue
                
                # Try to identify the header row and column structure
                header_row = table[0]
                data_rows = table[1:]
                
                # Look for common column patterns
                column_mapping = self._identify_columns(header_row)
                
                if not column_mapping:
                    logger.debug(f"Could not identify column structure in table {table_idx + 1}")
                    continue
                
                # Extract transactions from data rows
                for row_idx, row in enumerate(data_rows):
                    try:
                        transaction = self._parse_table_row(row, column_mapping, file_path, institution)
                        if transaction:
                            transactions.append(transaction)
                    except Exception as e:
                        logger.warning(f"Error parsing table row {row_idx + 1}: {e}")
                        continue
                        
        except Exception as e:
            logger.warning(f"Error extracting tables from page: {e}")
            
        return transactions
    
    def _extract_from_text(self, page, file_path: str, institution: str) -> List[Transaction]:
        """Extract transactions from PDF text when tables are not available"""
        transactions = []
        
        try:
            text = page.extract_text()
            if not text:
                return transactions
            
            # Split text into lines and look for transaction patterns
            lines = text.split('\n')
            
            for line_idx, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Look for lines that contain both date and amount patterns
                if self._looks_like_transaction_line(line):
                    try:
                        transaction = self._parse_text_line(line, file_path, institution)
                        if transaction:
                            transactions.append(transaction)
                    except Exception as e:
                        logger.debug(f"Could not parse line as transaction: {line} - {e}")
                        continue
                        
        except Exception as e:
            logger.warning(f"Error extracting text from page: {e}")
            
        return transactions
    
    def _identify_columns(self, header_row: List[str]) -> Optional[Dict[str, int]]:
        """Identify column positions based on header row"""
        if not header_row:
            return None
        
        column_mapping = {}
        
        # Common column name patterns
        patterns = {
            'date': [r'date', r'trans.*date', r'posting.*date', r'effective.*date'],
            'description': [r'description', r'memo', r'details', r'transaction', r'payee'],
            'amount': [r'amount', r'debit', r'credit', r'withdrawal', r'deposit'],
            'balance': [r'balance', r'running.*balance', r'account.*balance']
        }
        
        for col_idx, header in enumerate(header_row):
            if not header:
                continue
                
            header_lower = header.lower().strip()
            
            for field, field_patterns in patterns.items():
                if field in column_mapping:  # Skip if already found
                    continue
                    
                for pattern in field_patterns:
                    if re.search(pattern, header_lower):
                        column_mapping[field] = col_idx
                        break
        
        # We need at least date and amount columns
        if 'date' not in column_mapping or 'amount' not in column_mapping:
            return None
            
        return column_mapping
    
    def _parse_table_row(self, row: List[str], column_mapping: Dict[str, int], 
                         file_path: str, institution: str) -> Optional[Transaction]:
        """Parse a single table row into a Transaction"""
        try:
            # Extract required fields
            date_str = row[column_mapping['date']] if column_mapping.get('date') is not None else None
            amount_str = row[column_mapping['amount']] if column_mapping.get('amount') is not None else None
            description = row[column_mapping.get('description', 0)] if column_mapping.get('description') is not None else ""
            balance_str = row[column_mapping['balance']] if column_mapping.get('balance') is not None else None
            
            if not date_str or not amount_str:
                return None
            
            # Parse date
            date = self.transformer.normalize_date(date_str.strip())
            
            # Parse amount
            amount = self.transformer.normalize_amount(amount_str.strip())
            
            # CRITICAL FIX: Convert credit card statement signs to banking convention
            amount = self._convert_credit_card_amount_to_banking_convention(amount, description)
            
            # Parse balance if available
            balance = None
            if balance_str and balance_str.strip():
                try:
                    balance = self.transformer.normalize_amount(balance_str.strip())
                except:
                    pass  # Balance is optional
            
            # Clean description
            description = self.transformer.clean_description(description)
            
            # Extract account info
            account = self.transformer.extract_account(file_path, {})
            
            return Transaction(
                date=date,
                amount=amount,
                description=description,
                account=account,
                institution=institution,
                balance=balance
            )
            
        except Exception as e:
            logger.debug(f"Error parsing table row: {e}")
            return None
    
    def _looks_like_transaction_line(self, line: str) -> bool:
        """Check if a line looks like it contains transaction data"""
        # Look for date pattern
        has_date = any(re.search(pattern, line) for pattern in self.date_patterns)
        
        # Look for amount pattern
        has_amount = any(re.search(pattern, line) for pattern in self.amount_patterns)
        
        # Also check for Chase-specific format: MM/DD Description Amount
        chase_pattern = r'^\d{1,2}/\d{1,2}\s+.+\s+[-]?\d+\.\d{2}$'
        is_chase_format = re.match(chase_pattern, line.strip())
        
        return (has_date and has_amount) or is_chase_format
    
    def _parse_text_line(self, line: str, file_path: str, institution: str) -> Optional[Transaction]:
        """Parse a single text line into a Transaction"""
        try:
            line = line.strip()
            
            # Try Chase-specific format first: MM/DD Description Amount
            chase_pattern = r'^(\d{1,2}/\d{1,2})\s+(.+?)\s+([-]?\d+\.\d{2})$'
            chase_match = re.match(chase_pattern, line)
            
            if chase_match:
                date_str, description, amount_str = chase_match.groups()
                
                # Add current year to date (assuming current year for MM/DD format)
                from datetime import datetime
                current_year = datetime.now().year
                date_str = f"{date_str}/{current_year}"
                
                date = self.transformer.normalize_date(date_str)
                amount = self.transformer.normalize_amount(amount_str)
                
                # CRITICAL FIX: Convert credit card statement signs to banking convention
                # In credit card statements:
                # - Credits (payments, refunds) are shown as negative (reduce balance owed)
                # - Debits (purchases) are shown as positive (increase balance owed)
                # But in banking convention:
                # - Credits should be positive (money coming in)
                # - Debits should be negative (money going out)
                amount = self._convert_credit_card_amount_to_banking_convention(amount, description)
                
                description = self.transformer.clean_description(description)
                account = self.transformer.extract_account(file_path, {})
                
                return Transaction(
                    date=date,
                    amount=amount,
                    description=description,
                    account=account,
                    institution=institution
                )
            
            # Fall back to general pattern matching
            # Extract date
            date_match = None
            for pattern in self.date_patterns:
                match = re.search(pattern, line)
                if match:
                    date_match = match
                    break
            
            if not date_match:
                return None
            
            date_str = date_match.group()
            date = self.transformer.normalize_date(date_str)
            
            # Extract amount
            amount_match = None
            for pattern in self.amount_patterns:
                match = re.search(pattern, line)
                if match:
                    amount_match = match
                    break
            
            if not amount_match:
                return None
            
            amount_str = amount_match.group()
            amount = self.transformer.normalize_amount(amount_str)
            
            # Extract description (everything else in the line, cleaned up)
            description = line
            # Remove the date and amount from description
            description = re.sub(re.escape(date_str), '', description)
            description = re.sub(re.escape(amount_str), '', description)
            description = self.transformer.clean_description(description)
            
            # CRITICAL FIX: Convert credit card statement signs to banking convention
            amount = self._convert_credit_card_amount_to_banking_convention(amount, description)
            
            # Extract account info
            account = self.transformer.extract_account(file_path, {})
            
            return Transaction(
                date=date,
                amount=amount,
                description=description,
                account=account,
                institution=institution
            )
            
        except Exception as e:
            logger.debug(f"Error parsing text line: {e}")
            return None
    
    def _convert_credit_card_amount_to_banking_convention(self, amount: Decimal, description: str) -> Decimal:
        """
        Convert credit card statement amounts to banking convention
        
        Credit card statements show:
        - Credits (payments, refunds) as negative (they reduce balance owed)
        - Debits (purchases) as positive (they increase balance owed)
        
        Banking convention shows:
        - Credits as positive (money coming in)
        - Debits as negative (money going out)
        
        So we need to invert the signs for credit card statements.
        """
        # Detect if this is likely a credit/payment vs a debit/purchase
        description_lower = description.lower() if description else ""
        
        # Keywords that indicate credits (payments, refunds, returns)
        credit_keywords = [
            'payment', 'thank you', 'refund', 'return', 'credit', 'adjustment',
            'cashback', 'reward', 'rebate', 'amazon.com amzn.com/bill'  # Amazon refunds
        ]
        
        # Keywords that indicate debits (purchases, fees, interest)
        debit_keywords = [
            'purchase', 'fee', 'interest', 'charge', 'penalty', 'late',
            'amazon.com*', 'amazon mktpl*'  # Amazon purchases (different from refunds)
        ]
        
        is_likely_credit = any(keyword in description_lower for keyword in credit_keywords)
        is_likely_debit = any(keyword in description_lower for keyword in debit_keywords)
        
        # If we can't determine from description, use the sign as a hint
        # In credit card statements:
        # - Negative amounts are usually credits (payments/refunds)
        # - Positive amounts are usually debits (purchases)
        if not is_likely_credit and not is_likely_debit:
            if amount < 0:
                is_likely_credit = True
            else:
                is_likely_debit = True
        
        # Convert to banking convention
        if is_likely_credit:
            # Credits should be positive in banking convention
            return abs(amount)
        else:
            # Debits should be negative in banking convention
            return -abs(amount)
    
    def extract_tables_from_all_pages(self, pdf_path: str) -> List[List[Dict]]:
        """Extract transaction tables from all pages of PDF"""
        all_tables = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        # Convert table rows to dictionaries if possible
                        for table in tables:
                            if len(table) > 1:  # Has header + data
                                header = table[0]
                                rows = []
                                for data_row in table[1:]:
                                    if len(data_row) == len(header):
                                        row_dict = dict(zip(header, data_row))
                                        rows.append(row_dict)
                                if rows:
                                    all_tables.append(rows)
                                    
        except Exception as e:
            logger.error(f"Error extracting tables from {pdf_path}: {e}")
            
        return all_tables
    
    def identify_transaction_patterns(self, text_data: str) -> List[Dict]:
        """Identify and extract transaction patterns from text"""
        patterns = []
        
        if not text_data:
            return patterns
        
        lines = text_data.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if self._looks_like_transaction_line(line):
                # Extract components
                date_matches = []
                amount_matches = []
                
                for pattern in self.date_patterns:
                    matches = re.finditer(pattern, line)
                    date_matches.extend([m.group() for m in matches])
                
                for pattern in self.amount_patterns:
                    matches = re.finditer(pattern, line)
                    amount_matches.extend([m.group() for m in matches])
                
                if date_matches and amount_matches:
                    patterns.append({
                        'line': line,
                        'dates': date_matches,
                        'amounts': amount_matches
                    })
        
        return patterns