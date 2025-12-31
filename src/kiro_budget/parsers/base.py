"""Abstract base classes and interfaces for file parsers."""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from ..models.core import Transaction, ParserConfig


class FileParser(ABC):
    """Abstract base class for all file parsers"""
    
    def __init__(self, config: ParserConfig):
        self.config = config
    
    @abstractmethod
    def parse(self, file_path: str) -> List[Transaction]:
        """Parse the file and return list of transactions"""
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions"""
        pass
    
    @abstractmethod
    def validate_file(self, file_path: str) -> bool:
        """Validate if file can be processed by this parser"""
        pass


class DataTransformer:
    """Transforms parsed data to unified format"""
    
    def __init__(self, config: ParserConfig):
        self.config = config
    
    def normalize_date(self, date_str: str, formats: Optional[List[str]] = None) -> datetime:
        """Convert various date formats to datetime with multiple format support"""
        from datetime import datetime
        import re
        
        if not date_str or not str(date_str).strip():
            raise ValueError("Date string cannot be empty")
        
        date_str = str(date_str).strip()
        
        if formats is None:
            formats = self.config.date_formats
        
        # Extended format list with common variations
        extended_formats = formats + [
            "%m-%d-%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y %H:%M:%S",
            "%m-%d-%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S",
            "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
            "%Y%m%d", "%m%d%Y", "%d%m%Y"
        ]
        
        # Try parsing with each format
        for fmt in extended_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try to handle some special cases with regex preprocessing
        # Handle formats like "2023-12-31T00:00:00" (ISO with time)
        iso_match = re.match(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})', date_str)
        if iso_match:
            try:
                return datetime.strptime(f"{iso_match.group(1)} {iso_match.group(2)}", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        
        # Handle formats with ordinal indicators (1st, 2nd, 3rd, etc.)
        ordinal_cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
        if ordinal_cleaned != date_str:
            for fmt in extended_formats:
                try:
                    return datetime.strptime(ordinal_cleaned, fmt)
                except ValueError:
                    continue
        
        raise ValueError(f"Unable to parse date: {date_str} with any supported format")
    
    def normalize_amount(self, amount_str: str) -> Decimal:
        """Convert various amount formats to Decimal with precision preservation"""
        from decimal import Decimal, getcontext, ROUND_HALF_UP
        import re
        
        if not amount_str or str(amount_str).strip() == '':
            raise ValueError("Amount string cannot be empty")
        
        # Set precision context to preserve decimal places
        getcontext().prec = 28  # High precision for financial calculations
        
        amount_str = str(amount_str).strip()
        
        # Remove common currency symbols and whitespace
        cleaned = re.sub(r'[\$£€¥₹\s]', '', amount_str)
        
        # Handle different thousand separators and decimal points
        # European format: 1.234,56 -> 1234.56
        if re.match(r'^\d{1,3}(\.\d{3})*,\d{2}$', cleaned):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        # US format with commas: 1,234.56 -> 1234.56
        elif re.match(r'^\d{1,3}(,\d{3})*\.\d{2}$', cleaned):
            cleaned = cleaned.replace(',', '')
        # Simple comma removal for thousands
        elif ',' in cleaned and '.' in cleaned:
            # If both comma and dot, assume comma is thousands separator
            if cleaned.rfind(',') < cleaned.rfind('.'):
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned and '.' not in cleaned:
            # Only comma, could be decimal separator (European) or thousands
            # If exactly 2 digits after comma, treat as decimal
            if re.match(r'.*,\d{2}$', cleaned):
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        
        # Handle parentheses as negative indicators
        is_negative = False
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = cleaned[1:-1]
            is_negative = True
        elif cleaned.startswith('-'):
            is_negative = True
            cleaned = cleaned[1:]
        
        # Handle explicit positive sign
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]
        
        # Remove any remaining non-numeric characters except decimal point
        cleaned = re.sub(r'[^\d.]', '', cleaned)
        
        if not cleaned or cleaned == '.':
            raise ValueError(f"Unable to parse amount: {amount_str}")
        
        try:
            amount = Decimal(cleaned)
            if is_negative:
                amount = -amount
            
            # Round to 2 decimal places for currency precision
            return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as e:
            raise ValueError(f"Unable to parse amount: {amount_str}") from e
    
    def clean_description(self, description: str) -> str:
        """Clean and standardize transaction descriptions"""
        import re
        
        if not description:
            return ""
        
        description = str(description).strip()
        
        # Remove extra whitespace and normalize
        cleaned = ' '.join(description.split())
        
        # Remove common prefixes that add noise
        prefixes_to_remove = [
            r'^DEBIT\s+',
            r'^CREDIT\s+',
            r'^ACH\s+',
            r'^POS\s+',
            r'^ATM\s+',
            r'^CHECK\s+',
            r'^CHECKCARD\s+',
            r'^VISA\s+',
            r'^MASTERCARD\s+',
            r'^AMEX\s+',
        ]
        
        for prefix in prefixes_to_remove:
            cleaned = re.sub(prefix, '', cleaned, flags=re.IGNORECASE)
        
        # Remove transaction IDs and reference numbers that are typically at the end
        # Pattern: remove sequences like "REF#123456" or "TXN#ABC123"
        cleaned = re.sub(r'\s+(REF|TXN|TRACE|AUTH)#?\s*[A-Z0-9]+\s*$', '', cleaned, flags=re.IGNORECASE)
        
        # Remove dates at the end (common in some formats)
        cleaned = re.sub(r'\s+\d{2}/\d{2}/\d{4}\s*$', '', cleaned)
        cleaned = re.sub(r'\s+\d{4}-\d{2}-\d{2}\s*$', '', cleaned)
        
        # Remove excessive punctuation
        cleaned = re.sub(r'[*]{2,}', ' ', cleaned)  # Multiple asterisks
        cleaned = re.sub(r'[-]{2,}', ' ', cleaned)  # Multiple dashes
        cleaned = re.sub(r'[.]{2,}', ' ', cleaned)  # Multiple dots
        
        # Standardize merchant names (remove location codes)
        # Pattern: "MERCHANT NAME #123 CITY ST" -> "MERCHANT NAME"
        cleaned = re.sub(r'\s+#\d+\s+[A-Z]{2,}\s+[A-Z]{2}\s*$', '', cleaned)
        
        # Remove trailing location info like "CITY ST 12345"
        cleaned = re.sub(r'\s+[A-Z]{2,}\s+[A-Z]{2}\s+\d{5}\s*$', '', cleaned)
        
        # Final cleanup: remove extra spaces and trim
        cleaned = ' '.join(cleaned.split()).strip()
        
        return cleaned if cleaned else description.strip()
    
    def extract_institution(self, file_path: str) -> str:
        """Extract institution name from file path or configuration"""
        import os
        
        # Try to extract from file path structure
        path_parts = os.path.normpath(file_path).split(os.sep)
        
        # Look for institution name in path (typically in raw/institution_name/)
        for i, part in enumerate(path_parts):
            if part == 'raw' and i + 1 < len(path_parts):
                institution_name = path_parts[i + 1].lower()
                # Check if we have a mapping for this institution
                mapped_name = self.config.institution_mappings.get(institution_name, institution_name)
                return self._standardize_institution_name(mapped_name)
        
        # Fallback to filename-based extraction
        filename = os.path.basename(file_path).lower()
        
        # Common institution patterns in filenames
        institution_patterns = {
            'chase': ['chase'],
            'bank_of_america': ['bofa', 'bankofamerica', 'boa'],
            'wells_fargo': ['wellsfargo', 'wells'],
            'citi': ['citi', 'citibank'],
            'capital_one': ['capitalone', 'capital'],
            'american_express': ['amex', 'americanexpress'],
            'discover': ['discover'],
            'usaa': ['usaa'],
            'pnc': ['pnc'],
            'td_bank': ['tdbank', 'td'],
            'first_tech': ['firsttech', 'first_tech'],
            'gemini': ['gemini'],
        }
        
        for standard_name, patterns in institution_patterns.items():
            for pattern in patterns:
                if pattern in filename:
                    return self._standardize_institution_name(standard_name)
        
        # Try extracting first part of filename before underscore or dash
        name_parts = filename.replace('-', '_').split('_')
        if name_parts:
            potential_name = name_parts[0]
            if len(potential_name) > 2:  # Avoid single letters or very short strings
                return self._standardize_institution_name(potential_name)
        
        return 'unknown'
    
    def _standardize_institution_name(self, name: str) -> str:
        """Standardize institution name format"""
        if not name:
            return 'unknown'
        
        # Convert to title case and replace underscores with spaces
        standardized = name.replace('_', ' ').title()
        
        # Handle special cases
        special_cases = {
            'Bofa': 'Bank of America',
            'Boa': 'Bank of America',
            'Amex': 'American Express',
            'Usaa': 'USAA',
            'Pnc': 'PNC',
            'Td Bank': 'TD Bank',
            'Td': 'TD Bank',
        }
        
        return special_cases.get(standardized, standardized)
    
    def extract_account(self, file_path: str, transaction_data: Dict) -> str:
        """Extract account identifier from file path or transaction data"""
        import os
        import re
        
        # Try to extract from transaction data first
        if isinstance(transaction_data, dict):
            # Check various possible account field names
            account_fields = ['account', 'account_id', 'account_number', 'acct', 'acct_id']
            for field in account_fields:
                if field in transaction_data and transaction_data[field]:
                    account = str(transaction_data[field]).strip()
                    if account:
                        return self._format_account_number(account)
        
        # Try to extract from filename using various patterns
        filename = os.path.basename(file_path)
        
        # Pattern 1: statements-XXXX- (Chase format)
        match = re.search(r'statements-(\d{4})-', filename, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Pattern 2: InstitutionXXXX_ (Chase format)
        match = re.search(r'chase(\d{4})_', filename, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Pattern 3: Account ending in filename
        match = re.search(r'(\d{4})_activity', filename, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Pattern 4: Look for account-like patterns (4+ consecutive digits)
        account_patterns = [
            r'account[_-]?(\d{4,})',  # account_1234 or account-1234
            r'acct[_-]?(\d{4,})',     # acct_1234 or acct-1234
            r'(\d{4,})[_-]?account',  # 1234_account or 1234-account
            r'(\d{4,})[_-]?acct',     # 1234_acct or 1234-acct
        ]
        
        for pattern in account_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return self._format_account_number(match.group(1))
        
        # Pattern 5: Any sequence of 4+ digits (be more selective)
        digit_matches = re.findall(r'\d{4,}', filename)
        for digits in digit_matches:
            # Skip dates (YYYY, YYYYMMDD patterns)
            if len(digits) == 4 and 1900 <= int(digits) <= 2100:
                continue
            if len(digits) == 8:  # Likely a date YYYYMMDD
                try:
                    year = int(digits[:4])
                    month = int(digits[4:6])
                    day = int(digits[6:8])
                    if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                        continue
                except ValueError:
                    pass
            
            return self._format_account_number(digits)
        
        # Try to extract from directory structure
        path_parts = os.path.normpath(file_path).split(os.sep)
        for part in reversed(path_parts[:-1]):  # Exclude filename
            digit_matches = re.findall(r'\d{4,}', part)
            for digits in digit_matches:
                return self._format_account_number(digits)
        
        return 'unknown'
    
    def _format_account_number(self, account: str) -> str:
        """Format account number consistently"""
        if not account:
            return 'unknown'
        
        account = str(account).strip()
        
        # If it's a long account number, return last 4 digits
        if len(account) > 4 and account.isdigit():
            return account[-4:]
        
        # If it's already 4 digits or less, return as is
        if account.isdigit() and len(account) <= 4:
            return account.zfill(4)  # Pad with zeros if needed
        
        # For non-numeric accounts, clean and truncate
        cleaned = re.sub(r'[^\w]', '', account)
        return cleaned[:8] if len(cleaned) > 8 else cleaned