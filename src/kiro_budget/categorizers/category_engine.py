"""
Core CategoryEngine orchestrator that coordinates all categorization methods.
"""

from typing import List, Optional, Dict, Any, Tuple
import logging
from datetime import datetime

from .interfaces import Categorizer
from .models import Transaction, CategoryResult
from .pattern_matcher import PatternMatcher
from .storage import CategoryStorage
from .ai_categorizer import AICategorizer
from .ml_categorizer import MLCategorizer
from .persistence_manager import PersistenceManager
from .error_handler import (
    ErrorHandler, CategorizationError, ExternalServiceError, 
    ConfigurationError, ErrorCategory, ErrorSeverity, with_error_handling
)
from .performance_optimizer import PerformanceOptimizer


class CategoryEngine:
    """
    Central orchestrator that coordinates all categorization methods and manages
    the decision logic for assigning categories to transactions.
    """
    
    def __init__(self, config_path: str = "categories.yaml", enable_persistence: bool = True):
        """
        Initialize the CategoryEngine with configuration.
        
        Args:
            config_path: Path to the YAML configuration file
            enable_persistence: Whether to enable persistent storage of assignments
        """
        self.logger = logging.getLogger(__name__)
        self.error_handler = ErrorHandler(f"{__name__}.CategoryEngine")
        
        # Initialize performance optimizer
        performance_config = {
            'cache_size': 10000,
            'batch_size': 1000,
            'max_workers': None,  # Auto-detect
            'max_memory_mb': 1024,
            'memory_check_interval': 100
        }
        self.performance_optimizer = PerformanceOptimizer(performance_config)
        
        # Initialize storage with error handling
        try:
            self.storage = CategoryStorage(config_path)
        except Exception as e:
            self.error_handler.handle_error(e, {'component': 'storage', 'config_path': config_path})
            # Use default storage as fallback
            self.storage = CategoryStorage("categories_fallback.yaml")
            self.logger.warning("Using fallback storage configuration")
        
        self.pattern_matcher = PatternMatcher()
        
        # Initialize persistence manager if enabled
        if enable_persistence:
            try:
                self.persistence_manager = PersistenceManager()
            except Exception as e:
                self.error_handler.handle_error(e, {'component': 'persistence_manager'})
                self.persistence_manager = None
                self.logger.warning("Persistence disabled due to initialization error")
        else:
            self.persistence_manager = None
        
        # Load configuration and initialize components with error handling
        self._load_configuration()
        
        # Statistics tracking
        self.stats = {
            "total_processed": 0,
            "pattern_matches": 0,
            "ai_matches": 0,
            "ml_matches": 0,
            "manual_matches": 0,
            "uncategorized": 0,
            "persistent_matches": 0,
            "errors": 0,
            "fallback_used": 0,
            "cache_hits": 0,
            "processing_start_time": None,
            "processing_end_time": None
        }
    
    def categorize_transaction(self, transaction: Transaction) -> CategoryResult:
        """
        Categorize a single transaction using the hierarchical approach.
        
        Args:
            transaction: The transaction to categorize
            
        Returns:
            CategoryResult with category assignment and confidence
        """
        self.stats["total_processed"] += 1
        
        try:
            # Validate transaction data
            validated_transaction = self.error_handler.validate_transaction(transaction)
            
            # Check persistent storage first if enabled
            if self.persistence_manager:
                try:
                    stored_result = self.persistence_manager.get_category_assignment(validated_transaction)
                    if stored_result:
                        self.stats["persistent_matches"] += 1
                        return self.error_handler.validate_category_result(stored_result)
                except Exception as e:
                    self.error_handler.handle_error(e, {
                        'component': 'persistence_manager',
                        'operation': 'get_assignment',
                        'transaction_id': getattr(validated_transaction, 'transaction_id', 'unknown')
                    })
            
            # Try pattern matching first (fastest and most reliable)
            result = self._try_pattern_matching_safe(validated_transaction)
            if result and result.confidence >= self.confidence_threshold:
                self.stats["pattern_matches"] += 1
                self._store_result_safe(validated_transaction, result)
                return result
            
            # Try AI categorization for unknown merchants
            if hasattr(self, 'ai_categorizer') and self.ai_categorizer:
                ai_result = self._try_ai_categorization_safe(validated_transaction)
                if ai_result and ai_result.confidence >= getattr(self.ai_categorizer, 'get_confidence_threshold', lambda: 0.6)():
                    self.stats["ai_matches"] += 1
                    self._store_result_safe(validated_transaction, ai_result)
                    return ai_result
            
            # Try ML categorization for learned patterns
            if hasattr(self, 'ml_categorizer') and self.ml_categorizer and getattr(self.ml_categorizer, 'is_trained', False):
                ml_result = self._try_ml_categorization_safe(validated_transaction)
                if ml_result and ml_result.confidence >= getattr(self.ml_categorizer, 'get_confidence_threshold', lambda: 0.6)():
                    self.stats["ml_matches"] += 1
                    self._store_result_safe(validated_transaction, ml_result)
                    return ml_result
            
            # Fallback to uncategorized
            self.stats["uncategorized"] += 1
            fallback_result = CategoryResult(
                category=self.default_category,
                confidence=0.0,
                method="fallback",
                reasoning="No matching patterns found"
            )
            
            self._store_result_safe(validated_transaction, fallback_result)
            return fallback_result
            
        except Exception as e:
            self.stats["errors"] += 1
            self.error_handler.handle_error(e, {
                'component': 'category_engine',
                'operation': 'categorize_transaction',
                'transaction_description': getattr(transaction, 'description', 'unknown')[:100]
            })
            
            # Return safe fallback result
            self.stats["fallback_used"] += 1
            return CategoryResult(
                category=getattr(self, 'default_category', 'Uncategorized'),
                confidence=0.0,
                method="error_fallback",
                reasoning=f"Error during categorization: {str(e)[:100]}"
            )
    
    def batch_categorize(self, transactions: List[Transaction], 
                        show_progress: bool = True, use_optimization: bool = True) -> List[CategoryResult]:
        """
        Categorize multiple transactions in batch with progress tracking and error handling.
        
        Args:
            transactions: List of transactions to categorize
            show_progress: Whether to show progress information
            use_optimization: Whether to use performance optimizations
            
        Returns:
            List of CategoryResult objects in the same order as input
        """
        if not transactions:
            return []
        
        self.stats["processing_start_time"] = datetime.now()
        
        if show_progress:
            self.logger.info(f"Starting batch categorization of {len(transactions)} transactions")
        
        # Use optimized processing for large datasets
        if use_optimization and len(transactions) > 100:
            results = self._batch_categorize_optimized(transactions, show_progress)
        else:
            results = self._batch_categorize_standard(transactions, show_progress)
        
        self.stats["processing_end_time"] = datetime.now()
        
        if show_progress:
            self._log_batch_summary(len(transactions), [])
        
        return results
    
    def _batch_categorize_optimized(self, transactions: List[Transaction], 
                                   show_progress: bool = True) -> List[CategoryResult]:
        """
        Optimized batch categorization for large datasets.
        
        Args:
            transactions: List of transactions to categorize
            show_progress: Whether to show progress information
            
        Returns:
            List of CategoryResult objects
        """
        failed_transactions = []
        
        def progress_callback(processed: int, total: int):
            if show_progress and processed % 1000 == 0:
                self.logger.info(f"Processed {processed}/{total} transactions")
        
        # Use performance optimizer
        results = self.performance_optimizer.optimize_categorization(
            transactions, 
            self.categorize_transaction,
            progress_callback if show_progress else None
        )
        
        # Update statistics from performance optimizer
        perf_stats = self.performance_optimizer.get_performance_stats()
        self.stats["cache_hits"] = perf_stats.get('cache_stats', {}).get('hits', 0)
        
        # Store batch results if persistence is enabled
        if self.persistence_manager and results:
            try:
                assignments = [(transactions[i], results[i]) for i in range(len(transactions))]
                batch_stats = self.persistence_manager.batch_store_assignments(
                    assignments, reason="Optimized batch categorization"
                )
                self.logger.info(f"Stored {batch_stats['stored']} new and updated {batch_stats['updated']} assignments")
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'component': 'persistence_manager',
                    'operation': 'batch_store_assignments',
                    'batch_size': len(assignments)
                })
                self.logger.warning("Failed to store batch results to persistence")
        
        return results
    
    def _batch_categorize_standard(self, transactions: List[Transaction], 
                                  show_progress: bool = True) -> List[CategoryResult]:
        """
        Standard batch categorization for smaller datasets.
        
        Args:
            transactions: List of transactions to categorize
            show_progress: Whether to show progress information
            
        Returns:
            List of CategoryResult objects
        """
        results = []
        failed_transactions = []
        
        for i, transaction in enumerate(transactions):
            try:
                result = self.categorize_transaction(transaction)
                results.append(result)
            except Exception as e:
                # Handle individual transaction failures
                self.error_handler.handle_error(e, {
                    'component': 'category_engine',
                    'operation': 'batch_categorize_standard',
                    'transaction_index': i,
                    'transaction_id': getattr(transaction, 'transaction_id', 'unknown')
                })
                
                # Create error fallback result
                error_result = CategoryResult(
                    category=getattr(self, 'default_category', 'Uncategorized'),
                    confidence=0.0,
                    method="batch_error_fallback",
                    reasoning=f"Batch processing error: {str(e)[:100]}"
                )
                results.append(error_result)
                failed_transactions.append((i, transaction, e))
                self.stats["errors"] += 1
                self.stats["fallback_used"] += 1
            
            # Log progress every 1000 transactions
            if show_progress and (i + 1) % 1000 == 0:
                self.logger.info(f"Processed {i + 1}/{len(transactions)} transactions")
        
        # Store batch results if persistence is enabled
        if self.persistence_manager and results:
            try:
                assignments = [(transactions[i], results[i]) for i in range(len(transactions))]
                batch_stats = self.persistence_manager.batch_store_assignments(
                    assignments, reason="Standard batch categorization"
                )
                self.logger.info(f"Stored {batch_stats['stored']} new and updated {batch_stats['updated']} assignments")
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'component': 'persistence_manager',
                    'operation': 'batch_store_assignments',
                    'batch_size': len(assignments)
                })
                self.logger.warning("Failed to store batch results to persistence")
        
        return results
    
    def get_confidence_threshold(self) -> float:
        """Get the current confidence threshold."""
        return self.confidence_threshold
    
    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set the confidence threshold for categorization.
        
        Args:
            threshold: New confidence threshold (0.0-1.0)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        
        self.confidence_threshold = threshold
        self.logger.info(f"Confidence threshold updated to {threshold}")
    
    def configure_performance(self, config: Dict[str, Any]) -> None:
        """
        Configure performance optimization settings.
        
        Args:
            config: Performance configuration dictionary
        """
        self.performance_optimizer.configure(config)
        self.logger.info(f"Performance configuration updated: {list(config.keys())}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        # Get base categorization stats
        base_stats = self.get_categorization_stats()
        
        # Get performance optimizer stats
        perf_stats = self.performance_optimizer.get_performance_stats()
        
        # Combine statistics
        combined_stats = {
            **base_stats,
            'performance_optimization': perf_stats,
            'cache_enabled': True,
            'concurrent_processing_enabled': True
        }
        
        return combined_stats
    
    def clear_performance_caches(self) -> None:
        """Clear all performance caches."""
        self.performance_optimizer.clear_caches()
        self.logger.info("Performance caches cleared")
    
    def optimize_for_large_dataset(self, expected_size: int) -> None:
        """
        Optimize configuration for processing a large dataset.
        
        Args:
            expected_size: Expected number of transactions to process
        """
        # Calculate optimal settings based on dataset size
        if expected_size > 100000:
            # Very large dataset
            config = {
                'cache_size': 50000,
                'batch_size': 5000,
                'max_memory_mb': 2048,
                'memory_check_interval': 50
            }
        elif expected_size > 10000:
            # Large dataset
            config = {
                'cache_size': 20000,
                'batch_size': 2000,
                'max_memory_mb': 1024,
                'memory_check_interval': 100
            }
        else:
            # Medium dataset
            config = {
                'cache_size': 10000,
                'batch_size': 1000,
                'max_memory_mb': 512,
                'memory_check_interval': 200
            }
        
        self.configure_performance(config)
        self.logger.info(f"Optimized configuration for dataset size: {expected_size}")
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get current memory usage information.
        
        Returns:
            Dictionary with memory statistics
        """
        return self.performance_optimizer.memory_monitor.check_memory()
    
    def get_categorization_stats(self) -> Dict[str, Any]:
        """
        Get statistics about categorization performance.
        
        Returns:
            Dictionary with categorization statistics
        """
        stats = self.stats.copy()
        
        # Calculate percentages
        total = stats["total_processed"]
        if total > 0:
            stats["pattern_match_rate"] = stats["pattern_matches"] / total
            stats["uncategorized_rate"] = stats["uncategorized"] / total
            stats["error_rate"] = stats.get("errors", 0) / total
            stats["fallback_rate"] = stats.get("fallback_used", 0) / total
            
            # Calculate processing time
            if stats["processing_start_time"] and stats["processing_end_time"]:
                duration = stats["processing_end_time"] - stats["processing_start_time"]
                stats["processing_duration_seconds"] = duration.total_seconds()
                stats["transactions_per_second"] = total / duration.total_seconds()
        
        # Add error handler statistics
        error_stats = self.error_handler.get_error_statistics()
        stats["error_handler_stats"] = error_stats
        
        return stats
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health information.
        
        Returns:
            Dictionary with system health metrics
        """
        health = {
            "overall_status": "healthy",
            "components": {},
            "error_summary": {},
            "recommendations": []
        }
        
        # Check component health
        components = {
            "storage": self.storage,
            "pattern_matcher": self.pattern_matcher,
            "ai_categorizer": getattr(self, 'ai_categorizer', None),
            "ml_categorizer": getattr(self, 'ml_categorizer', None),
            "persistence_manager": self.persistence_manager
        }
        
        for name, component in components.items():
            if component is None:
                health["components"][name] = {"status": "disabled", "message": "Component not initialized"}
            else:
                try:
                    # Try to call a basic method to test component health
                    if hasattr(component, 'get_stats'):
                        component.get_stats()
                    elif hasattr(component, 'get_categories'):
                        component.get_categories()
                    health["components"][name] = {"status": "healthy", "message": "Component operational"}
                except Exception as e:
                    health["components"][name] = {"status": "error", "message": str(e)[:100]}
                    health["overall_status"] = "degraded"
        
        # Get error statistics
        error_stats = self.error_handler.get_error_statistics()
        health["error_summary"] = error_stats
        
        # Determine overall health status
        total_errors = error_stats.get("total_errors", 0)
        if total_errors > 100:
            health["overall_status"] = "unhealthy"
            health["recommendations"].append("High error count detected - review error logs")
        elif total_errors > 10:
            health["overall_status"] = "degraded"
            health["recommendations"].append("Moderate error count - monitor system closely")
        
        # Check error rates
        stats = self.get_categorization_stats()
        error_rate = stats.get("error_rate", 0)
        if error_rate > 0.1:  # More than 10% errors
            health["overall_status"] = "unhealthy"
            health["recommendations"].append(f"High error rate ({error_rate:.1%}) - investigate categorization failures")
        elif error_rate > 0.05:  # More than 5% errors
            health["overall_status"] = "degraded"
            health["recommendations"].append(f"Elevated error rate ({error_rate:.1%}) - monitor categorization quality")
        
        # Check component availability
        if not self.ai_categorizer and not self.ml_categorizer:
            health["recommendations"].append("No AI or ML categorization available - consider enabling advanced features")
        
        if not self.persistence_manager:
            health["recommendations"].append("Persistence disabled - category assignments will not be saved")
        
        return health
    
    def reset_stats(self) -> None:
        """Reset categorization statistics."""
        self.stats = {
            "total_processed": 0,
            "pattern_matches": 0,
            "ai_matches": 0,
            "ml_matches": 0,
            "manual_matches": 0,
            "uncategorized": 0,
            "processing_start_time": None,
            "processing_end_time": None
        }
    
    def reload_configuration(self) -> None:
        """Reload configuration from storage."""
        self._load_configuration()
        self.logger.info("Configuration reloaded successfully")
    
    def get_available_categories(self) -> List[str]:
        """Get list of all available categories."""
        return self.pattern_matcher.get_categories()
    
    def add_pattern_rule(self, category: str, pattern: str, confidence: float, 
                        specificity: str = "medium") -> None:
        """
        Add a new pattern rule and update the pattern matcher.
        
        Args:
            category: Category name
            pattern: Pattern string
            confidence: Confidence score (0.0-1.0)
            specificity: Pattern specificity level
        """
        # Add to storage
        self.storage.add_pattern_rule(category, pattern, confidence, specificity)
        
        # Update pattern matcher
        self.pattern_matcher.add_pattern(category, pattern, confidence, specificity)
        
        self.logger.info(f"Added pattern rule: {pattern} -> {category} (confidence: {confidence})")
    
    def train_ml_model(self, training_data: List[Tuple[Transaction, str]]) -> Dict[str, Any]:
        """
        Train the ML model with labeled transaction data.
        
        Args:
            training_data: List of (transaction, category) tuples
            
        Returns:
            Training metrics and statistics
        """
        if not hasattr(self, 'ml_categorizer') or not self.ml_categorizer:
            return {"error": "ML categorizer not initialized"}
        
        return self.ml_categorizer.train_model(training_data)
    
    def get_ml_model_info(self) -> Dict[str, Any]:
        """
        Get information about the ML model.
        
        Returns:
            Dictionary with ML model information
        """
        if not hasattr(self, 'ml_categorizer') or not self.ml_categorizer:
            return {"error": "ML categorizer not initialized"}
        
        return self.ml_categorizer.get_model_info()
    
    def reassign_category(self, old_category: str, new_category: str) -> int:
        """
        Reassign all transactions from one category to another.
        
        Args:
            old_category: Current category name
            new_category: New category name
            
        Returns:
            Number of transactions reassigned
        """
        if not self.persistence_manager:
            self.logger.warning("Persistence not enabled - cannot reassign categories")
            return 0
        
        return self.persistence_manager.reassign_category_transactions(old_category, new_category)
    
    def update_csv_with_categories(self, csv_path: str, output_path: Optional[str] = None) -> bool:
        """
        Update a CSV file with stored category assignments.
        
        Args:
            csv_path: Path to the CSV file to update
            output_path: Optional output path (defaults to overwriting input)
            
        Returns:
            True if successful
        """
        if not self.persistence_manager:
            self.logger.warning("Persistence not enabled - cannot update CSV")
            return False
        
        return self.persistence_manager.update_csv_with_categories(csv_path, output_path)
    
    def get_category_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored category assignments.
        
        Returns:
            Dictionary with category statistics
        """
        if not self.persistence_manager:
            return {"error": "Persistence not enabled"}
        
        return self.persistence_manager.get_category_statistics()
    
    def validate_data_integrity(self) -> Dict[str, Any]:
        """
        Validate referential integrity of category data.
        
        Returns:
            Dictionary with validation results
        """
        if not self.persistence_manager:
            return {"error": "Persistence not enabled"}
        
        return self.persistence_manager.validate_referential_integrity()
    
    def repair_data_integrity(self) -> Dict[str, Any]:
        """
        Repair referential integrity issues in category data.
        
        Returns:
            Dictionary with repair results
        """
        if not self.persistence_manager:
            return {"error": "Persistence not enabled"}
        
        return self.persistence_manager.repair_referential_integrity()
    
    def _load_configuration(self) -> None:
        """Load configuration from storage and initialize components."""
        try:
            config = self.storage.load_categories()
            
            # Set configuration values with safe defaults
            self.confidence_threshold = config.get("confidence_threshold", 0.7)
            self.default_category = config.get("default_category", "Uncategorized")
            
            # Validate configuration values
            if not 0.0 <= self.confidence_threshold <= 1.0:
                self.logger.warning(f"Invalid confidence threshold {self.confidence_threshold}, using 0.7")
                self.confidence_threshold = 0.7
            
            if not self.default_category or not isinstance(self.default_category, str):
                self.logger.warning(f"Invalid default category {self.default_category}, using 'Uncategorized'")
                self.default_category = "Uncategorized"
            
            # Initialize AI categorizer if enabled
            ai_config = config.get("ai_config", {})
            if ai_config.get("enabled", True):
                try:
                    self.ai_categorizer = AICategorizer(ai_config)
                    self.logger.info("AI categorizer initialized successfully")
                except Exception as e:
                    self.error_handler.handle_error(e, {
                        'component': 'ai_categorizer',
                        'operation': 'initialization'
                    })
                    self.ai_categorizer = None
                    self.logger.warning("AI categorizer disabled due to initialization error")
            else:
                self.ai_categorizer = None
                self.logger.info("AI categorizer disabled in configuration")
            
            # Initialize ML categorizer if enabled
            ml_config = config.get("ml_config", {})
            if ml_config.get("enabled", True):
                try:
                    model_path = ml_config.get("model_path", "ml_model.pkl")
                    confidence_threshold = ml_config.get("confidence_threshold", 0.6)
                    retrain_threshold = ml_config.get("retrain_threshold", 100)
                    
                    self.ml_categorizer = MLCategorizer(
                        model_path=model_path,
                        confidence_threshold=confidence_threshold,
                        retrain_threshold=retrain_threshold
                    )
                    self.logger.info("ML categorizer initialized successfully")
                except Exception as e:
                    self.error_handler.handle_error(e, {
                        'component': 'ml_categorizer',
                        'operation': 'initialization'
                    })
                    self.ml_categorizer = None
                    self.logger.warning("ML categorizer disabled due to initialization error")
            else:
                self.ml_categorizer = None
                self.logger.info("ML categorizer disabled in configuration")
            
            # Load patterns into pattern matcher
            categories = config.get("categories", {})
            patterns_dict = {}
            
            for category, category_data in categories.items():
                if "patterns" in category_data:
                    patterns_dict[category] = category_data["patterns"]
            
            try:
                self.pattern_matcher.load_patterns_from_dict(patterns_dict)
                self.logger.info(f"Loaded configuration with {len(categories)} categories")
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'component': 'pattern_matcher',
                    'operation': 'load_patterns'
                })
                self.logger.warning("Pattern loading failed, using empty patterns")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'category_engine',
                'operation': 'load_configuration'
            })
            # Use safe default values
            self.confidence_threshold = 0.7
            self.default_category = "Uncategorized"
            self.ai_categorizer = None
            self.ml_categorizer = None
            self.logger.warning("Using default configuration due to loading error")
    
    def _try_pattern_matching_safe(self, transaction: Transaction) -> Optional[CategoryResult]:
        """
        Safely try to categorize using pattern matching.
        
        Args:
            transaction: Transaction to categorize
            
        Returns:
            CategoryResult if match found, None otherwise
        """
        try:
            match = self.pattern_matcher.match_patterns(transaction.description)
            if match:
                result = CategoryResult(
                    category=match.category,
                    confidence=match.confidence,
                    method="pattern",
                    reasoning=f"Matched pattern: {match.pattern} (type: {match.match_type})"
                )
                return self.error_handler.validate_category_result(result)
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'pattern_matcher',
                'operation': 'match_patterns',
                'transaction_id': getattr(transaction, 'transaction_id', 'unknown'),
                'description': transaction.description[:100]
            })
        
        return None
    
    def _try_ai_categorization_safe(self, transaction: Transaction) -> Optional[CategoryResult]:
        """
        Safely try to categorize using AI services.
        
        Args:
            transaction: Transaction to categorize
            
        Returns:
            CategoryResult if match found, None otherwise
        """
        try:
            available_categories = self.get_available_categories()
            result = self.ai_categorizer.categorize_with_ai(
                transaction.description, 
                transaction.amount,
                available_categories
            )
            if result:
                return self.error_handler.validate_category_result(result)
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'ai_categorizer',
                'operation': 'categorize_with_ai',
                'transaction_id': getattr(transaction, 'transaction_id', 'unknown'),
                'description': transaction.description[:100]
            })
        
        return None
    
    def _try_ml_categorization_safe(self, transaction: Transaction) -> Optional[CategoryResult]:
        """
        Safely try to categorize using ML model.
        
        Args:
            transaction: Transaction to categorize
            
        Returns:
            CategoryResult if match found, None otherwise
        """
        try:
            result = self.ml_categorizer.categorize(transaction)
            if result:
                return self.error_handler.validate_category_result(result)
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'ml_categorizer',
                'operation': 'categorize',
                'transaction_id': getattr(transaction, 'transaction_id', 'unknown'),
                'description': transaction.description[:100]
            })
        
        return None
    
    def _store_result_safe(self, transaction: Transaction, result: CategoryResult) -> None:
        """
        Safely store categorization result if persistence is enabled.
        
        Args:
            transaction: The transaction that was categorized
            result: The categorization result
        """
        if self.persistence_manager:
            try:
                self.persistence_manager.store_category_assignment(transaction, result)
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'component': 'persistence_manager',
                    'operation': 'store_assignment',
                    'transaction_id': getattr(transaction, 'transaction_id', 'unknown'),
                    'category': result.category
                })
    
    def _log_batch_summary(self, total_transactions: int, failed_transactions: List = None) -> None:
        """Log summary of batch processing results."""
        stats = self.get_categorization_stats()
        
        self.logger.info("Batch categorization completed:")
        self.logger.info(f"  Total transactions: {total_transactions}")
        self.logger.info(f"  Pattern matches: {stats['pattern_matches']} ({stats.get('pattern_match_rate', 0):.1%})")
        
        if stats.get('persistent_matches', 0) > 0:
            self.logger.info(f"  Persistent matches: {stats['persistent_matches']}")
        
        if stats['ai_matches'] > 0:
            self.logger.info(f"  AI matches: {stats['ai_matches']}")
        
        if stats['ml_matches'] > 0:
            self.logger.info(f"  ML matches: {stats['ml_matches']}")
        
        if stats.get('cache_hits', 0) > 0:
            cache_hit_rate = stats['cache_hits'] / total_transactions if total_transactions > 0 else 0
            self.logger.info(f"  Cache hits: {stats['cache_hits']} ({cache_hit_rate:.1%})")
        
        self.logger.info(f"  Uncategorized: {stats['uncategorized']} ({stats.get('uncategorized_rate', 0):.1%})")
        
        if stats.get('errors', 0) > 0:
            self.logger.warning(f"  Errors encountered: {stats['errors']}")
        
        if stats.get('fallback_used', 0) > 0:
            self.logger.warning(f"  Fallback results: {stats['fallback_used']}")
        
        if failed_transactions:
            self.logger.warning(f"  Failed transactions: {len(failed_transactions)}")
            # Log first few failures for debugging
            for i, (idx, transaction, error) in enumerate(failed_transactions[:3]):
                self.logger.warning(f"    {idx}: {getattr(transaction, 'description', 'unknown')[:50]} - {str(error)[:100]}")
            if len(failed_transactions) > 3:
                self.logger.warning(f"    ... and {len(failed_transactions) - 3} more failures")
        
        if "processing_duration_seconds" in stats:
            self.logger.info(f"  Processing time: {stats['processing_duration_seconds']:.2f} seconds")
            self.logger.info(f"  Processing rate: {stats.get('transactions_per_second', 0):.1f} transactions/second")
        
        # Log performance optimization statistics
        perf_stats = self.performance_optimizer.get_performance_stats()
        if 'cache_stats' in perf_stats:
            cache_stats = perf_stats['cache_stats']
            self.logger.info(f"  Performance cache: {cache_stats['size']} entries, {cache_stats['hit_rate']:.1%} hit rate")
        
        if 'memory_stats' in perf_stats:
            memory_stats = perf_stats['memory_stats']
            self.logger.info(f"  Memory usage: {memory_stats['memory_mb']:.1f}MB")
        
        # Log error handler statistics
        error_stats = self.error_handler.get_error_statistics()
        if error_stats['total_errors'] > 0:
            self.logger.info(f"  Error handler statistics: {error_stats['total_errors']} total errors")
            for category, count in error_stats['error_counts_by_category'].items():
                self.logger.info(f"    {category}: {count}")