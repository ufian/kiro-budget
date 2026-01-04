"""
Tests for AICategorizer class.
"""

import os
import tempfile
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from kiro_budget.categorizers.ai_categorizer import AICategorizer
from kiro_budget.categorizers.models import Transaction, CategoryResult


class TestAICategorizer:
    """Test AICategorizer functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.temp_dir, "test_cache.json")
        
        self.config = {
            "enabled": True,
            "primary_service": "openai",
            "cache_responses": True,
            "cache_file": self.cache_file,
            "max_cost_per_month": 10.0,
            "max_requests_per_minute": 5,
            "confidence_threshold": 0.6
        }
        
        self.categorizer = AICategorizer(self.config)
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization_disabled(self):
        """Test initialization when AI is disabled."""
        config = {"enabled": False}
        categorizer = AICategorizer(config)
        
        assert not categorizer.enabled
        assert categorizer.categorize_with_ai("TEST", 100.0) is None
    
    def test_initialization_no_api_key(self):
        """Test initialization without OpenAI API key."""
        with patch.dict(os.environ, {}, clear=True):
            # Mock OPENAI_AVAILABLE to be True but no API key
            with patch('kiro_budget.categorizers.ai_categorizer.OPENAI_AVAILABLE', True):
                categorizer = AICategorizer({"enabled": True})
                assert not categorizer.enabled
    
    def test_build_prompt(self):
        """Test prompt building functionality."""
        prompt = self.categorizer.build_prompt("COSTCO WHSE #1029", 127.45)
        
        assert "COSTCO WHSE #1029" in prompt
        assert "$127.45" in prompt
        assert "Groceries" in prompt
        assert "Gas" in prompt
        assert "CATEGORY_NAME|CONFIDENCE" in prompt
    
    def test_build_prompt_with_custom_categories(self):
        """Test prompt building with custom categories."""
        categories = ["Food", "Transport", "Other"]
        prompt = self.categorizer.build_prompt("TEST", 50.0, categories)
        
        assert "Food" in prompt
        assert "Transport" in prompt
        assert "Other" in prompt
        # Note: The prompt includes the custom categories, not the defaults
    
    def test_parse_ai_response_valid_format(self):
        """Test parsing valid AI response."""
        response = "Groceries|0.95"
        result = self.categorizer.parse_ai_response(response)
        
        assert result is not None
        assert result.category == "Groceries"
        assert result.confidence == 0.95
        assert result.method == "ai"
    
    def test_parse_ai_response_category_only(self):
        """Test parsing response with category name only."""
        response = "Restaurants"
        result = self.categorizer.parse_ai_response(response)
        
        assert result is not None
        assert result.category == "Restaurants"
        assert result.confidence == 0.7  # Default confidence
        assert result.method == "ai"
    
    def test_parse_ai_response_invalid_confidence(self):
        """Test parsing response with invalid confidence."""
        response = "Gas|invalid"
        result = self.categorizer.parse_ai_response(response)
        
        # Should fallback to category-only parsing
        assert result is not None
        assert result.category == "Gas|invalid"
        assert result.confidence == 0.7
    
    def test_parse_ai_response_confidence_clamping(self):
        """Test confidence score clamping to valid range."""
        # Test high confidence
        result = self.categorizer.parse_ai_response("Shopping|1.5")
        assert result.confidence == 1.0
        
        # Test negative confidence
        result = self.categorizer.parse_ai_response("Utilities|-0.2")
        assert result.confidence == 0.0
    
    def test_parse_ai_response_empty(self):
        """Test parsing empty or invalid response."""
        assert self.categorizer.parse_ai_response("") is None
        assert self.categorizer.parse_ai_response("   ") is None
        assert self.categorizer.parse_ai_response("A" * 100) is None  # Too long
    
    def test_cache_functionality(self):
        """Test response caching."""
        # Create a mock result
        result = CategoryResult(
            category="Groceries",
            confidence=0.9,
            method="ai",
            reasoning="Test result"
        )
        
        # Cache the result
        self.categorizer._cache_result("COSTCO WHSE", result)
        
        # Retrieve from cache
        cached = self.categorizer.get_cached_result("COSTCO WHSE")
        assert cached is not None
        assert cached.category == "Groceries"
        assert cached.confidence == 0.9
        assert cached.method == "ai_cached"
    
    def test_cache_key_normalization(self):
        """Test cache key normalization."""
        result = CategoryResult("Test", 0.8, "ai")
        
        # Cache with different cases and whitespace
        self.categorizer._cache_result("  COSTCO whse  ", result)
        
        # Should retrieve with normalized key
        cached = self.categorizer.get_cached_result("costco WHSE")
        assert cached is not None
        assert cached.category == "Test"
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        # Set low rate limit
        self.categorizer.max_requests_per_minute = 2
        
        # First request should pass
        assert self.categorizer._check_rate_limits()
        
        # Add timestamps to simulate requests
        import time
        now = time.time()
        self.categorizer.request_timestamps = [now, now - 10]  # 2 requests in last minute
        
        # Should hit rate limit
        assert not self.categorizer._check_rate_limits()
        
        # Old timestamps should be cleaned up
        self.categorizer.request_timestamps = [now - 70]  # Request older than 1 minute
        assert self.categorizer._check_rate_limits()
    
    def test_cost_tracking(self):
        """Test cost tracking functionality."""
        # Set low cost limit
        self.categorizer.max_cost_per_month = 1.0
        self.categorizer.monthly_cost = 0.5
        
        # Should allow requests under limit
        assert self.categorizer._check_cost_limits()
        
        # Exceed cost limit
        self.categorizer.monthly_cost = 1.5
        assert not self.categorizer._check_cost_limits()
    
    def test_get_confidence_threshold(self):
        """Test confidence threshold retrieval."""
        threshold = self.categorizer.get_confidence_threshold()
        assert threshold == 0.6  # From config
        
        # Test default value
        categorizer = AICategorizer({})
        assert categorizer.get_confidence_threshold() == 0.6
    
    def test_get_stats(self):
        """Test statistics retrieval."""
        stats = self.categorizer.get_stats()
        
        assert "enabled" in stats
        assert "monthly_cost" in stats
        assert "cached_results" in stats
        assert "openai_available" in stats
        assert isinstance(stats["enabled"], bool)
        assert isinstance(stats["monthly_cost"], float)
    
    def test_clear_cache(self):
        """Test cache clearing."""
        # Add some cache entries
        result = CategoryResult("Test", 0.8, "ai")
        self.categorizer._cache_result("TEST1", result)
        self.categorizer._cache_result("TEST2", result)
        
        assert len(self.categorizer.cache) == 2
        
        # Clear cache
        self.categorizer.clear_cache()
        
        assert len(self.categorizer.cache) == 0
    
    def test_categorize_with_openai_success(self):
        """Test successful OpenAI categorization."""
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Groceries|0.95"
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 10
        
        mock_client.chat.completions.create.return_value = mock_response
        self.categorizer.openai_client = mock_client
        
        # Test categorization
        result = self.categorizer._categorize_with_openai("COSTCO WHSE", 100.0)
        
        assert result is not None
        assert result.category == "Groceries"
        assert result.confidence == 0.95
        assert result.method == "ai"
        
        # Verify OpenAI was called
        mock_client.chat.completions.create.assert_called_once()
    
    def test_categorize_with_openai_failure(self):
        """Test OpenAI categorization failure."""
        # Mock OpenAI client to raise exception
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        self.categorizer.openai_client = mock_client
        
        # Test categorization
        result = self.categorizer._categorize_with_openai("TEST", 100.0)
        
        assert result is None
    
    def test_categorize_transaction_interface(self):
        """Test Transaction interface compatibility."""
        transaction = Transaction(
            date=datetime.now(),
            amount=-50.0,
            description="TEST MERCHANT",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        # Should return None when disabled or no API key
        self.categorizer.enabled = False
        result = self.categorizer.categorize(transaction)
        assert result is None
    
    def test_cache_file_operations(self):
        """Test cache file save/load operations."""
        # Add cache entries
        result = CategoryResult("Groceries", 0.9, "ai")
        self.categorizer._cache_result("COSTCO", result)
        
        # Save cache
        self.categorizer._save_cache()
        
        # Verify file exists
        assert os.path.exists(self.cache_file)
        
        # Create new categorizer and load cache
        new_categorizer = AICategorizer(self.config)
        
        # Should have loaded the cached result
        cached = new_categorizer.get_cached_result("COSTCO")
        assert cached is not None
        assert cached.category == "Groceries"


class TestAICategorizerIntegration:
    """Integration tests for AICategorizer with CategoryEngine."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_ai_fallback_integration(self):
        """Test AI categorization as fallback when patterns fail."""
        from kiro_budget.categorizers.category_engine import CategoryEngine
        
        # Create engine with AI disabled to test fallback behavior
        config_path = os.path.join(self.temp_dir, "test_config.yaml")
        
        # Create config with AI disabled
        config_content = """
version: "1.0"
default_category: "Uncategorized"
confidence_threshold: 0.7
categories: {}
ai_config:
  enabled: false
"""
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        engine = CategoryEngine(config_path)
        
        # Test transaction that won't match any patterns
        transaction = Transaction(
            date=datetime.now(),
            amount=-50.0,
            description="UNKNOWN MERCHANT XYZ",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = engine.categorize_transaction(transaction)
        
        # Should fallback to uncategorized since AI is disabled
        assert result.category == "Uncategorized"
        assert result.method == "fallback"