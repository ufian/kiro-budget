"""CSV output writer with standardized formatting and organization."""

import os
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ..models.core import Transaction, ParserConfig, ProcessingResult


class CSVWriter:
    """Handles CSV output with standardized formatting and organization"""
    
    # Standard CSV column headers in the unified format
    STANDARD_HEADERS = [
        'date',
        'amount', 
        'description',
        'account',
        'institution',
        'transaction_id',
        'category',
        'balance'
    ]
    
    def __init__(self, config: ParserConfig):
        self.config = config
    
    def write_transactions(self, transactions: List[Transaction], output_path: str) -> bool:
        """
        Write transactions to CSV file with standardized format
        
        Args:
            transactions: List of Transaction objects to write
            output_path: Path where CSV file should be written
            
        Returns:
            True if successful, False otherwise
        """
        if not transactions:
            return False
        
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.STANDARD_HEADERS)
                
                # Write header row
                writer.writeheader()
                
                # Write transaction data
                for transaction in transactions:
                    row = self._transaction_to_dict(transaction)
                    writer.writerow(row)
            
            return True
            
        except (OSError, PermissionError, csv.Error) as e:
            return False
    
    def generate_output_path(self, transactions: List[Transaction], source_file_path: str) -> str:
        """
        Generate output file path based on transactions and configuration
        
        Args:
            transactions: List of transactions to determine date range and institution
            source_file_path: Original source file path for context
            
        Returns:
            Generated output file path
        """
        if not transactions:
            # Fallback for empty transaction list
            institution = self._extract_institution_from_path(source_file_path)
            account = self._extract_account_from_path(source_file_path)
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"{institution}_{account}_{timestamp}.csv"
            return os.path.join(self.config.data_directory, institution, filename)
        
        # Extract information from transactions
        institution = transactions[0].institution.lower().replace(' ', '_')
        account = transactions[0].account
        
        # Find date range
        dates = [t.date for t in transactions]
        start_date = min(dates).strftime("%Y%m%d")
        end_date = max(dates).strftime("%Y%m%d")
        
        # Generate filename using pattern
        filename_vars = {
            'institution': institution,
            'account': account,
            'start_date': start_date,
            'end_date': end_date
        }
        
        try:
            filename = self.config.output_filename_pattern.format(**filename_vars)
        except KeyError:
            # Fallback if pattern has invalid variables
            filename = f"{institution}_{account}_{start_date}_{end_date}.csv"
        
        # Ensure filename ends with .csv
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        
        # Create institution-based directory structure
        institution_dir = os.path.join(self.config.data_directory, institution)
        return os.path.join(institution_dir, filename)
    
    def create_unique_filename(self, base_path: str) -> str:
        """
        Create unique filename if file already exists
        
        Args:
            base_path: Base file path
            
        Returns:
            Unique file path (may have suffix added)
        """
        if not os.path.exists(base_path):
            return base_path
        
        # Split path and extension
        path_without_ext, ext = os.path.splitext(base_path)
        
        # Try adding incrementing numbers
        counter = 1
        while counter <= 999:  # Reasonable limit
            new_path = f"{path_without_ext}_{counter:03d}{ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1
        
        # If we can't find a unique name, add timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{path_without_ext}_{timestamp}{ext}"
    
    def organize_output_by_institution(self, transactions_by_file: Dict[str, List[Transaction]]) -> Dict[str, str]:
        """
        Organize multiple files by institution and generate output paths
        
        Args:
            transactions_by_file: Dictionary mapping source file paths to transaction lists
            
        Returns:
            Dictionary mapping source file paths to output file paths
        """
        output_paths = {}
        
        for source_file, transactions in transactions_by_file.items():
            if transactions:  # Only process files with transactions
                output_path = self.generate_output_path(transactions, source_file)
                
                # Ensure unique filename
                unique_path = self.create_unique_filename(output_path)
                output_paths[source_file] = unique_path
        
        return output_paths
    
    def write_multiple_files(self, transactions_by_file: Dict[str, List[Transaction]]) -> Dict[str, ProcessingResult]:
        """
        Write multiple transaction files with proper organization
        
        Args:
            transactions_by_file: Dictionary mapping source file paths to transaction lists
            
        Returns:
            Dictionary mapping source file paths to ProcessingResult objects
        """
        results = {}
        output_paths = self.organize_output_by_institution(transactions_by_file)
        
        for source_file, transactions in transactions_by_file.items():
            start_time = datetime.now()
            
            if source_file not in output_paths:
                # No output path generated (likely no transactions)
                results[source_file] = ProcessingResult(
                    file_path=source_file,
                    institution='unknown',
                    transactions_count=0,
                    output_file='',
                    processing_time=0.0,
                    errors=['No transactions to write'],
                    warnings=[],
                    success=False
                )
                continue
            
            output_path = output_paths[source_file]
            success = self.write_transactions(transactions, output_path)
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            institution = transactions[0].institution if transactions else 'unknown'
            
            results[source_file] = ProcessingResult(
                file_path=source_file,
                institution=institution,
                transactions_count=len(transactions),
                output_file=output_path if success else '',
                processing_time=processing_time,
                errors=[] if success else ['Failed to write CSV file'],
                warnings=[],
                success=success
            )
        
        return results
    
    def validate_csv_output(self, csv_path: str) -> List[str]:
        """
        Validate generated CSV file for data integrity
        
        Args:
            csv_path: Path to CSV file to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not os.path.exists(csv_path):
            errors.append(f"CSV file does not exist: {csv_path}")
            return errors
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Check headers
                if reader.fieldnames != self.STANDARD_HEADERS:
                    errors.append(f"Invalid headers. Expected: {self.STANDARD_HEADERS}, Got: {reader.fieldnames}")
                
                row_count = 0
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                    row_count += 1
                    
                    # Validate required fields
                    if not row.get('date'):
                        errors.append(f"Row {row_num}: Missing date")
                    
                    if not row.get('amount'):
                        errors.append(f"Row {row_num}: Missing amount")
                    
                    if not row.get('description'):
                        errors.append(f"Row {row_num}: Missing description")
                    
                    # Validate date format
                    if row.get('date'):
                        try:
                            datetime.strptime(row['date'], '%Y-%m-%d')
                        except ValueError:
                            errors.append(f"Row {row_num}: Invalid date format: {row['date']}")
                    
                    # Validate amount format
                    if row.get('amount'):
                        try:
                            float(row['amount'])
                        except ValueError:
                            errors.append(f"Row {row_num}: Invalid amount format: {row['amount']}")
                
                if row_count == 0:
                    errors.append("CSV file contains no data rows")
                    
        except (csv.Error, UnicodeDecodeError) as e:
            errors.append(f"Error reading CSV file: {str(e)}")
        
        return errors
    
    def create_directory_structure(self, institutions: List[str]) -> bool:
        """
        Create directory structure for institutions
        
        Args:
            institutions: List of institution names
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create main data directory
            os.makedirs(self.config.data_directory, exist_ok=True)
            
            # Create institution subdirectories
            for institution in institutions:
                institution_dir = os.path.join(
                    self.config.data_directory, 
                    institution.lower().replace(' ', '_')
                )
                os.makedirs(institution_dir, exist_ok=True)
            
            return True
            
        except (OSError, PermissionError):
            return False
    
    def _transaction_to_dict(self, transaction: Transaction) -> Dict[str, str]:
        """Convert Transaction object to dictionary for CSV writing"""
        return {
            'date': transaction.date.strftime('%Y-%m-%d'),
            'amount': str(transaction.amount),
            'description': transaction.description or '',
            'account': transaction.account or '',
            'institution': transaction.institution or '',
            'transaction_id': transaction.transaction_id or '',
            'category': transaction.category or '',
            'balance': str(transaction.balance) if transaction.balance is not None else ''
        }
    
    def _extract_institution_from_path(self, file_path: str) -> str:
        """Extract institution name from file path as fallback"""
        path_parts = os.path.normpath(file_path).split(os.sep)
        
        # Look for institution name in path (typically in raw/institution_name/)
        for i, part in enumerate(path_parts):
            if part == 'raw' and i + 1 < len(path_parts):
                return path_parts[i + 1].lower().replace(' ', '_')
        
        return 'unknown'
    
    def _extract_account_from_path(self, file_path: str) -> str:
        """Extract account identifier from file path as fallback"""
        import re
        
        filename = os.path.basename(file_path)
        
        # Look for account-like patterns in filename
        patterns = [
            r'statements-(\d{4})-',  # Chase format
            r'(\d{4})_activity',     # Activity format
            r'account[_-]?(\d{4,})', # Account patterns
            r'(\d{4,})'              # Any 4+ digit sequence
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return 'unknown'


class OutputOrganizer:
    """Organizes output files by institution and manages directory structure"""
    
    def __init__(self, config: ParserConfig):
        self.config = config
        self.csv_writer = CSVWriter(config)
    
    def organize_by_institution(self, processing_results: Dict[str, ProcessingResult]) -> Dict[str, List[ProcessingResult]]:
        """
        Group processing results by institution
        
        Args:
            processing_results: Dictionary of processing results
            
        Returns:
            Dictionary mapping institution names to lists of processing results
        """
        institution_groups = {}
        
        for result in processing_results.values():
            institution = result.institution.lower().replace(' ', '_')
            
            if institution not in institution_groups:
                institution_groups[institution] = []
            
            institution_groups[institution].append(result)
        
        return institution_groups
    
    def create_institution_directories(self, processing_results: Dict[str, ProcessingResult]) -> bool:
        """
        Create directory structure based on processing results
        
        Args:
            processing_results: Dictionary of processing results
            
        Returns:
            True if successful, False otherwise
        """
        institutions = set()
        
        for result in processing_results.values():
            if result.institution and result.institution != 'unknown':
                institutions.add(result.institution)
        
        return self.csv_writer.create_directory_structure(list(institutions))
    
    def generate_summary_report(self, processing_results: Dict[str, ProcessingResult]) -> Dict[str, any]:
        """
        Generate summary report of processing results
        
        Args:
            processing_results: Dictionary of processing results
            
        Returns:
            Summary report dictionary
        """
        total_files = len(processing_results)
        successful_files = sum(1 for r in processing_results.values() if r.success)
        failed_files = total_files - successful_files
        total_transactions = sum(r.transactions_count for r in processing_results.values())
        total_processing_time = sum(r.processing_time for r in processing_results.values())
        
        # Group by institution
        institution_stats = {}
        for result in processing_results.values():
            inst = result.institution
            if inst not in institution_stats:
                institution_stats[inst] = {
                    'files': 0,
                    'transactions': 0,
                    'successful': 0,
                    'failed': 0
                }
            
            institution_stats[inst]['files'] += 1
            institution_stats[inst]['transactions'] += result.transactions_count
            if result.success:
                institution_stats[inst]['successful'] += 1
            else:
                institution_stats[inst]['failed'] += 1
        
        # Collect all errors and warnings
        all_errors = []
        all_warnings = []
        for result in processing_results.values():
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)
        
        return {
            'total_files': total_files,
            'successful_files': successful_files,
            'failed_files': failed_files,
            'total_transactions': total_transactions,
            'total_processing_time': total_processing_time,
            'institution_stats': institution_stats,
            'errors': all_errors,
            'warnings': all_warnings,
            'timestamp': datetime.now().isoformat()
        }