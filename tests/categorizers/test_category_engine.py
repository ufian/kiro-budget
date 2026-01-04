"""
Tests for CategoryEngine class with property-based testing.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, strategies as st, settings

from kiro_budget.categorizers.category_engine import CategoryEngine
from kiro_budget.categorizers.models import Transaction, CategoryResult


class TestCategoryEngine:
    """Test CategoryEngine functionality."""
    
    def setup_method(self):
        """Set up test environment with temporary configuration."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_categories.yaml"
        self.engine = CategoryEngine(str(self.config_path))
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test CategoryEngine initialization."""
        assert self.engine.confidence_threshold == 0.7
        assert self.engine.default_category == "Uncategorized"
        assert self.engine.pattern_matcher is not None
        assert self.engine.storage is not None
    
    def test_categorize_transaction_pattern_match(self):
        """Test successful pattern-based categorization."""
        # Add a pattern rule
        self.engine.add_pattern_rule("Groceries", "COSTCO", 0.95, "high")
        
        # Create test transaction
        transaction = Transaction(
            date=datetime.now(),
            amount=-127.45,
            description="COSTCO WHSE #1029",
            account="Checking",
            institution="Chase",
            transaction_id="test_001"
        )
        
        result = self.engine.categorize_transaction(transaction)
        
        assert result.category == "Groceries"
        assert result.confidence == 0.95
        assert result.method == "pattern"
        assert "COSTCO" in result.reasoning
    
    def test_categorize_transaction_no_match(self):
        """Test fallback to uncategorized when no patterns match."""
        transaction = Transaction(
            date=datetime.now(),
            amount=-50.00,
            description="UNKNOWN MERCHANT",
            account="Checking",
            institution="Chase",
            transaction_id="test_002"
        )
        
        result = self.engine.categorize_transaction(transaction)
        
        assert result.category == "Uncategorized"
        assert result.confidence == 0.0
        assert result.method == "fallback"
        assert "No matching patterns found" in result.reasoning
    
    def test_categorize_transaction_below_threshold(self):
        """Test fallback when confidence is below threshold."""
        # Add a low-confidence pattern
        self.engine.add_pattern_rule("Shopping", "STORE", 0.5, "low")
        self.engine.set_confidence_threshold(0.8)  # Higher than pattern confidence
        
        transaction = Transaction(
            date=datetime.now(),
            amount=-25.00,
            description="SOME STORE",
            account="Checking",
            institution="Chase",
            transaction_id="test_003"
        )
        
        result = self.engine.categorize_transaction(transaction)
        
        # Should fallback to uncategorized due to low confidence
        assert result.category == "Uncategorized"
        assert result.method == "fallback"
    
    def test_batch_categorize_empty_list(self):
        """Test batch categorization with empty list."""
        results = self.engine.batch_categorize([])
        assert results == []
    
    def test_batch_categorize_multiple_transactions(self):
        """Test batch categorization with multiple transactions."""
        # Add pattern rules
        self.engine.add_pattern_rule("Groceries", "COSTCO", 0.95, "high")
        self.engine.add_pattern_rule("Gas", "SHELL", 0.90, "high")
        
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.00,
                description="COSTCO WHSE #1029",
                account="Checking",
                institution="Chase",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-45.00,
                description="SHELL GAS STATION",
                account="Checking",
                institution="Chase",
                transaction_id="test_002"
            ),
            Transaction(
                date=datetime.now(),
                amount=-25.00,
                description="UNKNOWN MERCHANT",
                account="Checking",
                institution="Chase",
                transaction_id="test_003"
            )
        ]
        
        results = self.engine.batch_categorize(transactions, show_progress=False)
        
        assert len(results) == 3
        assert results[0].category == "Groceries"
        assert results[1].category == "Gas"
        assert results[2].category == "Uncategorized"
    
    def test_confidence_threshold_validation(self):
        """Test confidence threshold validation."""
        # Valid thresholds
        self.engine.set_confidence_threshold(0.0)
        assert self.engine.get_confidence_threshold() == 0.0
        
        self.engine.set_confidence_threshold(1.0)
        assert self.engine.get_confidence_threshold() == 1.0
        
        self.engine.set_confidence_threshold(0.5)
        assert self.engine.get_confidence_threshold() == 0.5
        
        # Invalid thresholds
        with pytest.raises(ValueError):
            self.engine.set_confidence_threshold(-0.1)
        
        with pytest.raises(ValueError):
            self.engine.set_confidence_threshold(1.1)
    
    def test_categorization_stats_tracking(self):
        """Test statistics tracking during categorization."""
        # Add pattern rule
        self.engine.add_pattern_rule("Groceries", "COSTCO", 0.95, "high")
        
        # Reset stats to start clean
        self.engine.reset_stats()
        
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.00,
                description="COSTCO WHSE #1029",
                account="Checking",
                institution="Chase",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-25.00,
                description="UNKNOWN MERCHANT",
                account="Checking",
                institution="Chase",
                transaction_id="test_002"
            )
        ]
        
        self.engine.batch_categorize(transactions, show_progress=False)
        
        stats = self.engine.get_categorization_stats()
        
        assert stats["total_processed"] == 2
        assert stats["pattern_matches"] == 1
        assert stats["uncategorized"] == 1
        assert stats["pattern_match_rate"] == 0.5
        assert stats["uncategorized_rate"] == 0.5
    
    def test_add_pattern_rule(self):
        """Test adding pattern rules."""
        initial_categories = len(self.engine.get_available_categories())
        
        self.engine.add_pattern_rule("TestCategory", "TEST_PATTERN", 0.85, "medium")
        
        # Should have added a new category
        categories = self.engine.get_available_categories()
        assert len(categories) == initial_categories + 1
        assert "TestCategory" in categories
        
        # Test categorization with new rule
        transaction = Transaction(
            date=datetime.now(),
            amount=-50.00,
            description="TEST_PATTERN MERCHANT",
            account="Checking",
            institution="Chase",
            transaction_id="test_001"
        )
        
        result = self.engine.categorize_transaction(transaction)
        assert result.category == "TestCategory"
        assert result.confidence == 0.85
    
    def test_reload_configuration(self):
        """Test configuration reloading."""
        # Add a pattern rule
        self.engine.add_pattern_rule("Groceries", "COSTCO", 0.95, "high")
        
        # Verify it works
        transaction = Transaction(
            date=datetime.now(),
            amount=-100.00,
            description="COSTCO WHSE #1029",
            account="Checking",
            institution="Chase",
            transaction_id="test_001"
        )
        
        result = self.engine.categorize_transaction(transaction)
        assert result.category == "Groceries"
        
        # Reload configuration (should still work)
        self.engine.reload_configuration()
        
        result = self.engine.categorize_transaction(transaction)
        assert result.category == "Groceries"
    
    def test_reset_stats(self):
        """Test statistics reset functionality."""
        # Process some transactions to generate stats
        self.engine.add_pattern_rule("Groceries", "COSTCO", 0.95, "high")
        
        transaction = Transaction(
            date=datetime.now(),
            amount=-100.00,
            description="COSTCO WHSE #1029",
            account="Checking",
            institution="Chase",
            transaction_id="test_001"
        )
        
        self.engine.categorize_transaction(transaction)
        
        # Verify stats are not zero
        stats = self.engine.get_categorization_stats()
        assert stats["total_processed"] > 0
        
        # Reset and verify stats are zero
        self.engine.reset_stats()
        stats = self.engine.get_categorization_stats()
        assert stats["total_processed"] == 0
        assert stats["pattern_matches"] == 0
        assert stats["uncategorized"] == 0


# Property-based tests
class TestCategoryEngineProperties:
    """Property-based tests for CategoryEngine."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_categories.yaml"
        self.engine = CategoryEngine(str(self.config_path))
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @given(
        description=st.text(min_size=1, max_size=100),
        amount=st.floats(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False)
    )
    @settings(deadline=None, max_examples=20)
    def test_property_single_category_assignment(self, description, amount):
        """
        Feature: transaction-categorization, Property 1: Single Category Assignment
        For any transaction processed by the CategoryEngine, exactly one primary category should be assigned.
        """
        transaction = Transaction(
            date=datetime.now(),
            amount=amount,
            description=description,
            account="TestAccount",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = self.engine.categorize_transaction(transaction)
        
        # Should always return exactly one category
        assert result.category is not None
        assert isinstance(result.category, str)
        assert len(result.category) > 0
    
    @given(
        confidence_threshold=st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(deadline=None, max_examples=10)
    def test_property_valid_confidence_scores(self, confidence_threshold):
        """
        Feature: transaction-categorization, Property 4: Valid Confidence Scores
        For any category assignment, the confidence score should be between 0.0 and 1.0 inclusive.
        """
        self.engine.set_confidence_threshold(confidence_threshold)
        
        transaction = Transaction(
            date=datetime.now(),
            amount=-50.00,
            description="TEST MERCHANT",
            account="TestAccount",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = self.engine.categorize_transaction(transaction)
        
        # Confidence should always be in valid range
        assert 0.0 <= result.confidence <= 1.0
    
    @given(
        transactions=st.lists(
            st.builds(
                Transaction,
                date=st.just(datetime.now()),
                amount=st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
                description=st.text(min_size=1, max_size=50),
                account=st.just("TestAccount"),
                institution=st.just("TestBank"),
                transaction_id=st.text(min_size=1, max_size=20)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(deadline=None, max_examples=10)
    def test_property_complete_batch_processing(self, transactions):
        """
        Feature: transaction-categorization, Property 20: Complete Batch Processing
        For any batch processing operation, all transactions in the input should be categorized.
        """
        results = self.engine.batch_categorize(transactions, show_progress=False)
        
        # Should return exactly one result per transaction
        assert len(results) == len(transactions)
        
        # All results should have valid categories
        for result in results:
            assert result.category is not None
            assert isinstance(result.category, str)
            assert len(result.category) > 0
            assert 0.0 <= result.confidence <= 1.0
    
    def test_property_uncategorized_fallback(self):
        """
        Feature: transaction-categorization, Property 3: Uncategorized Fallback
        For any transaction that matches no category rules, it should be assigned to "Uncategorized" category.
        """
        # Create transaction that won't match any patterns
        transaction = Transaction(
            date=datetime.now(),
            amount=-50.00,
            description="COMPLETELY_UNKNOWN_MERCHANT_12345",
            account="TestAccount",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = self.engine.categorize_transaction(transaction)
        
        # Should fallback to default category
        assert result.category == self.engine.default_category
        assert result.method == "fallback"
    
    @given(
        pattern=st.text(min_size=1, max_size=20),
        confidence=st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(deadline=None, max_examples=10)
    def test_property_highest_confidence_selection(self, pattern, confidence):
        """
        Feature: transaction-categorization, Property 2: Highest Confidence Selection
        For any transaction that matches multiple category rules, the rule with the highest confidence score should be selected.
        """
        # Add two patterns with different confidence scores
        low_confidence = min(confidence, 0.5)
        high_confidence = max(confidence, 0.8)
        
        self.engine.add_pattern_rule("LowConfidenceCategory", pattern, low_confidence, "medium")
        self.engine.add_pattern_rule("HighConfidenceCategory", pattern, high_confidence, "medium")
        
        transaction = Transaction(
            date=datetime.now(),
            amount=-50.00,
            description=f"{pattern} MERCHANT",
            account="TestAccount",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = self.engine.categorize_transaction(transaction)
        
        # Should select the higher confidence category
        if high_confidence > low_confidence:
            assert result.category == "HighConfidenceCategory"
            assert result.confidence == high_confidence
        # If they're equal, either is acceptable
        assert result.confidence >= low_confidence