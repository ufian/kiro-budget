"""
Performance optimization utilities for the transaction categorization system.
Provides caching, concurrent processing, and memory optimization features.
"""

import threading
import time
from typing import List, Dict, Any, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict
import logging
import gc
import psutil
import os
from datetime import datetime, timedelta

from .models import Transaction, CategoryResult
from .error_handler import ErrorHandler, ErrorCategory, ErrorSeverity


class LRUCache:
    """
    Thread-safe Least Recently Used cache for pattern matching results.
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                value = self.cache.pop(key)
                self.cache[key] = value
                self.hits += 1
                return value
            else:
                self.misses += 1
                return None
    
    def put(self, key: str, value: Any) -> None:
        """
        Put item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self.lock:
            if key in self.cache:
                # Update existing item
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                # Remove least recently used item
                self.cache.popitem(last=False)
            
            self.cache[key] = value
    
    def clear(self) -> None:
        """Clear the cache."""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0.0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate,
                'memory_usage_mb': self._estimate_memory_usage()
            }
    
    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage in MB."""
        # Rough estimation - actual usage may vary
        estimated_bytes = len(self.cache) * 200  # Assume ~200 bytes per entry
        return estimated_bytes / (1024 * 1024)


class BatchProcessor:
    """
    Optimized batch processor for large transaction datasets.
    """
    
    def __init__(self, batch_size: int = 1000, max_workers: int = None):
        """
        Initialize batch processor.
        
        Args:
            batch_size: Number of transactions to process in each batch
            max_workers: Maximum number of worker threads (None for auto-detect)
        """
        self.batch_size = batch_size
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.logger = logging.getLogger(__name__)
        self.error_handler = ErrorHandler(f"{__name__}.BatchProcessor")
    
    def process_batch(self, transactions: List[Transaction], 
                     categorize_func: Callable[[Transaction], CategoryResult],
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> List[CategoryResult]:
        """
        Process transactions in optimized batches.
        
        Args:
            transactions: List of transactions to process
            categorize_func: Function to categorize individual transactions
            progress_callback: Optional callback for progress updates (processed, total)
            
        Returns:
            List of CategoryResult objects
        """
        if not transactions:
            return []
        
        total_transactions = len(transactions)
        results = [None] * total_transactions  # Pre-allocate results list
        
        self.logger.info(f"Processing {total_transactions} transactions in batches of {self.batch_size}")
        
        # Process in batches to manage memory usage
        for batch_start in range(0, total_transactions, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total_transactions)
            batch_transactions = transactions[batch_start:batch_end]
            
            # Process batch with concurrent workers
            batch_results = self._process_batch_concurrent(
                batch_transactions, categorize_func, batch_start
            )
            
            # Store results
            for i, result in enumerate(batch_results):
                results[batch_start + i] = result
            
            # Call progress callback
            if progress_callback:
                progress_callback(batch_end, total_transactions)
            
            # Force garbage collection between batches for large datasets
            if batch_end % (self.batch_size * 10) == 0:
                gc.collect()
        
        return results
    
    def _process_batch_concurrent(self, batch_transactions: List[Transaction],
                                 categorize_func: Callable[[Transaction], CategoryResult],
                                 batch_offset: int = 0) -> List[CategoryResult]:
        """
        Process a batch of transactions concurrently.
        
        Args:
            batch_transactions: Transactions in this batch
            categorize_func: Categorization function
            batch_offset: Offset for logging purposes
            
        Returns:
            List of CategoryResult objects
        """
        results = [None] * len(batch_transactions)
        
        # Use ThreadPoolExecutor for I/O-bound operations (AI API calls)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self._safe_categorize, transaction, categorize_func): i
                for i, transaction in enumerate(batch_transactions)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                except Exception as e:
                    self.error_handler.handle_error(e, {
                        'component': 'batch_processor',
                        'operation': 'process_batch_concurrent',
                        'batch_offset': batch_offset,
                        'transaction_index': index
                    })
                    # Create fallback result
                    results[index] = CategoryResult(
                        category="Uncategorized",
                        confidence=0.0,
                        method="batch_error_fallback",
                        reasoning=f"Concurrent processing error: {str(e)[:100]}"
                    )
        
        return results
    
    def _safe_categorize(self, transaction: Transaction, 
                        categorize_func: Callable[[Transaction], CategoryResult]) -> CategoryResult:
        """
        Safely categorize a transaction with error handling.
        
        Args:
            transaction: Transaction to categorize
            categorize_func: Categorization function
            
        Returns:
            CategoryResult
        """
        try:
            return categorize_func(transaction)
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'batch_processor',
                'operation': 'safe_categorize',
                'transaction_id': getattr(transaction, 'transaction_id', 'unknown')
            })
            return CategoryResult(
                category="Uncategorized",
                confidence=0.0,
                method="safe_categorize_fallback",
                reasoning=f"Categorization error: {str(e)[:100]}"
            )


class MemoryMonitor:
    """
    Monitor and manage memory usage during categorization.
    """
    
    def __init__(self, max_memory_mb: int = 1024, check_interval: int = 100):
        """
        Initialize memory monitor.
        
        Args:
            max_memory_mb: Maximum memory usage in MB before triggering cleanup
            check_interval: Check memory every N transactions
        """
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        self.transaction_count = 0
        self.logger = logging.getLogger(__name__)
        self.cleanup_callbacks = []
    
    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback to be called when memory cleanup is needed.
        
        Args:
            callback: Function to call for cleanup
        """
        self.cleanup_callbacks.append(callback)
    
    def check_memory(self) -> Dict[str, Any]:
        """
        Check current memory usage.
        
        Returns:
            Dictionary with memory statistics
        """
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            return {
                'memory_mb': memory_mb,
                'max_memory_mb': self.max_memory_mb,
                'memory_percent': (memory_mb / self.max_memory_mb) * 100,
                'needs_cleanup': memory_mb > self.max_memory_mb
            }
        except Exception as e:
            self.logger.warning(f"Failed to check memory usage: {e}")
            return {
                'memory_mb': 0,
                'max_memory_mb': self.max_memory_mb,
                'memory_percent': 0,
                'needs_cleanup': False
            }
    
    def monitor_transaction(self) -> bool:
        """
        Monitor memory usage for a transaction.
        
        Returns:
            True if processing should continue, False if memory limit exceeded
        """
        self.transaction_count += 1
        
        # Check memory periodically
        if self.transaction_count % self.check_interval == 0:
            memory_stats = self.check_memory()
            
            if memory_stats['needs_cleanup']:
                self.logger.warning(f"Memory usage high: {memory_stats['memory_mb']:.1f}MB")
                self._trigger_cleanup()
                
                # Check again after cleanup
                memory_stats = self.check_memory()
                if memory_stats['needs_cleanup']:
                    self.logger.error(f"Memory usage still high after cleanup: {memory_stats['memory_mb']:.1f}MB")
                    return False
        
        return True
    
    def _trigger_cleanup(self) -> None:
        """Trigger memory cleanup callbacks."""
        self.logger.info("Triggering memory cleanup")
        
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger.warning(f"Cleanup callback failed: {e}")
        
        # Force garbage collection
        gc.collect()


class PerformanceOptimizer:
    """
    Main performance optimization coordinator for the categorization system.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize performance optimizer.
        
        Args:
            config: Performance configuration
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        cache_size = self.config.get('cache_size', 10000)
        self.pattern_cache = LRUCache(cache_size)
        
        batch_size = self.config.get('batch_size', 1000)
        max_workers = self.config.get('max_workers', None)
        self.batch_processor = BatchProcessor(batch_size, max_workers)
        
        max_memory_mb = self.config.get('max_memory_mb', 1024)
        memory_check_interval = self.config.get('memory_check_interval', 100)
        self.memory_monitor = MemoryMonitor(max_memory_mb, memory_check_interval)
        
        # Register cleanup callbacks
        self.memory_monitor.register_cleanup_callback(self.pattern_cache.clear)
        
        # Performance statistics
        self.stats = {
            'cache_enabled': True,
            'concurrent_processing_enabled': True,
            'memory_monitoring_enabled': True,
            'start_time': None,
            'end_time': None,
            'total_transactions': 0,
            'processing_time_seconds': 0.0
        }
    
    def optimize_categorization(self, transactions: List[Transaction],
                               categorize_func: Callable[[Transaction], CategoryResult],
                               progress_callback: Optional[Callable[[int, int], None]] = None) -> List[CategoryResult]:
        """
        Optimize categorization of a large transaction dataset.
        
        Args:
            transactions: List of transactions to categorize
            categorize_func: Base categorization function
            progress_callback: Optional progress callback
            
        Returns:
            List of CategoryResult objects
        """
        self.stats['start_time'] = datetime.now()
        self.stats['total_transactions'] = len(transactions)
        
        self.logger.info(f"Starting optimized categorization of {len(transactions)} transactions")
        
        # Create optimized categorization function
        optimized_func = self._create_optimized_categorizer(categorize_func)
        
        # Process with batch processor
        results = self.batch_processor.process_batch(
            transactions, optimized_func, progress_callback
        )
        
        self.stats['end_time'] = datetime.now()
        if self.stats['start_time'] and self.stats['end_time']:
            duration = self.stats['end_time'] - self.stats['start_time']
            self.stats['processing_time_seconds'] = duration.total_seconds()
        
        self._log_performance_summary()
        
        return results
    
    def _create_optimized_categorizer(self, base_categorize_func: Callable[[Transaction], CategoryResult]) -> Callable[[Transaction], CategoryResult]:
        """
        Create an optimized version of the categorization function.
        
        Args:
            base_categorize_func: Base categorization function
            
        Returns:
            Optimized categorization function
        """
        def optimized_categorize(transaction: Transaction) -> CategoryResult:
            # Check memory limits
            if not self.memory_monitor.monitor_transaction():
                self.logger.warning("Memory limit exceeded, using fallback categorization")
                return CategoryResult(
                    category="Uncategorized",
                    confidence=0.0,
                    method="memory_limit_fallback",
                    reasoning="Memory limit exceeded during processing"
                )
            
            # Check cache first
            cache_key = self._get_transaction_cache_key(transaction)
            cached_result = self.pattern_cache.get(cache_key)
            if cached_result:
                return cached_result
            
            # Call base categorization function
            result = base_categorize_func(transaction)
            
            # Cache the result
            if result and result.confidence > 0.5:  # Only cache confident results
                self.pattern_cache.put(cache_key, result)
            
            return result
        
        return optimized_categorize
    
    def _get_transaction_cache_key(self, transaction: Transaction) -> str:
        """
        Generate cache key for a transaction.
        
        Args:
            transaction: Transaction to generate key for
            
        Returns:
            Cache key string
        """
        # Use description and amount for cache key
        key_parts = [
            transaction.description.upper().strip(),
            str(round(abs(transaction.amount), 2))  # Round to avoid float precision issues
        ]
        return "|".join(key_parts)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        stats = self.stats.copy()
        
        # Add component statistics
        stats['cache_stats'] = self.pattern_cache.get_stats()
        stats['memory_stats'] = self.memory_monitor.check_memory()
        
        # Calculate performance metrics
        if stats['processing_time_seconds'] > 0 and stats['total_transactions'] > 0:
            stats['transactions_per_second'] = stats['total_transactions'] / stats['processing_time_seconds']
        else:
            stats['transactions_per_second'] = 0.0
        
        return stats
    
    def _log_performance_summary(self) -> None:
        """Log performance summary."""
        stats = self.get_performance_stats()
        
        self.logger.info("Performance optimization summary:")
        self.logger.info(f"  Total transactions: {stats['total_transactions']}")
        self.logger.info(f"  Processing time: {stats['processing_time_seconds']:.2f} seconds")
        self.logger.info(f"  Throughput: {stats['transactions_per_second']:.1f} transactions/second")
        
        cache_stats = stats['cache_stats']
        self.logger.info(f"  Cache hit rate: {cache_stats['hit_rate']:.1%}")
        self.logger.info(f"  Cache size: {cache_stats['size']}/{cache_stats['max_size']}")
        
        memory_stats = stats['memory_stats']
        self.logger.info(f"  Memory usage: {memory_stats['memory_mb']:.1f}MB")
    
    def clear_caches(self) -> None:
        """Clear all caches."""
        self.pattern_cache.clear()
        self.logger.info("Performance caches cleared")
    
    def configure(self, config: Dict[str, Any]) -> None:
        """
        Update performance configuration.
        
        Args:
            config: New configuration settings
        """
        self.config.update(config)
        
        # Update component configurations
        if 'cache_size' in config:
            # Create new cache with updated size
            old_cache = self.pattern_cache
            self.pattern_cache = LRUCache(config['cache_size'])
            # Copy some entries from old cache if it's smaller
            if config['cache_size'] > old_cache.max_size:
                with old_cache.lock:
                    for key, value in list(old_cache.cache.items())[-config['cache_size']:]:
                        self.pattern_cache.put(key, value)
        
        if 'batch_size' in config:
            self.batch_processor.batch_size = config['batch_size']
        
        if 'max_workers' in config:
            self.batch_processor.max_workers = config['max_workers']
        
        if 'max_memory_mb' in config:
            self.memory_monitor.max_memory_mb = config['max_memory_mb']
        
        self.logger.info(f"Performance configuration updated: {list(config.keys())}")