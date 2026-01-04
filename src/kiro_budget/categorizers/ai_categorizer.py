"""
AI-powered transaction categorization using external APIs.
"""

import os
import json
import time
import hashlib
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, timedelta

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .interfaces import Categorizer
from .models import Transaction, CategoryResult
from .error_handler import (
    ErrorHandler, ExternalServiceError, ErrorCategory, ErrorSeverity,
    with_error_handling
)


class AICategorizer(Categorizer):
    """
    AI-powered categorizer using OpenAI GPT and other AI services for
    intelligent transaction categorization when pattern matching fails.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize AI categorizer with configuration.
        
        Args:
            config: AI configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.error_handler = ErrorHandler(f"{__name__}.AICategorizer")
        self.config = config or {}
        
        # Configuration settings with safe defaults
        self.enabled = self.config.get("enabled", True)
        self.primary_service = self.config.get("primary_service", "openai")
        self.fallback_service = self.config.get("fallback_service", "claude")
        self.cache_responses = self.config.get("cache_responses", True)
        self.max_cost_per_month = self.config.get("max_cost_per_month", 50.0)
        
        # Rate limiting with safe defaults
        self.max_requests_per_minute = self.config.get("max_requests_per_minute", 60)
        self.request_timestamps = []
        
        # Retry configuration
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 1.0)
        
        # Cost tracking
        self.monthly_cost = 0.0
        self.cost_reset_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Response cache
        self.cache = {}
        self.cache_file = self.config.get("cache_file", "ai_categorization_cache.json")
        self._load_cache()
        
        # Initialize OpenAI client with error handling
        self.openai_client = None
        if OPENAI_AVAILABLE and self.enabled:
            self._initialize_openai_client()
        else:
            if not OPENAI_AVAILABLE:
                self.logger.warning("OpenAI library not available. Install with: pip install openai")
            self.enabled = False
    
    def _initialize_openai_client(self) -> None:
        """Initialize OpenAI client with error handling."""
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ExternalServiceError(
                    "openai", 
                    "API key not found. Set OPENAI_API_KEY environment variable."
                )
            
            self.openai_client = openai.OpenAI(api_key=api_key)
            
            # Test the client with a minimal request
            try:
                # This will validate the API key without using significant quota
                self.openai_client.models.list()
                self.logger.info("OpenAI client initialized and validated successfully")
            except Exception as e:
                raise ExternalServiceError("openai", f"API key validation failed: {e}")
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'ai_categorizer',
                'operation': 'initialize_openai'
            })
            self.openai_client = None
            self.enabled = False
            self.logger.warning("OpenAI client initialization failed, AI categorization disabled")
    
    @with_error_handling(fallback_value=None)
    def categorize(self, transaction: Transaction) -> Optional[CategoryResult]:
        """
        Categorize a transaction using AI services.
        
        Args:
            transaction: Transaction to categorize
            
        Returns:
            CategoryResult if successful, None otherwise
        """
        if not self.enabled:
            return None
        
        return self.categorize_with_ai(transaction.description, transaction.amount)
    
    def categorize_with_ai(self, description: str, amount: float, 
                          available_categories: List[str] = None) -> Optional[CategoryResult]:
        """
        Categorize a transaction description using AI with comprehensive error handling.
        
        Args:
            description: Transaction description
            amount: Transaction amount
            available_categories: List of available categories to choose from
            
        Returns:
            CategoryResult if successful, None otherwise
        """
        if not self.enabled or not description.strip():
            return None
        
        try:
            # Validate inputs
            if not isinstance(description, str) or len(description.strip()) == 0:
                raise ValueError("Description must be a non-empty string")
            
            if not isinstance(amount, (int, float)):
                raise ValueError("Amount must be a number")
            
            # Check cost limits
            if not self._check_cost_limits():
                self.logger.warning("Monthly cost limit reached. AI categorization disabled.")
                return None
            
            # Check rate limits
            if not self._check_rate_limits():
                self.logger.warning("Rate limit reached. Skipping AI categorization.")
                return None
            
            # Check cache first
            if self.cache_responses:
                cached_result = self.get_cached_result(description)
                if cached_result:
                    return cached_result
            
            # Try primary service with retries
            result = None
            if self.primary_service == "openai":
                result = self._categorize_with_openai_retry(description, amount, available_categories)
            
            # Try fallback service if primary fails
            if not result and self.fallback_service and self.fallback_service != self.primary_service:
                if self.fallback_service == "openai":
                    result = self._categorize_with_openai_retry(description, amount, available_categories)
                # Add other services here (Claude, etc.)
            
            # Cache successful results
            if result and self.cache_responses:
                self._cache_result_safe(description, result)
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'ai_categorizer',
                'operation': 'categorize_with_ai',
                'description': description[:100],
                'amount': amount
            })
            return None
    
    def _categorize_with_openai_retry(self, description: str, amount: float, 
                                     available_categories: List[str] = None) -> Optional[CategoryResult]:
        """
        Categorize using OpenAI with retry logic.
        
        Args:
            description: Transaction description
            amount: Transaction amount
            available_categories: Available categories
            
        Returns:
            CategoryResult if successful, None otherwise
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                result = self._categorize_with_openai(description, amount, available_categories)
                if result:
                    return result
            except Exception as e:
                last_error = e
                
                # Check if this is a retryable error
                if self._is_retryable_error(e):
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        self.logger.info(f"AI request failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                        time.sleep(delay)
                        continue
                else:
                    # Non-retryable error, don't retry
                    break
        
        # All retries failed
        if last_error:
            self.error_handler.handle_error(last_error, {
                'component': 'ai_categorizer',
                'operation': 'categorize_with_openai_retry',
                'attempts': self.max_retries,
                'description': description[:100]
            })
        
        return None
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.
        
        Args:
            error: The exception to check
            
        Returns:
            True if the error should be retried
        """
        error_message = str(error).lower()
        
        # Network/timeout errors are retryable
        if any(keyword in error_message for keyword in [
            'timeout', 'connection', 'network', 'temporary', 'service unavailable'
        ]):
            return True
        
        # Rate limiting is retryable (with backoff)
        if any(keyword in error_message for keyword in [
            'rate limit', 'too many requests', 'quota exceeded'
        ]):
            return True
        
        # Server errors (5xx) are retryable
        if any(keyword in error_message for keyword in [
            'internal server error', 'bad gateway', 'service unavailable'
        ]):
            return True
        
        # Authentication and client errors (4xx) are not retryable
        if any(keyword in error_message for keyword in [
            'unauthorized', 'forbidden', 'invalid api key', 'bad request'
        ]):
            return False
        
        # Default to not retryable for unknown errors
        return False
    
    def get_cached_result(self, description: str) -> Optional[CategoryResult]:
        """
        Get cached categorization result for a description.
        
        Args:
            description: Transaction description
            
        Returns:
            Cached CategoryResult if found, None otherwise
        """
        cache_key = self._get_cache_key(description)
        cached_data = self.cache.get(cache_key)
        
        if cached_data:
            return CategoryResult(
                category=cached_data["category"],
                confidence=cached_data["confidence"],
                method="ai_cached",
                reasoning=cached_data.get("reasoning", "Cached AI result")
            )
        
        return None
    
    def get_confidence_threshold(self) -> float:
        """Get the confidence threshold for AI categorization."""
        return self.config.get("confidence_threshold", 0.6)
    
    def _categorize_with_openai(self, description: str, amount: float, 
                               available_categories: List[str] = None) -> Optional[CategoryResult]:
        """
        Categorize using OpenAI GPT.
        
        Args:
            description: Transaction description
            amount: Transaction amount
            available_categories: Available categories
            
        Returns:
            CategoryResult if successful, None otherwise
        """
        if not self.openai_client:
            return None
        
        try:
            prompt = self.build_prompt(description, amount, available_categories)
            
            # Record request timestamp for rate limiting
            self.request_timestamps.append(time.time())
            
            response = self.openai_client.chat.completions.create(
                model=self.config.get("openai_model", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": "You are a financial transaction categorization expert."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1  # Low temperature for consistent results
            )
            
            # Track costs (approximate)
            self._track_cost(response)
            
            # Parse response
            result = self.parse_ai_response(response.choices[0].message.content)
            if result:
                result.method = "ai"
                return result
                
        except Exception as e:
            self.logger.error(f"OpenAI categorization failed: {e}")
        
        return None
    
    def build_prompt(self, description: str, amount: float, 
                    available_categories: List[str] = None) -> str:
        """
        Build a structured prompt for AI categorization.
        
        Args:
            description: Transaction description
            amount: Transaction amount
            available_categories: Available categories
            
        Returns:
            Formatted prompt string
        """
        # Default categories if none provided
        if not available_categories:
            available_categories = [
                "Groceries", "Gas", "Restaurants", "Shopping", "Utilities",
                "Transportation", "Healthcare", "Entertainment", "Income",
                "Transfer", "Uncategorized"
            ]
        
        prompt = f"""Categorize this financial transaction:

Description: "{description}"
Amount: ${abs(amount):.2f}

Available categories: {', '.join(available_categories)}

Instructions:
1. Choose the MOST appropriate category from the list above
2. Consider the merchant name, transaction type, and amount
3. If uncertain, choose "Uncategorized"
4. Respond with ONLY the category name and confidence (0.0-1.0)

Format your response as: CATEGORY_NAME|CONFIDENCE
Example: Groceries|0.95

Response:"""
        
        return prompt
    
    def parse_ai_response(self, response: str) -> Optional[CategoryResult]:
        """
        Parse AI response into CategoryResult.
        
        Args:
            response: Raw AI response text
            
        Returns:
            CategoryResult if parsing successful, None otherwise
        """
        try:
            response = response.strip()
            
            # Handle format: CATEGORY|CONFIDENCE
            if "|" in response:
                parts = response.split("|")
                if len(parts) >= 2:
                    category = parts[0].strip()
                    confidence_str = parts[1].strip()
                    
                    try:
                        confidence = float(confidence_str)
                        confidence = max(0.0, min(1.0, confidence))  # Clamp to valid range
                        
                        return CategoryResult(
                            category=category,
                            confidence=confidence,
                            method="ai",
                            reasoning=f"AI categorization with {confidence:.1%} confidence"
                        )
                    except ValueError:
                        pass
            
            # Fallback: treat entire response as category name
            if response and len(response) < 50:  # Reasonable category name length
                return CategoryResult(
                    category=response,
                    confidence=0.7,  # Default confidence
                    method="ai",
                    reasoning="AI categorization (default confidence)"
                )
        
        except Exception as e:
            self.logger.error(f"Failed to parse AI response '{response}': {e}")
        
        return None
    
    def _check_cost_limits(self) -> bool:
        """Check if monthly cost limits allow more requests."""
        # Reset monthly cost if new month
        now = datetime.now()
        if now >= self.cost_reset_date + timedelta(days=32):  # Approximate month
            self.monthly_cost = 0.0
            self.cost_reset_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return self.monthly_cost < self.max_cost_per_month
    
    def _check_rate_limits(self) -> bool:
        """Check if rate limits allow more requests."""
        now = time.time()
        
        # Remove timestamps older than 1 minute
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if now - ts < 60
        ]
        
        return len(self.request_timestamps) < self.max_requests_per_minute
    
    def _track_cost(self, response) -> None:
        """Track API costs for budget management."""
        try:
            # Approximate cost calculation for GPT-3.5-turbo
            # These are rough estimates - actual costs may vary
            input_tokens = getattr(response.usage, 'prompt_tokens', 0)
            output_tokens = getattr(response.usage, 'completion_tokens', 0)
            
            # GPT-3.5-turbo pricing (approximate)
            input_cost = input_tokens * 0.0015 / 1000  # $0.0015 per 1K tokens
            output_cost = output_tokens * 0.002 / 1000  # $0.002 per 1K tokens
            
            total_cost = input_cost + output_cost
            self.monthly_cost += total_cost
            
            self.logger.debug(f"AI request cost: ${total_cost:.4f}, monthly total: ${self.monthly_cost:.2f}")
            
        except Exception as e:
            self.logger.warning(f"Failed to track AI costs: {e}")
    
    def _get_cache_key(self, description: str) -> str:
        """Generate cache key for a transaction description."""
        # Normalize description for consistent caching
        normalized = description.upper().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _cache_result(self, description: str, result: CategoryResult) -> None:
        """Cache a categorization result with error handling."""
        try:
            cache_key = self._get_cache_key(description)
            self.cache[cache_key] = {
                "category": result.category,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "timestamp": datetime.now().isoformat()
            }
            
            # Save cache to file periodically
            if len(self.cache) % 10 == 0:  # Save every 10 new entries
                self._save_cache_safe()
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'ai_categorizer',
                'operation': 'cache_result',
                'description': description[:50]
            })
    
    def _load_cache(self) -> None:
        """Load cache from file with error handling."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                self.logger.info(f"Loaded {len(self.cache)} cached AI results")
            else:
                self.cache = {}
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'ai_categorizer',
                'operation': 'load_cache',
                'cache_file': self.cache_file
            })
            self.cache = {}
            self.logger.warning("Failed to load AI cache, starting with empty cache")
    
    def _save_cache(self) -> None:
        """Save cache to file with error handling."""
        try:
            # Create directory if it doesn't exist
            cache_dir = os.path.dirname(self.cache_file)
            if cache_dir and not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
            
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            self.error_handler.handle_error(e, {
                'component': 'ai_categorizer',
                'operation': 'save_cache',
                'cache_file': self.cache_file,
                'cache_size': len(self.cache)
            })
            self.logger.warning("Failed to save AI cache")
    
    def _save_cache_safe(self) -> None:
        """Alias for _save_cache for backward compatibility."""
        self._save_cache()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get AI categorization statistics."""
        return {
            "enabled": self.enabled,
            "monthly_cost": self.monthly_cost,
            "max_cost_per_month": self.max_cost_per_month,
            "cached_results": len(self.cache),
            "recent_requests": len(self.request_timestamps),
            "max_requests_per_minute": self.max_requests_per_minute,
            "openai_available": OPENAI_AVAILABLE and self.openai_client is not None
        }
    
    def clear_cache(self) -> None:
        """Clear the response cache."""
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        self.logger.info("AI categorization cache cleared")