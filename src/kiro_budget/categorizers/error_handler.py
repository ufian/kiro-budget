"""
Comprehensive error handling for the transaction categorization system.
Provides fallback mechanisms, logging, and recovery strategies.
"""

import logging
import traceback
from typing import Optional, Dict, Any, List, Callable, Union
from enum import Enum
from datetime import datetime
import functools

from .models import Transaction, CategoryResult


class ErrorSeverity(Enum):
    """Error severity levels for categorization failures."""
    LOW = "low"           # Non-critical errors that don't affect core functionality
    MEDIUM = "medium"     # Errors that degrade functionality but have fallbacks
    HIGH = "high"         # Critical errors that prevent categorization
    CRITICAL = "critical" # System-level errors that require immediate attention


class ErrorCategory(Enum):
    """Categories of errors in the categorization system."""
    EXTERNAL_SERVICE = "external_service"     # AI API, external lookup failures
    DATA_VALIDATION = "data_validation"       # Invalid input data
    CONFIGURATION = "configuration"           # Config file or setup issues
    STORAGE = "storage"                      # File I/O, database issues
    PROCESSING = "processing"                # Internal processing errors
    NETWORK = "network"                      # Network connectivity issues
    AUTHENTICATION = "authentication"        # API key or auth failures
    RATE_LIMIT = "rate_limit"               # API rate limiting
    RESOURCE = "resource"                    # Memory, disk space issues


class CategorizationError(Exception):
    """Base exception for categorization system errors."""
    
    def __init__(self, message: str, category: ErrorCategory, 
                 severity: ErrorSeverity, details: Dict[str, Any] = None):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.timestamp = datetime.now()


class ExternalServiceError(CategorizationError):
    """Error for external service failures (AI APIs, etc.)."""
    
    def __init__(self, service: str, message: str, details: Dict[str, Any] = None):
        super().__init__(
            f"External service '{service}' failed: {message}",
            ErrorCategory.EXTERNAL_SERVICE,
            ErrorSeverity.MEDIUM,
            details
        )
        self.service = service


class DataValidationError(CategorizationError):
    """Error for invalid input data."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        details = {}
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = str(value)
        
        super().__init__(
            f"Data validation failed: {message}",
            ErrorCategory.DATA_VALIDATION,
            ErrorSeverity.HIGH,
            details
        )


class ConfigurationError(CategorizationError):
    """Error for configuration issues."""
    
    def __init__(self, message: str, config_section: str = None):
        details = {}
        if config_section:
            details['config_section'] = config_section
        
        super().__init__(
            f"Configuration error: {message}",
            ErrorCategory.CONFIGURATION,
            ErrorSeverity.HIGH,
            details
        )


class ErrorHandler:
    """
    Centralized error handling for the categorization system.
    Provides logging, fallback mechanisms, and recovery strategies.
    """
    
    def __init__(self, logger_name: str = __name__):
        """
        Initialize error handler.
        
        Args:
            logger_name: Name for the logger instance
        """
        self.logger = logging.getLogger(logger_name)
        self.error_counts = {}
        self.fallback_strategies = {}
        self.recovery_callbacks = {}
        
        # Configure default fallback strategies
        self._setup_default_fallbacks()
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Optional[Any]:
        """
        Handle an error with appropriate logging and fallback mechanisms.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            
        Returns:
            Result from fallback strategy if available, None otherwise
        """
        context = context or {}
        
        # Determine error category and severity
        if isinstance(error, CategorizationError):
            category = error.category
            severity = error.severity
        else:
            category, severity = self._classify_error(error)
        
        # Log the error
        self._log_error(error, category, severity, context)
        
        # Update error statistics
        self._update_error_stats(category, severity)
        
        # Try fallback strategy
        fallback_result = self._try_fallback(error, category, context)
        
        # Execute recovery callback if configured
        self._execute_recovery_callback(category, error, context)
        
        return fallback_result
    
    def with_error_handling(self, fallback_value: Any = None, 
                           reraise: bool = False):
        """
        Decorator for automatic error handling.
        
        Args:
            fallback_value: Value to return if error occurs
            reraise: Whether to reraise the exception after handling
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    context = {
                        'function': func.__name__,
                        'args': str(args)[:200],  # Truncate for logging
                        'kwargs': str(kwargs)[:200]
                    }
                    
                    result = self.handle_error(e, context)
                    
                    if reraise:
                        raise
                    
                    return result if result is not None else fallback_value
            
            return wrapper
        return decorator
    
    def validate_transaction(self, transaction: Transaction) -> Transaction:
        """
        Validate and sanitize transaction data.
        
        Args:
            transaction: Transaction to validate
            
        Returns:
            Validated transaction
            
        Raises:
            DataValidationError: If validation fails
        """
        if not transaction:
            raise DataValidationError("Transaction cannot be None")
        
        # Validate required fields
        if not hasattr(transaction, 'description') or not transaction.description:
            raise DataValidationError("Transaction description is required", 'description')
        
        if not hasattr(transaction, 'amount') or transaction.amount is None:
            raise DataValidationError("Transaction amount is required", 'amount')
        
        if not hasattr(transaction, 'date') or not transaction.date:
            raise DataValidationError("Transaction date is required", 'date')
        
        # Sanitize description
        if len(transaction.description) > 1000:
            self.logger.warning(f"Transaction description truncated from {len(transaction.description)} characters")
            transaction.description = transaction.description[:1000]
        
        # Validate amount
        try:
            float(transaction.amount)
        except (ValueError, TypeError):
            raise DataValidationError(f"Invalid amount: {transaction.amount}", 'amount', transaction.amount)
        
        return transaction
    
    def validate_category_result(self, result: CategoryResult) -> CategoryResult:
        """
        Validate category result data.
        
        Args:
            result: CategoryResult to validate
            
        Returns:
            Validated result
            
        Raises:
            DataValidationError: If validation fails
        """
        if not result:
            raise DataValidationError("CategoryResult cannot be None")
        
        # Validate category name
        if not result.category or not isinstance(result.category, str):
            raise DataValidationError("Category name must be a non-empty string", 'category')
        
        # Validate confidence score
        if not isinstance(result.confidence, (int, float)) or not 0.0 <= result.confidence <= 1.0:
            raise DataValidationError(
                f"Confidence must be between 0.0 and 1.0, got {result.confidence}",
                'confidence', result.confidence
            )
        
        # Validate method
        valid_methods = ['pattern', 'ai', 'ml', 'manual', 'fallback', 'ai_cached']
        if result.method not in valid_methods:
            self.logger.warning(f"Unknown categorization method: {result.method}")
            result.method = 'unknown'
        
        return result
    
    def register_fallback_strategy(self, error_category: ErrorCategory, 
                                  strategy: Callable[[Exception, Dict[str, Any]], Any]) -> None:
        """
        Register a fallback strategy for a specific error category.
        
        Args:
            error_category: Category of errors this strategy handles
            strategy: Function that implements the fallback logic
        """
        self.fallback_strategies[error_category] = strategy
        self.logger.info(f"Registered fallback strategy for {error_category.value}")
    
    def register_recovery_callback(self, error_category: ErrorCategory,
                                  callback: Callable[[Exception, Dict[str, Any]], None]) -> None:
        """
        Register a recovery callback for a specific error category.
        
        Args:
            error_category: Category of errors this callback handles
            callback: Function to execute for recovery actions
        """
        self.recovery_callbacks[error_category] = callback
        self.logger.info(f"Registered recovery callback for {error_category.value}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics and health metrics.
        
        Returns:
            Dictionary with error statistics
        """
        total_errors = sum(self.error_counts.values())
        
        stats = {
            'total_errors': total_errors,
            'error_counts_by_category': {},
            'error_counts_by_severity': {},
            'fallback_strategies_registered': len(self.fallback_strategies),
            'recovery_callbacks_registered': len(self.recovery_callbacks)
        }
        
        # Group by category and severity
        for key, count in self.error_counts.items():
            if isinstance(key, tuple) and len(key) == 2:
                category, severity = key
                
                if category.value not in stats['error_counts_by_category']:
                    stats['error_counts_by_category'][category.value] = 0
                stats['error_counts_by_category'][category.value] += count
                
                if severity.value not in stats['error_counts_by_severity']:
                    stats['error_counts_by_severity'][severity.value] = 0
                stats['error_counts_by_severity'][severity.value] += count
        
        return stats
    
    def reset_error_statistics(self) -> None:
        """Reset error statistics."""
        self.error_counts.clear()
        self.logger.info("Error statistics reset")
    
    def _setup_default_fallbacks(self) -> None:
        """Setup default fallback strategies for common error categories."""
        
        # External service fallback - return None to trigger next categorization method
        def external_service_fallback(error: Exception, context: Dict[str, Any]) -> None:
            self.logger.info("External service failed, falling back to next categorization method")
            return None
        
        # Configuration fallback - use safe defaults
        def configuration_fallback(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
            self.logger.warning("Configuration error, using safe defaults")
            return {
                'confidence_threshold': 0.7,
                'default_category': 'Uncategorized',
                'enabled': False  # Disable problematic features
            }
        
        # Storage fallback - use in-memory storage
        def storage_fallback(error: Exception, context: Dict[str, Any]) -> bool:
            self.logger.warning("Storage error, operations may not persist")
            return False  # Indicate storage operation failed
        
        self.register_fallback_strategy(ErrorCategory.EXTERNAL_SERVICE, external_service_fallback)
        self.register_fallback_strategy(ErrorCategory.CONFIGURATION, configuration_fallback)
        self.register_fallback_strategy(ErrorCategory.STORAGE, storage_fallback)
    
    def _classify_error(self, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """
        Classify an error by category and severity.
        
        Args:
            error: Exception to classify
            
        Returns:
            Tuple of (ErrorCategory, ErrorSeverity)
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Network-related errors
        if any(keyword in error_message for keyword in ['connection', 'timeout', 'network', 'dns']):
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        
        # Authentication errors
        if any(keyword in error_message for keyword in ['unauthorized', 'authentication', 'api key', 'forbidden']):
            return ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH
        
        # Rate limiting
        if any(keyword in error_message for keyword in ['rate limit', 'too many requests', 'quota']):
            return ErrorCategory.RATE_LIMIT, ErrorSeverity.MEDIUM
        
        # File/storage errors
        if error_type in ['FileNotFoundError', 'PermissionError', 'OSError', 'IOError']:
            return ErrorCategory.STORAGE, ErrorSeverity.HIGH
        
        # Memory/resource errors
        if error_type in ['MemoryError', 'ResourceWarning']:
            return ErrorCategory.RESOURCE, ErrorSeverity.CRITICAL
        
        # Validation errors
        if error_type in ['ValueError', 'TypeError', 'KeyError']:
            return ErrorCategory.DATA_VALIDATION, ErrorSeverity.MEDIUM
        
        # Default classification
        return ErrorCategory.PROCESSING, ErrorSeverity.MEDIUM
    
    def _log_error(self, error: Exception, category: ErrorCategory, 
                   severity: ErrorSeverity, context: Dict[str, Any]) -> None:
        """
        Log an error with appropriate level and context.
        
        Args:
            error: The exception that occurred
            category: Error category
            severity: Error severity
            context: Additional context
        """
        log_message = f"[{category.value.upper()}] {str(error)}"
        
        # Add context information
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            log_message += f" | Context: {context_str}"
        
        # Log at appropriate level based on severity
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, exc_info=True)
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, exc_info=True)
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:  # LOW
            self.logger.info(log_message)
    
    def _update_error_stats(self, category: ErrorCategory, severity: ErrorSeverity) -> None:
        """Update error statistics."""
        key = (category, severity)
        self.error_counts[key] = self.error_counts.get(key, 0) + 1
    
    def _try_fallback(self, error: Exception, category: ErrorCategory, 
                     context: Dict[str, Any]) -> Optional[Any]:
        """
        Try to execute a fallback strategy for the error.
        
        Args:
            error: The exception that occurred
            category: Error category
            context: Additional context
            
        Returns:
            Result from fallback strategy if available
        """
        strategy = self.fallback_strategies.get(category)
        if strategy:
            try:
                return strategy(error, context)
            except Exception as fallback_error:
                self.logger.error(f"Fallback strategy failed for {category.value}: {fallback_error}")
        
        return None
    
    def _execute_recovery_callback(self, category: ErrorCategory, error: Exception,
                                  context: Dict[str, Any]) -> None:
        """
        Execute recovery callback if registered.
        
        Args:
            category: Error category
            error: The exception that occurred
            context: Additional context
        """
        callback = self.recovery_callbacks.get(category)
        if callback:
            try:
                callback(error, context)
            except Exception as callback_error:
                self.logger.error(f"Recovery callback failed for {category.value}: {callback_error}")


# Global error handler instance
_global_error_handler = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def with_error_handling(fallback_value: Any = None, reraise: bool = False):
    """
    Convenience decorator for error handling.
    
    Args:
        fallback_value: Value to return if error occurs
        reraise: Whether to reraise the exception after handling
    """
    return get_error_handler().with_error_handling(fallback_value, reraise)


def handle_categorization_error(error: Exception, context: Dict[str, Any] = None) -> Optional[Any]:
    """
    Convenience function for handling categorization errors.
    
    Args:
        error: The exception that occurred
        context: Additional context about the error
        
    Returns:
        Result from fallback strategy if available
    """
    return get_error_handler().handle_error(error, context)