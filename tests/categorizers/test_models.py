"""Tests for categorization data models."""

import pytest
from datetime import datetime
from hypothesis import given, strategies as st
import numpy as np

from kiro_budget.categorizers.models import (
    Transaction, CategoryResult, CategoryMatch, PatternRule, 
    CategoryDefinition, TransactionFeatures
)


class TestTransaction:
    """Test Transaction model."""
    
    def test_transaction_creation(self):
        """Test basic transaction creation."""
        transaction = Transaction(
            date=datetime(2024, 1, 1),
            amount=-50.0,
            description="COSTCO WHSE #1029",
            account="1234",
            institution="Chase",
            transaction_id="tx_123"
        )
        
        assert transaction.date == datetime(2024, 1, 1)
        assert transaction.amount == -50.0
        assert transaction.description == "COSTCO WHSE #1029"
        assert transaction.account == "1234"
        assert transaction.institution == "Chase"
        assert transaction.transaction_id == "tx_123"


class TestCategoryResult:
    """Test CategoryResult model."""
    
    def test_valid_confidence_score(self):
        """Test that valid confidence scores are accepted."""
        result = CategoryResult(
            category="Groceries",
            confidence=0.85,
            method="pattern"
        )
        assert result.confidence == 0.85
    
    def test_invalid_confidence_score_high(self):
        """Test that confidence scores > 1.0 are rejected."""
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            CategoryResult(
                category="Groceries",
                confidence=1.5,
                method="pattern"
            )
    
    def test_invalid_confidence_score_low(self):
        """Test that confidence scores < 0.0 are rejected."""
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            CategoryResult(
                category="Groceries",
                confidence=-0.1,
                method="pattern"
            )
    
    @given(confidence=st.floats(min_value=0.0, max_value=1.0))
    def test_valid_confidence_range_property(self, confidence):
        """Property test: All confidence scores in [0.0, 1.0] should be valid."""
        result = CategoryResult(
            category="Test",
            confidence=confidence,
            method="test"
        )
        assert 0.0 <= result.confidence <= 1.0


class TestCategoryMatch:
    """Test CategoryMatch model."""
    
    def test_valid_category_match(self):
        """Test valid category match creation."""
        match = CategoryMatch(
            category="Gas",
            pattern="COSTCO GAS",
            confidence=0.95,
            match_type="substring",
            specificity="very_high"
        )
        
        assert match.category == "Gas"
        assert match.pattern == "COSTCO GAS"
        assert match.confidence == 0.95
        assert match.match_type == "substring"
        assert match.specificity == "very_high"
    
    def test_invalid_specificity(self):
        """Test that invalid specificity values are rejected."""
        with pytest.raises(ValueError, match="Specificity must be one of"):
            CategoryMatch(
                category="Gas",
                pattern="GAS",
                confidence=0.8,
                match_type="substring",
                specificity="invalid"
            )


class TestPatternRule:
    """Test PatternRule model."""
    
    def test_valid_pattern_rule(self):
        """Test valid pattern rule creation."""
        rule = PatternRule(
            pattern="COSTCO.*",
            confidence=0.9,
            type="regex",
            specificity="high",
            case_sensitive=False
        )
        
        assert rule.pattern == "COSTCO.*"
        assert rule.confidence == 0.9
        assert rule.type == "regex"
        assert rule.specificity == "high"
        assert rule.case_sensitive is False
    
    def test_invalid_pattern_type(self):
        """Test that invalid pattern types are rejected."""
        with pytest.raises(ValueError, match="Pattern type must be one of"):
            PatternRule(
                pattern="test",
                confidence=0.8,
                type="invalid_type"
            )


class TestCategoryDefinition:
    """Test CategoryDefinition model."""
    
    def test_category_definition_with_patterns(self):
        """Test category definition with pattern rules."""
        patterns = [
            PatternRule(pattern="COSTCO", confidence=0.9, type="substring"),
            PatternRule(pattern="FRED.MEYER", confidence=0.85, type="substring")
        ]
        
        definition = CategoryDefinition(
            patterns=patterns,
            parent_category="Shopping",
            aliases=["Grocery", "Food"]
        )
        
        assert len(definition.patterns) == 2
        assert definition.parent_category == "Shopping"
        assert "Grocery" in definition.aliases
        assert "Food" in definition.aliases
    
    def test_category_definition_empty_aliases(self):
        """Test that None aliases are converted to empty list."""
        patterns = [PatternRule(pattern="TEST", confidence=0.8, type="substring")]
        definition = CategoryDefinition(patterns=patterns)
        
        assert definition.aliases == []


class TestTransactionFeatures:
    """Test TransactionFeatures model."""
    
    def test_transaction_features_creation(self):
        """Test transaction features creation with optional fields."""
        features = TransactionFeatures(
            amount=50.0,
            amount_bucket="medium",
            day_of_week=1,
            account_type="credit",
            institution="Chase"
        )
        
        assert features.amount == 50.0
        assert features.amount_bucket == "medium"
        assert features.day_of_week == 1
        assert features.account_type == "credit"
        assert features.institution == "Chase"
        assert features.description_vector is None