"""Processing result tracking and summary reporting for financial data parser."""

import json
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict
from ..models.core import ProcessingResult, Transaction
from .error_handler import ErrorHandler


@dataclass
class FileProcessingState:
    """State information for processed files"""
    file_path: str
    file_hash: str
    last_processed: str
    output_file: str
    transaction_count: int
    success: bool
    processing_time: float
    file_size: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class BatchProcessingSummary:
    """Summary of batch processing operation"""
    start_time: str
    end_time: str
    total_duration: float
    total_files: int
    processed_files: int
    successful_files: int
    failed_files: int
    skipped_files: int
    new_files: int
    updated_files: int
    total_transactions: int
    total_output_files: int
    success_rate: float
    processing_rate: float  # files per second
    errors_by_category: Dict[str, int]
    warnings_by_category: Dict[str, int]
    institution_summary: Dict[str, Dict[str, Any]]
    largest_file: Optional[Dict[str, Any]] = None
    slowest_file: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class ProcessingTracker:
    """Tracks processing results and generates summary reports"""
    
    def __init__(self, 
                 state_directory: str = ".kiro_parser_state",
                 error_handler: Optional[ErrorHandler] = None):
        self.state_directory = Path(state_directory)
        self.state_directory.mkdir(exist_ok=True)
        
        self.state_file = self.state_directory / "processing_state.json"
        self.error_handler = error_handler or ErrorHandler()
        
        # Load existing state
        self.processed_files: Dict[str, FileProcessingState] = self._load_state()
        
        # Current batch tracking
        self.current_batch_results: List[ProcessingResult] = []
        self.batch_start_time: Optional[datetime] = None
        self.institution_stats: Dict[str, Dict[str, Any]] = {}
    
    def _load_state(self) -> Dict[str, FileProcessingState]:
        """Load processing state from disk"""
        if not self.state_file.exists():
            return {}
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            processed_files = {}
            for file_path, state_data in data.get('processed_files', {}).items():
                processed_files[file_path] = FileProcessingState(**state_data)
            
            return processed_files
        
        except Exception as e:
            if self.error_handler:
                self.error_handler.log_error(
                    f"Failed to load processing state: {str(e)}",
                    "CONFIG_FILE_NOT_FOUND",
                    file_path=str(self.state_file),
                    exception=e
                )
            return {}
    
    def _save_state(self):
        """Save processing state to disk"""
        try:
            state_data = {
                'last_updated': datetime.now().isoformat(),
                'processed_files': {
                    file_path: state.to_dict() 
                    for file_path, state in self.processed_files.items()
                }
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
        
        except Exception as e:
            if self.error_handler:
                self.error_handler.log_error(
                    f"Failed to save processing state: {str(e)}",
                    "FILE_PERMISSION_DENIED",
                    file_path=str(self.state_file),
                    exception=e
                )
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate hash of file for change detection"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            # If we can't hash the file, use modification time and size
            try:
                stat = os.stat(file_path)
                return f"mtime_{stat.st_mtime}_size_{stat.st_size}"
            except Exception:
                return "unknown"
    
    def should_process_file(self, file_path: str, force_reprocess: bool = False) -> bool:
        """Determine if a file should be processed"""
        if force_reprocess:
            return True
        
        if file_path not in self.processed_files:
            return True
        
        # Check if file has changed since last processing
        current_hash = self._calculate_file_hash(file_path)
        stored_state = self.processed_files[file_path]
        
        if current_hash != stored_state.file_hash:
            return True
        
        # Check if previous processing was successful
        if not stored_state.success:
            return True
        
        # Check if output file still exists
        if not os.path.exists(stored_state.output_file):
            return True
        
        return False
    
    def start_batch_processing(self):
        """Start tracking a new batch processing operation"""
        self.batch_start_time = datetime.now()
        self.current_batch_results.clear()
        self.institution_stats.clear()
        
        if self.error_handler:
            self.error_handler.log_info("Starting new batch processing operation")
    
    def record_processing_result(self, result: ProcessingResult):
        """Record the result of processing a single file"""
        self.current_batch_results.append(result)
        
        # Update processing state
        file_hash = self._calculate_file_hash(result.file_path)
        file_size = 0
        try:
            file_size = os.path.getsize(result.file_path)
        except Exception:
            pass
        
        state = FileProcessingState(
            file_path=result.file_path,
            file_hash=file_hash,
            last_processed=datetime.now().isoformat(),
            output_file=result.output_file,
            transaction_count=result.transactions_count,
            success=result.success,
            processing_time=result.processing_time,
            file_size=file_size
        )
        
        self.processed_files[result.file_path] = state
        
        # Update institution statistics
        institution = result.institution
        if institution not in self.institution_stats:
            self.institution_stats[institution] = {
                'files_processed': 0,
                'files_successful': 0,
                'files_failed': 0,
                'total_transactions': 0,
                'total_processing_time': 0.0,
                'output_files': []
            }
        
        stats = self.institution_stats[institution]
        stats['files_processed'] += 1
        stats['total_transactions'] += result.transactions_count
        stats['total_processing_time'] += result.processing_time
        
        if result.success:
            stats['files_successful'] += 1
            stats['output_files'].append(result.output_file)
        else:
            stats['files_failed'] += 1
        
        # Save state after each file
        self._save_state()
        
        if self.error_handler:
            status = "successfully" if result.success else "with errors"
            self.error_handler.log_info(
                f"Processed {result.file_path} {status} - "
                f"{result.transactions_count} transactions in {result.processing_time:.2f}s",
                context={
                    'file_path': result.file_path,
                    'institution': result.institution,
                    'transactions': result.transactions_count,
                    'processing_time': result.processing_time,
                    'success': result.success
                }
            )
    
    def generate_batch_summary(self) -> BatchProcessingSummary:
        """Generate summary of current batch processing"""
        if not self.batch_start_time:
            raise ValueError("No batch processing started")
        
        end_time = datetime.now()
        total_duration = (end_time - self.batch_start_time).total_seconds()
        
        # Calculate statistics
        total_files = len(self.current_batch_results)
        successful_files = sum(1 for r in self.current_batch_results if r.success)
        failed_files = total_files - successful_files
        total_transactions = sum(r.transactions_count for r in self.current_batch_results)
        
        # Count new vs updated files
        new_files = 0
        updated_files = 0
        for result in self.current_batch_results:
            if result.file_path in self.processed_files:
                # Check if this was an update (different hash)
                current_hash = self._calculate_file_hash(result.file_path)
                if (result.file_path in self.processed_files and 
                    self.processed_files[result.file_path].file_hash != current_hash):
                    updated_files += 1
                else:
                    new_files += 1
            else:
                new_files += 1
        
        # Processing rate
        processing_rate = total_files / total_duration if total_duration > 0 else 0
        success_rate = (successful_files / total_files * 100) if total_files > 0 else 0
        
        # Error and warning summaries
        errors_by_category = {}
        warnings_by_category = {}
        if self.error_handler:
            error_summary = self.error_handler.get_error_summary()
            errors_by_category = error_summary.get('errors_by_category', {})
            warnings_by_category = error_summary.get('warnings_by_category', {})
        
        # Find largest and slowest files
        largest_file = None
        slowest_file = None
        
        if self.current_batch_results:
            # Largest file by transaction count
            largest_result = max(self.current_batch_results, key=lambda r: r.transactions_count)
            largest_file = {
                'file_path': largest_result.file_path,
                'institution': largest_result.institution,
                'transactions': largest_result.transactions_count,
                'processing_time': largest_result.processing_time
            }
            
            # Slowest file by processing time
            slowest_result = max(self.current_batch_results, key=lambda r: r.processing_time)
            slowest_file = {
                'file_path': slowest_result.file_path,
                'institution': slowest_result.institution,
                'transactions': slowest_result.transactions_count,
                'processing_time': slowest_result.processing_time
            }
        
        # Count unique output files
        output_files = set(r.output_file for r in self.current_batch_results if r.success)
        
        summary = BatchProcessingSummary(
            start_time=self.batch_start_time.isoformat(),
            end_time=end_time.isoformat(),
            total_duration=total_duration,
            total_files=total_files,
            processed_files=total_files,
            successful_files=successful_files,
            failed_files=failed_files,
            skipped_files=0,  # Will be updated by caller if needed
            new_files=new_files,
            updated_files=updated_files,
            total_transactions=total_transactions,
            total_output_files=len(output_files),
            success_rate=success_rate,
            processing_rate=processing_rate,
            errors_by_category=errors_by_category,
            warnings_by_category=warnings_by_category,
            institution_summary=self.institution_stats.copy(),
            largest_file=largest_file,
            slowest_file=slowest_file
        )
        
        return summary
    
    def save_batch_report(self, summary: BatchProcessingSummary, output_file: Optional[str] = None) -> str:
        """Save batch processing report to file"""
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = str(self.state_directory / f"batch_report_{timestamp}.json")
        
        report_data = {
            'report_type': 'batch_processing_summary',
            'generated_at': datetime.now().isoformat(),
            'summary': summary.to_dict(),
            'detailed_results': [
                {
                    'file_path': r.file_path,
                    'institution': r.institution,
                    'transactions_count': r.transactions_count,
                    'output_file': r.output_file,
                    'processing_time': r.processing_time,
                    'success': r.success,
                    'error_count': len(r.errors),
                    'warning_count': len(r.warnings)
                }
                for r in self.current_batch_results
            ]
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            
            if self.error_handler:
                self.error_handler.log_info(f"Batch processing report saved: {output_file}")
            
            return output_file
        
        except Exception as e:
            if self.error_handler:
                self.error_handler.log_error(
                    f"Failed to save batch report: {str(e)}",
                    "FILE_PERMISSION_DENIED",
                    file_path=output_file,
                    exception=e
                )
            raise
    
    def get_processing_history(self, 
                             institution: Optional[str] = None,
                             days_back: int = 30) -> List[FileProcessingState]:
        """Get processing history for files"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        history = []
        for state in self.processed_files.values():
            try:
                processed_date = datetime.fromisoformat(state.last_processed)
                if processed_date >= cutoff_date:
                    if institution is None or institution.lower() in state.file_path.lower():
                        history.append(state)
            except ValueError:
                # Skip entries with invalid dates
                continue
        
        # Sort by processing date, most recent first
        history.sort(key=lambda s: s.last_processed, reverse=True)
        return history
    
    def get_duplicate_prevention_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get information about previous processing to prevent duplicates"""
        if file_path not in self.processed_files:
            return None
        
        state = self.processed_files[file_path]
        current_hash = self._calculate_file_hash(file_path)
        
        return {
            'previously_processed': True,
            'last_processed': state.last_processed,
            'previous_success': state.success,
            'previous_transaction_count': state.transaction_count,
            'previous_output_file': state.output_file,
            'file_changed': current_hash != state.file_hash,
            'output_file_exists': os.path.exists(state.output_file),
            'should_reprocess': self.should_process_file(file_path)
        }
    
    def cleanup_old_state(self, days_to_keep: int = 90):
        """Clean up old processing state entries"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        files_to_remove = []
        for file_path, state in self.processed_files.items():
            try:
                processed_date = datetime.fromisoformat(state.last_processed)
                if processed_date < cutoff_date:
                    # Only remove if the file no longer exists
                    if not os.path.exists(file_path):
                        files_to_remove.append(file_path)
            except ValueError:
                # Remove entries with invalid dates
                files_to_remove.append(file_path)
        
        for file_path in files_to_remove:
            del self.processed_files[file_path]
        
        if files_to_remove:
            self._save_state()
            if self.error_handler:
                self.error_handler.log_info(
                    f"Cleaned up {len(files_to_remove)} old processing state entries"
                )
    
    def get_institution_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics by institution from all processed files"""
        stats = {}
        
        for state in self.processed_files.values():
            # Extract institution from file path
            institution = self._extract_institution_from_path(state.file_path)
            
            if institution not in stats:
                stats[institution] = {
                    'total_files': 0,
                    'successful_files': 0,
                    'failed_files': 0,
                    'total_transactions': 0,
                    'avg_processing_time': 0.0,
                    'last_processed': None,
                    'output_files': []
                }
            
            inst_stats = stats[institution]
            inst_stats['total_files'] += 1
            inst_stats['total_transactions'] += state.transaction_count
            
            if state.success:
                inst_stats['successful_files'] += 1
                if state.output_file not in inst_stats['output_files']:
                    inst_stats['output_files'].append(state.output_file)
            else:
                inst_stats['failed_files'] += 1
            
            # Update last processed date
            if (inst_stats['last_processed'] is None or 
                state.last_processed > inst_stats['last_processed']):
                inst_stats['last_processed'] = state.last_processed
        
        # Calculate averages
        for inst_stats in stats.values():
            if inst_stats['total_files'] > 0:
                total_time = sum(
                    state.processing_time 
                    for state in self.processed_files.values()
                    if self._extract_institution_from_path(state.file_path) in stats
                )
                inst_stats['avg_processing_time'] = total_time / inst_stats['total_files']
        
        return stats
    
    def _extract_institution_from_path(self, file_path: str) -> str:
        """Extract institution name from file path"""
        path_parts = Path(file_path).parts
        
        # Look for institution name in path (typically in raw/institution_name/)
        for i, part in enumerate(path_parts):
            if part == 'raw' and i + 1 < len(path_parts):
                return path_parts[i + 1].lower().replace('_', ' ').title()
        
        # Fallback to filename-based extraction
        filename = Path(file_path).stem.lower()
        
        # Common institution patterns
        if 'chase' in filename:
            return 'Chase'
        elif 'bofa' in filename or 'bankofamerica' in filename:
            return 'Bank of America'
        elif 'wells' in filename:
            return 'Wells Fargo'
        elif 'citi' in filename:
            return 'Citibank'
        elif 'amex' in filename:
            return 'American Express'
        elif 'firsttech' in filename:
            return 'First Tech'
        elif 'gemini' in filename:
            return 'Gemini'
        
        return 'Unknown'