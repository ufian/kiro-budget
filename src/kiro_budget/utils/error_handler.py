"""Comprehensive error handling and logging system for financial data parser."""

import json
import logging
import traceback
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
import sys


class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""
    FILE_ACCESS = "file_access"
    FILE_FORMAT = "file_format"
    DATA_PARSING = "data_parsing"
    DATA_VALIDATION = "data_validation"
    CONFIGURATION = "configuration"
    SYSTEM = "system"
    PLUGIN = "plugin"
    NETWORK = "network"


@dataclass
class ErrorDetail:
    """Detailed error information"""
    timestamp: str
    severity: str
    category: str
    error_code: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    field_name: Optional[str] = None
    raw_value: Optional[str] = None
    expected_format: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class ProcessingProgress:
    """Progress tracking for batch operations"""
    total_files: int
    processed_files: int
    successful_files: int
    failed_files: int
    skipped_files: int
    current_file: Optional[str] = None
    start_time: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage"""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.processed_files == 0:
            return 0.0
        return (self.successful_files / self.processed_files) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'successful_files': self.successful_files,
            'failed_files': self.failed_files,
            'skipped_files': self.skipped_files,
            'current_file': self.current_file,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
            'completion_percentage': self.completion_percentage,
            'success_rate': self.success_rate
        }


class ErrorHandler:
    """Comprehensive error handling and logging system"""
    
    def __init__(self, log_directory: str = "logs", enable_console: bool = True):
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(exist_ok=True)
        
        self.errors: List[ErrorDetail] = []
        self.warnings: List[ErrorDetail] = []
        self.progress: Optional[ProcessingProgress] = None
        
        # Set up structured logging
        self._setup_logging(enable_console)
        
        # Error code mappings
        self.error_codes = {
            # File access errors
            "FILE_NOT_FOUND": "F001",
            "FILE_PERMISSION_DENIED": "F002",
            "FILE_CORRUPTED": "F003",
            "DIRECTORY_NOT_FOUND": "F004",
            "DISK_SPACE_INSUFFICIENT": "F005",
            
            # File format errors
            "UNSUPPORTED_FORMAT": "F101",
            "MALFORMED_FILE": "F102",
            "INVALID_HEADER": "F103",
            "MISSING_REQUIRED_COLUMNS": "F104",
            "ENCODING_ERROR": "F105",
            
            # Data parsing errors
            "DATE_PARSE_ERROR": "D001",
            "AMOUNT_PARSE_ERROR": "D002",
            "INVALID_TRANSACTION_ID": "D003",
            "MISSING_REQUIRED_FIELD": "D004",
            "DATA_TYPE_MISMATCH": "D005",
            
            # Data validation errors
            "DUPLICATE_TRANSACTION": "V001",
            "INVALID_DATE_RANGE": "V002",
            "AMOUNT_OUT_OF_RANGE": "V003",
            "INVALID_ACCOUNT_FORMAT": "V004",
            "CROSS_FIELD_VALIDATION_ERROR": "V005",
            
            # Configuration errors
            "CONFIG_FILE_NOT_FOUND": "C001",
            "INVALID_CONFIG_FORMAT": "C002",
            "MISSING_CONFIG_PARAMETER": "C003",
            "INVALID_CONFIG_VALUE": "C004",
            
            # System errors
            "MEMORY_ERROR": "S001",
            "TIMEOUT_ERROR": "S002",
            "NETWORK_ERROR": "S003",
            "PLUGIN_LOAD_ERROR": "S004",
            "UNEXPECTED_ERROR": "S999"
        }
    
    def _setup_logging(self, enable_console: bool):
        """Set up structured JSON logging"""
        # Create logger
        self.logger = logging.getLogger('financial_parser')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # JSON formatter
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                
                # Add extra fields if present
                if hasattr(record, 'error_code'):
                    log_entry['error_code'] = record.error_code
                if hasattr(record, 'file_path'):
                    log_entry['file_path'] = record.file_path
                if hasattr(record, 'category'):
                    log_entry['category'] = record.category
                if hasattr(record, 'context'):
                    log_entry['context'] = record.context
                
                return json.dumps(log_entry)
        
        # File handler for JSON logs
        log_file = self.log_directory / f"parser_{datetime.now().strftime('%Y%m%d')}.jsonl"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)
        
        # Console handler for human-readable logs
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        
        # Error file handler for errors only
        error_file = self.log_directory / f"errors_{datetime.now().strftime('%Y%m%d')}.jsonl"
        error_handler = logging.FileHandler(error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(error_handler)
    
    def log_error(self, 
                  message: str,
                  error_type: str,
                  category: ErrorCategory = ErrorCategory.SYSTEM,
                  file_path: Optional[str] = None,
                  line_number: Optional[int] = None,
                  field_name: Optional[str] = None,
                  raw_value: Optional[str] = None,
                  expected_format: Optional[str] = None,
                  exception: Optional[Exception] = None,
                  context: Optional[Dict[str, Any]] = None) -> ErrorDetail:
        """Log an error with detailed information"""
        
        error_code = self.error_codes.get(error_type, "S999")
        stack_trace = None
        
        if exception:
            stack_trace = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
            stack_trace = ''.join(stack_trace)
        
        error_detail = ErrorDetail(
            timestamp=datetime.now().isoformat(),
            severity=ErrorSeverity.ERROR.value,
            category=category.value,
            error_code=error_code,
            message=message,
            file_path=file_path,
            line_number=line_number,
            field_name=field_name,
            raw_value=raw_value,
            expected_format=expected_format,
            stack_trace=stack_trace,
            context=context or {}
        )
        
        self.errors.append(error_detail)
        
        # Log to structured logger
        self.logger.error(
            message,
            extra={
                'error_code': error_code,
                'category': category.value,
                'file_path': file_path,
                'context': context or {}
            }
        )
        
        return error_detail
    
    def log_warning(self,
                   message: str,
                   warning_type: str,
                   category: ErrorCategory = ErrorCategory.SYSTEM,
                   file_path: Optional[str] = None,
                   context: Optional[Dict[str, Any]] = None) -> ErrorDetail:
        """Log a warning with detailed information"""
        
        warning_code = self.error_codes.get(warning_type, "W999")
        
        warning_detail = ErrorDetail(
            timestamp=datetime.now().isoformat(),
            severity=ErrorSeverity.WARNING.value,
            category=category.value,
            error_code=warning_code,
            message=message,
            file_path=file_path,
            context=context or {}
        )
        
        self.warnings.append(warning_detail)
        
        # Log to structured logger
        self.logger.warning(
            message,
            extra={
                'error_code': warning_code,
                'category': category.value,
                'file_path': file_path,
                'context': context or {}
            }
        )
        
        return warning_detail
    
    def log_info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log informational message"""
        self.logger.info(message, extra={'context': context or {}})
    
    def log_debug(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log debug message"""
        self.logger.debug(message, extra={'context': context or {}})
    
    def start_progress_tracking(self, total_files: int) -> ProcessingProgress:
        """Start tracking progress for batch operations"""
        self.progress = ProcessingProgress(
            total_files=total_files,
            processed_files=0,
            successful_files=0,
            failed_files=0,
            skipped_files=0,
            start_time=datetime.now()
        )
        
        self.log_info(f"Starting batch processing of {total_files} files")
        return self.progress
    
    def update_progress(self, 
                       current_file: Optional[str] = None,
                       success: Optional[bool] = None,
                       skipped: bool = False):
        """Update progress tracking"""
        if not self.progress:
            return
        
        if current_file:
            self.progress.current_file = current_file
        
        if success is not None or skipped:
            self.progress.processed_files += 1
            
            if skipped:
                self.progress.skipped_files += 1
            elif success:
                self.progress.successful_files += 1
            else:
                self.progress.failed_files += 1
        
        # Estimate completion time
        if self.progress.start_time and self.progress.processed_files > 0:
            elapsed = datetime.now() - self.progress.start_time
            avg_time_per_file = elapsed / self.progress.processed_files
            remaining_files = self.progress.total_files - self.progress.processed_files
            self.progress.estimated_completion = datetime.now() + (avg_time_per_file * remaining_files)
        
        # Log progress periodically
        if self.progress.processed_files % 10 == 0 or self.progress.processed_files == self.progress.total_files:
            self.log_info(
                f"Progress: {self.progress.completion_percentage:.1f}% "
                f"({self.progress.processed_files}/{self.progress.total_files}) - "
                f"Success rate: {self.progress.success_rate:.1f}%",
                context={
                    'progress': {
                        'total': self.progress.total_files,
                        'processed': self.progress.processed_files,
                        'successful': self.progress.successful_files,
                        'failed': self.progress.failed_files,
                        'skipped': self.progress.skipped_files,
                        'completion_percentage': self.progress.completion_percentage,
                        'success_rate': self.progress.success_rate
                    }
                }
            )
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all errors and warnings"""
        error_by_category = {}
        warning_by_category = {}
        
        for error in self.errors:
            category = error.category
            if category not in error_by_category:
                error_by_category[category] = []
            error_by_category[category].append(error)
        
        for warning in self.warnings:
            category = warning.category
            if category not in warning_by_category:
                warning_by_category[category] = []
            warning_by_category[category].append(warning)
        
        summary = {
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings),
            'errors_by_category': {k: len(v) for k, v in error_by_category.items()},
            'warnings_by_category': {k: len(v) for k, v in warning_by_category.items()},
            'most_common_errors': self._get_most_common_errors(),
            'files_with_errors': len(set(e.file_path for e in self.errors if e.file_path)),
            'progress': self.progress.to_dict() if self.progress else None
        }
        
        return summary
    
    def _get_most_common_errors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most common error types"""
        error_counts = {}
        
        for error in self.errors:
            key = f"{error.error_code}: {error.message}"
            if key not in error_counts:
                error_counts[key] = {
                    'error_code': error.error_code,
                    'message': error.message,
                    'category': error.category,
                    'count': 0,
                    'files': set()
                }
            error_counts[key]['count'] += 1
            if error.file_path:
                error_counts[key]['files'].add(error.file_path)
        
        # Convert sets to lists for JSON serialization
        for error_info in error_counts.values():
            error_info['files'] = list(error_info['files'])
        
        # Sort by count and return top errors
        sorted_errors = sorted(error_counts.values(), key=lambda x: x['count'], reverse=True)
        return sorted_errors[:limit]
    
    def generate_error_report(self, output_file: Optional[str] = None) -> str:
        """Generate comprehensive error report"""
        if output_file is None:
            output_file = str(self.log_directory / f"error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'summary': self.get_error_summary(),
            'all_errors': [error.to_dict() for error in self.errors],
            'all_warnings': [warning.to_dict() for warning in self.warnings]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.log_info(f"Error report generated: {output_file}")
        return output_file
    
    def clear_errors(self):
        """Clear all accumulated errors and warnings"""
        self.errors.clear()
        self.warnings.clear()
        self.progress = None
        self.log_info("Error history cleared")
    
    def has_errors(self) -> bool:
        """Check if any errors have been logged"""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if any warnings have been logged"""
        return len(self.warnings) > 0
    
    def get_errors_for_file(self, file_path: str) -> List[ErrorDetail]:
        """Get all errors for a specific file"""
        return [error for error in self.errors if error.file_path == file_path]
    
    def get_warnings_for_file(self, file_path: str) -> List[ErrorDetail]:
        """Get all warnings for a specific file"""
        return [warning for warning in self.warnings if warning.file_path == file_path]


# Convenience functions for common error scenarios
def handle_file_access_error(error_handler: ErrorHandler, 
                           file_path: str, 
                           exception: Exception) -> ErrorDetail:
    """Handle common file access errors"""
    if isinstance(exception, FileNotFoundError):
        return error_handler.log_error(
            f"File not found: {file_path}",
            "FILE_NOT_FOUND",
            ErrorCategory.FILE_ACCESS,
            file_path=file_path,
            exception=exception
        )
    elif isinstance(exception, PermissionError):
        return error_handler.log_error(
            f"Permission denied accessing file: {file_path}",
            "FILE_PERMISSION_DENIED",
            ErrorCategory.FILE_ACCESS,
            file_path=file_path,
            exception=exception
        )
    else:
        return error_handler.log_error(
            f"File access error: {str(exception)}",
            "UNEXPECTED_ERROR",
            ErrorCategory.FILE_ACCESS,
            file_path=file_path,
            exception=exception
        )


def handle_parsing_error(error_handler: ErrorHandler,
                        file_path: str,
                        field_name: str,
                        raw_value: str,
                        expected_format: str,
                        line_number: Optional[int] = None,
                        exception: Optional[Exception] = None) -> ErrorDetail:
    """Handle data parsing errors"""
    if 'date' in field_name.lower():
        error_type = "DATE_PARSE_ERROR"
    elif 'amount' in field_name.lower() or 'money' in field_name.lower():
        error_type = "AMOUNT_PARSE_ERROR"
    else:
        error_type = "DATA_TYPE_MISMATCH"
    
    return error_handler.log_error(
        f"Failed to parse {field_name}: '{raw_value}' (expected format: {expected_format})",
        error_type,
        ErrorCategory.DATA_PARSING,
        file_path=file_path,
        line_number=line_number,
        field_name=field_name,
        raw_value=raw_value,
        expected_format=expected_format,
        exception=exception
    )


def handle_validation_error(error_handler: ErrorHandler,
                          file_path: str,
                          message: str,
                          field_name: Optional[str] = None,
                          raw_value: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None) -> ErrorDetail:
    """Handle data validation errors"""
    return error_handler.log_error(
        message,
        "CROSS_FIELD_VALIDATION_ERROR",
        ErrorCategory.DATA_VALIDATION,
        file_path=file_path,
        field_name=field_name,
        raw_value=raw_value,
        context=context
    )