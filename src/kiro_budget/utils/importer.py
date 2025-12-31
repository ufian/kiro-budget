"""Transaction import module for consolidating processed CSV files.

This module provides functionality to scan, load, deduplicate, and consolidate
all processed transaction CSV files from data/ subdirectories into a single
unified file at data/total/all_transactions.csv.

Requirements: 1.1-1.5, 2.1-2.5, 3.1-3.5, 4.1-4.4, 5.1-5.3
"""

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional, Union

from ..models.core import EnrichedTransaction, Transaction
from .csv_writer import CSVWriter
from .duplicate_detector import DuplicateDetector


class ImportError(Exception):
    """Import operation failure with context.
    
    Provides detailed error information including the file path,
    line number, and field that caused the error.
    
    Requirements: 5.1, 5.2
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        field: Optional[str] = None
    ):
        """Create import error with optional context.
        
        Args:
            message: Error description
            file_path: Path to the file that caused the error
            line_number: Line number where the error occurred
            field: Field name that caused the error
        """
        self.file_path = file_path
        self.line_number = line_number
        self.field = field
        
        context_parts = []
        if file_path:
            context_parts.append(f"file: {file_path}")
        if line_number:
            context_parts.append(f"line: {line_number}")
        if field:
            context_parts.append(f"field: {field}")
        
        context = f" ({', '.join(context_parts)})" if context_parts else ""
        super().__init__(f"{message}{context}")


@dataclass
class ImportResult:
    """Result of an import operation.
    
    Contains statistics and status information about the import.
    
    Requirements: 3.5
    """
    success: bool
    source_files_count: int
    total_input_transactions: int
    duplicates_removed: int
    final_transaction_count: int
    output_file: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# Required columns for valid transaction CSV files
REQUIRED_COLUMNS = [
    'date', 'amount', 'description', 'account',
    'account_name', 'account_type', 'institution'
]


class TransactionImporter:
    """Imports and consolidates transaction CSV files.
    
    Scans data/ subdirectories for processed CSV files, loads and validates
    transactions, deduplicates across files, and writes a consolidated output.
    
    Requirements: 1.1-1.5, 2.1-2.5, 3.1-3.5
    """
    
    def __init__(
        self,
        data_directory: str = "data",
        output_directory: str = "data/total"
    ):
        """Initialize importer with source and output directories.
        
        Args:
            data_directory: Root directory containing processed CSV files
            output_directory: Directory for consolidated output file
        """
        self.data_directory = Path(data_directory)
        self.output_directory = Path(output_directory)
        self.duplicate_detector = DuplicateDetector(date_tolerance_days=3)
    
    def scan_source_files(self) -> List[Path]:
        """Find all CSV files in data subdirectories.
        
        Recursively scans data/ for CSV files, excluding:
        - data/total/ (output directory)
        - data/processed/ (legacy processed directory)
        
        Returns:
            List of Path objects for found CSV files
            
        Requirements: 1.1, 1.4
        """
        csv_files = []
        
        if not self.data_directory.exists():
            return csv_files
        
        # Directories to exclude from scanning
        excluded_dirs = {'total', 'processed', 'reports'}
        
        for item in self.data_directory.iterdir():
            if item.is_dir() and item.name not in excluded_dirs:
                # Scan institution subdirectory
                for csv_file in item.rglob('*.csv'):
                    csv_files.append(csv_file)
        
        return sorted(csv_files)
    
    def validate_csv_structure(self, file_path: Path) -> bool:
        """Check that CSV has required columns.
        
        Args:
            file_path: Path to CSV file to validate
            
        Returns:
            True if valid
            
        Raises:
            ImportError: If required columns are missing
            
        Requirements: 1.2, 1.3
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    raise ImportError(
                        "CSV file is empty or has no headers",
                        file_path=str(file_path)
                    )
                
                headers = set(reader.fieldnames)
                missing = set(REQUIRED_COLUMNS) - headers
                
                if missing:
                    raise ImportError(
                        f"Missing required columns: {', '.join(sorted(missing))}",
                        file_path=str(file_path)
                    )
                
                return True
                
        except csv.Error as e:
            raise ImportError(
                f"Invalid CSV format: {e}",
                file_path=str(file_path)
            )
        except UnicodeDecodeError as e:
            raise ImportError(
                f"File encoding error: {e}",
                file_path=str(file_path)
            )
    
    def load_transactions(self, file_path: Path) -> List[EnrichedTransaction]:
        """Load and validate transactions from a CSV file.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            List of EnrichedTransaction objects
            
        Raises:
            ImportError: If file is invalid or contains bad data
            
        Requirements: 1.5, 5.2
        """
        transactions = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for line_num, row in enumerate(reader, start=2):
                    try:
                        transaction = self._parse_row(row, line_num, file_path)
                        transactions.append(transaction)
                    except ImportError:
                        raise
                    except Exception as e:
                        raise ImportError(
                            f"Failed to parse row: {e}",
                            file_path=str(file_path),
                            line_number=line_num
                        )
        
        except ImportError:
            raise
        except Exception as e:
            raise ImportError(
                f"Failed to read file: {e}",
                file_path=str(file_path)
            )
        
        return transactions
    
    def _parse_row(
        self,
        row: dict,
        line_num: int,
        file_path: Path
    ) -> EnrichedTransaction:
        """Parse a CSV row into an EnrichedTransaction.
        
        Args:
            row: Dictionary from CSV reader
            line_num: Line number for error reporting
            file_path: File path for error reporting
            
        Returns:
            EnrichedTransaction object
            
        Raises:
            ImportError: If parsing fails
        """
        # Parse date
        date_str = row.get('date', '').strip()
        if not date_str:
            raise ImportError(
                "Missing date value",
                file_path=str(file_path),
                line_number=line_num,
                field='date'
            )
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ImportError(
                f"Invalid date format: {date_str}",
                file_path=str(file_path),
                line_number=line_num,
                field='date'
            )
        
        # Parse amount
        amount_str = row.get('amount', '').strip()
        if not amount_str:
            raise ImportError(
                "Missing amount value",
                file_path=str(file_path),
                line_number=line_num,
                field='amount'
            )
        
        try:
            amount = Decimal(amount_str)
        except InvalidOperation:
            raise ImportError(
                f"Invalid amount format: {amount_str}",
                file_path=str(file_path),
                line_number=line_num,
                field='amount'
            )
        
        # Parse balance (optional)
        balance = None
        balance_str = row.get('balance', '').strip()
        if balance_str:
            try:
                balance = Decimal(balance_str)
            except InvalidOperation:
                raise ImportError(
                    f"Invalid balance format: {balance_str}",
                    file_path=str(file_path),
                    line_number=line_num,
                    field='balance'
                )
        
        return EnrichedTransaction(
            date=date,
            amount=amount,
            description=row.get('description', '').strip(),
            account=row.get('account', '').strip(),
            institution=row.get('institution', '').strip(),
            transaction_id=row.get('transaction_id', '').strip() or None,
            category=row.get('category', '').strip() or None,
            balance=balance,
            account_name=row.get('account_name', '').strip(),
            account_type=row.get('account_type', 'debit').strip()
        )

    
    def deduplicate_transactions(
        self,
        transactions: List[EnrichedTransaction]
    ) -> tuple[List[EnrichedTransaction], dict]:
        """Deduplicate transactions using fuzzy matching.
        
        Uses the existing DuplicateDetector with fuzzy matching mode
        (ignore_transaction_ids=True) and 3-day date tolerance.
        
        Args:
            transactions: List of transactions to deduplicate
            
        Returns:
            Tuple of (deduplicated transactions, statistics dict)
            
        Requirements: 2.1, 2.2, 2.5
        """
        if not transactions:
            return [], {'duplicates_removed': 0}
        
        # Convert EnrichedTransaction to Transaction for DuplicateDetector
        # The detector works with Transaction objects
        base_transactions = [
            Transaction(
                date=t.date,
                amount=t.amount,
                description=t.description,
                account=t.account,
                institution=t.institution,
                transaction_id=t.transaction_id,
                category=t.category,
                balance=t.balance
            )
            for t in transactions
        ]
        
        # Create mapping from base transaction object id to enriched data
        # This preserves the exact mapping before deduplication
        id_to_enrichment = {}
        for i, t in enumerate(transactions):
            id_to_enrichment[id(base_transactions[i])] = (t.account_name, t.account_type)
        
        # Also create a lookup by (institution, account) for fallback
        # This handles merged transactions where the object id changes
        institution_account_enrichment = {}
        for t in transactions:
            key = (t.institution.lower() if t.institution else '', t.account or '')
            # Keep the first enrichment found (should be consistent per account)
            if key not in institution_account_enrichment:
                institution_account_enrichment[key] = (t.account_name, t.account_type)
        
        # Use fuzzy matching (ignore transaction IDs for cross-file dedup)
        deduped, stats = self.duplicate_detector.deduplicate_transactions(
            base_transactions,
            use_fuzzy_matching=True
        )
        
        # Convert back to EnrichedTransaction, preserving enrichment data
        result = []
        for t in deduped:
            # First try exact object id lookup (for non-merged transactions)
            if id(t) in id_to_enrichment:
                account_name, account_type = id_to_enrichment[id(t)]
            else:
                # Fallback: lookup by (institution, account) pair
                # This handles merged transactions where a new object was created
                key = (t.institution.lower() if t.institution else '', t.account or '')
                if key in institution_account_enrichment:
                    account_name, account_type = institution_account_enrichment[key]
                else:
                    # Final fallback to defaults
                    account_name = t.account or ''
                    account_type = 'debit'
            
            result.append(EnrichedTransaction(
                date=t.date,
                amount=t.amount,
                description=t.description,
                account=t.account,
                institution=t.institution,
                transaction_id=t.transaction_id,
                category=t.category,
                balance=t.balance,
                account_name=account_name,
                account_type=account_type
            ))
        
        return result, {
            'duplicates_removed': stats.get('total_duplicates_removed', 0),
            'duplicate_groups': stats.get('duplicate_groups_found', 0)
        }
    
    def write_consolidated_output(
        self,
        transactions: List[EnrichedTransaction]
    ) -> str:
        """Write consolidated transactions to output file.
        
        Creates data/total/ directory if needed and writes all transactions
        to all_transactions.csv, sorted by date ascending.
        
        Args:
            transactions: List of deduplicated transactions
            
        Returns:
            Path to output file
            
        Raises:
            ImportError: If output cannot be written
            
        Requirements: 3.1, 3.2, 3.3, 3.4
        """
        # Create output directory
        try:
            self.output_directory.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ImportError(
                f"Cannot create output directory: {e}",
                file_path=str(self.output_directory)
            )
        
        output_file = self.output_directory / "all_transactions.csv"
        
        # Sort transactions by date ascending
        sorted_transactions = sorted(transactions, key=lambda t: t.date)
        
        # Write using standard CSV format
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'date', 'amount', 'description', 'account',
                    'account_name', 'account_type', 'institution',
                    'transaction_id', 'category', 'balance'
                ])
                writer.writeheader()
                
                for t in sorted_transactions:
                    writer.writerow({
                        'date': t.date.strftime('%Y-%m-%d'),
                        'amount': str(t.amount),
                        'description': t.description or '',
                        'account': t.account or '',
                        'account_name': t.account_name or '',
                        'account_type': t.account_type or 'debit',
                        'institution': t.institution or '',
                        'transaction_id': t.transaction_id or '',
                        'category': t.category or '',
                        'balance': str(t.balance) if t.balance is not None else ''
                    })
        except (OSError, csv.Error) as e:
            raise ImportError(
                f"Cannot write output file: {e}",
                file_path=str(output_file)
            )
        
        return str(output_file)
    
    def import_all(self) -> ImportResult:
        """Execute full import pipeline.
        
        Orchestrates: scan → validate → load → deduplicate → write
        
        Returns:
            ImportResult with statistics and status
            
        Raises:
            ImportError: If any file cannot be processed
            
        Requirements: 1.1, 2.2, 3.1, 5.1
        """
        errors = []
        warnings = []
        
        # Step 1: Scan for source files
        source_files = self.scan_source_files()
        
        if not source_files:
            return ImportResult(
                success=True,
                source_files_count=0,
                total_input_transactions=0,
                duplicates_removed=0,
                final_transaction_count=0,
                output_file='',
                errors=[],
                warnings=['No CSV files found in data directory']
            )
        
        # Step 2: Validate and load all transactions
        all_transactions = []
        
        for file_path in source_files:
            # Validate structure
            self.validate_csv_structure(file_path)
            
            # Load transactions
            transactions = self.load_transactions(file_path)
            all_transactions.extend(transactions)
        
        total_input = len(all_transactions)
        
        if not all_transactions:
            return ImportResult(
                success=True,
                source_files_count=len(source_files),
                total_input_transactions=0,
                duplicates_removed=0,
                final_transaction_count=0,
                output_file='',
                errors=[],
                warnings=['No transactions found in source files']
            )
        
        # Step 3: Deduplicate
        deduped_transactions, dedup_stats = self.deduplicate_transactions(
            all_transactions
        )
        
        duplicates_removed = dedup_stats.get('duplicates_removed', 0)
        
        if duplicates_removed > 0:
            warnings.append(
                f"Removed {duplicates_removed} duplicate transactions"
            )
        
        # Step 4: Write consolidated output
        output_file = self.write_consolidated_output(deduped_transactions)
        
        # Verify arithmetic: final = input - duplicates
        final_count = len(deduped_transactions)
        expected_final = total_input - duplicates_removed
        
        if final_count != expected_final:
            warnings.append(
                f"Statistics mismatch: expected {expected_final}, got {final_count}"
            )
        
        return ImportResult(
            success=True,
            source_files_count=len(source_files),
            total_input_transactions=total_input,
            duplicates_removed=duplicates_removed,
            final_transaction_count=final_count,
            output_file=output_file,
            errors=errors,
            warnings=warnings
        )
