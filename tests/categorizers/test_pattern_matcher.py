"""Tests for PatternMatcher class."""

import pytest
from hypothesis import given, strategies as st

from kiro_budget.categorizers.pattern_matcher import PatternMatcher
from kiro_budget.categorizers.models import CategoryMatch, PatternRule


class TestPatternMatcher:
    """Test PatternMatcher functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = PatternMatcher()
    
    def test_empty_matcher_returns_none(self):
        """Test that empty matcher returns None for any description."""
        result = self.matcher.match_patterns("COSTCO WHSE #1029")
        assert result is None
    
    def test_add_pattern_and_match(self):
        """Test adding a pattern and matching against it."""
        self.matcher.add_pattern("Groceries", "COSTCO", 0.9)
        
        result = self.matcher.match_patterns("COSTCO WHSE #1029")
        
        assert result is not None
        assert result.category == "Groceries"
        assert result.pattern == "COSTCO"
        assert result.confidence == 0.9
        assert result.match_type == "substring"
    
    def test_case_insensitive_matching(self):
        """Test that pattern matching is case insensitive."""
        self.matcher.add_pattern("Groceries", "costco", 0.9)
        
        # Test various case combinations
        test_cases = [
            "COSTCO WHSE #1029",
            "costco whse #1029", 
            "Costco Whse #1029",
            "CoStCo WhSe #1029"
        ]
        
        for description in test_cases:
            result = self.matcher.match_patterns(description)
            assert result is not None
            assert result.category == "Groceries"
    
    def test_multiple_patterns_per_category(self):
        """Test that multiple patterns can be added to the same category."""
        self.matcher.add_pattern("Groceries", "COSTCO", 0.9)
        self.matcher.add_pattern("Groceries", "FRED MEYER", 0.85)
        
        # Test first pattern
        result1 = self.matcher.match_patterns("COSTCO WHSE #1029")
        assert result1.category == "Groceries"
        assert result1.confidence == 0.9
        
        # Test second pattern
        result2 = self.matcher.match_patterns("FRED MEYER #0658")
        assert result2.category == "Groceries"
        assert result2.confidence == 0.85
    
    def test_pattern_specificity_priority(self):
        """Test that more specific patterns are prioritized."""
        # Add general pattern
        self.matcher.add_pattern("Groceries", "COSTCO", 0.85, "medium")
        # Add specific pattern with higher specificity
        self.matcher.add_pattern("Gas", "COSTCO GAS", 0.90, "very_high")
        
        result = self.matcher.match_patterns("COSTCO GAS #1029")
        
        # Should match the more specific "Gas" category
        assert result.category == "Gas"
        assert result.pattern == "COSTCO GAS"
        assert result.specificity == "very_high"
    
    def test_confidence_score_priority(self):
        """Test that higher confidence scores are prioritized when specificity is equal."""
        self.matcher.add_pattern("Category1", "TEST", 0.7, "medium")
        self.matcher.add_pattern("Category2", "TEST", 0.9, "medium")
        
        result = self.matcher.match_patterns("TEST TRANSACTION")
        
        # Should match the higher confidence pattern
        assert result.category == "Category2"
        assert result.confidence == 0.9
    
    def test_regex_pattern_matching(self):
        """Test regex pattern matching."""
        self.matcher.add_pattern("Gas", ".*GAS.*", 0.8)
        
        test_cases = [
            "COSTCO GAS #1029",
            "SHELL GAS STATION",
            "ARCO GAS",
            "GASOLINE ALLEY"
        ]
        
        for description in test_cases:
            result = self.matcher.match_patterns(description)
            assert result is not None
            assert result.category == "Gas"
            assert result.match_type == "regex"
    
    def test_exact_pattern_matching(self):
        """Test exact pattern matching."""
        # Manually create exact pattern
        exact_rule = PatternRule(
            pattern="COSTCO WHSE #1029",
            confidence=0.95,
            type="exact",
            specificity="very_high"
        )
        self.matcher._patterns["Groceries"] = [exact_rule]
        
        # Should match exactly
        result = self.matcher.match_patterns("COSTCO WHSE #1029")
        assert result is not None
        assert result.category == "Groceries"
        
        # Should not match partial
        result = self.matcher.match_patterns("COSTCO WHSE #1030")
        assert result is None
    
    def test_get_all_matching_patterns(self):
        """Test getting all patterns that match a description."""
        self.matcher.add_pattern("Groceries", "COSTCO", 0.85)
        self.matcher.add_pattern("Gas", "COSTCO GAS", 0.90)
        self.matcher.add_pattern("Shopping", "COSTCO", 0.80)
        
        matches = self.matcher.get_matching_patterns("COSTCO GAS #1029")
        
        # Should get 3 matches (all patterns match)
        assert len(matches) == 3
        categories = [match.category for match in matches]
        assert "Groceries" in categories
        assert "Gas" in categories
        assert "Shopping" in categories
    
    def test_empty_description_returns_none(self):
        """Test that empty description returns None."""
        self.matcher.add_pattern("Test", "PATTERN", 0.8)
        
        assert self.matcher.match_patterns("") is None
        assert self.matcher.match_patterns(None) is None
    
    def test_invalid_regex_fallback(self):
        """Test that invalid regex patterns fall back to substring matching."""
        # Add pattern with invalid regex
        invalid_rule = PatternRule(
            pattern="[invalid regex",
            confidence=0.8,
            type="regex"
        )
        self.matcher._patterns["Test"] = [invalid_rule]
        
        # Should still match using substring fallback
        result = self.matcher.match_patterns("[invalid regex test")
        assert result is not None
        assert result.category == "Test"
    
    def test_load_patterns_from_dict(self):
        """Test loading patterns from dictionary structure."""
        patterns_dict = {
            "Groceries": [
                {"pattern": "COSTCO", "confidence": 0.9, "specificity": "high"},
                {"pattern": "FRED MEYER", "confidence": 0.85, "specificity": "medium"}
            ],
            "Gas": [
                {"pattern": ".*GAS.*", "confidence": 0.8, "specificity": "medium"}
            ]
        }
        
        self.matcher.load_patterns_from_dict(patterns_dict)
        
        # Test that patterns were loaded correctly
        assert "Groceries" in self.matcher.get_categories()
        assert "Gas" in self.matcher.get_categories()
        
        groceries_patterns = self.matcher.get_patterns_for_category("Groceries")
        assert len(groceries_patterns) == 2
        
        # Test matching works
        result = self.matcher.match_patterns("COSTCO WHSE")
        assert result.category == "Groceries"
    
    def test_hyphen_normalization(self):
        """Test that hyphens are treated as spaces in pattern matching."""
        # Add pattern with space
        self.matcher.add_pattern("Groceries", "FRED MEYER", 0.9)
        
        # Test descriptions with hyphens should match
        hyphen_cases = [
            "FRED-MEYER #0658",
            "FRED-MEYER STORE",
            "fred-meyer issaquah",
            "FRED-MEYER-STORE"
        ]
        
        for description in hyphen_cases:
            result = self.matcher.match_patterns(description)
            assert result is not None, f"Should match for: {description}"
            assert result.category == "Groceries"
            assert result.pattern == "FRED MEYER"
        
        # Test the reverse: pattern with hyphen should match description with space
        self.matcher.add_pattern("Gas", "SHELL-GAS", 0.85)
        
        space_cases = [
            "SHELL GAS STATION",
            "shell gas #123",
            "SHELL GAS BELLEVUE"
        ]
        
        for description in space_cases:
            result = self.matcher.match_patterns(description)
            # Should match either the SHELL-GAS pattern or no pattern (depending on other patterns)
            # Let's check if we get any match at all
            matches = self.matcher.get_matching_patterns(description)
            shell_gas_matches = [m for m in matches if m.pattern == "SHELL-GAS"]
            assert len(shell_gas_matches) > 0, f"Should match SHELL-GAS pattern for: {description}"
    
    def test_mixed_hyphen_space_normalization(self):
        """Test complex cases with mixed hyphens and spaces."""
        # Pattern with mixed separators
        self.matcher.add_pattern("Shopping", "HOME DEPOT", 0.9)
        
        test_cases = [
            "HOME-DEPOT #4704",
            "HOME DEPOT ISSAQUAH", 
            "home-depot store",
            "THE HOME-DEPOT 4704"
        ]
        
        for description in test_cases:
            result = self.matcher.match_patterns(description)
            assert result is not None, f"Should match for: {description}"
            assert result.category == "Shopping"
        """Test the specific case of COSTCO GAS vs COSTCO pattern priority."""
        # Add general COSTCO pattern for Groceries
        self.matcher.add_pattern("Groceries", "COSTCO", 0.85, "medium")
        # Add specific COSTCO GAS pattern for Gas
        self.matcher.add_pattern("Gas", "COSTCO GAS", 0.90, "very_high")
        
        # Test various COSTCO GAS variations
        test_cases = [
            "COSTCO GAS #1029",
            "COSTCO GAS STATION",
            "COSTCO GAS BELLEVUE",
            "costco gas #123"
        ]
        
        for description in test_cases:
            result = self.matcher.match_patterns(description)
            assert result is not None, f"Should match something for: {description}"
            assert result.category == "Gas", f"Should match Gas category for: {description}, got: {result.category}"
            assert result.pattern == "COSTCO GAS", f"Should match COSTCO GAS pattern for: {description}"
        
        # Test that regular COSTCO still matches Groceries
        regular_costco_cases = [
            "COSTCO WHSE #1029",
            "COSTCO WHOLESALE",
            "COSTCO ISSAQUAH"
        ]
        
        for description in regular_costco_cases:
            result = self.matcher.match_patterns(description)
            assert result is not None, f"Should match something for: {description}"
            assert result.category == "Groceries", f"Should match Groceries for: {description}, got: {result.category}"
    
    def test_calculate_specificity_score(self):
        """Test specificity score calculation."""
        # Exact match should have highest score
        score1 = self.matcher.calculate_specificity_score("COSTCO", "COSTCO")
        assert score1 == 1.0
        
        # Partial match should have lower score
        score2 = self.matcher.calculate_specificity_score("COSTCO", "COSTCO WHSE #1029")
        assert 0.0 < score2 < 1.0
        
        # Longer patterns should have higher base scores
        score3 = self.matcher.calculate_specificity_score("COSTCO GAS", "COSTCO GAS STATION")
        score4 = self.matcher.calculate_specificity_score("GAS", "COSTCO GAS STATION")
        assert score3 > score4


class TestPatternMatcherProperties:
    """Property-based tests for PatternMatcher."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.matcher = PatternMatcher()
    
    @given(st.text(min_size=1, max_size=50))
    def test_case_insensitive_property(self, description):
        """
        Property test: Case variations should match the same pattern.
        **Feature: transaction-categorization, Property 6: Case-Insensitive Matching**
        **Validates: Requirements 2.1**
        """
        # Skip descriptions that might cause issues
        if not description.strip():
            return
            
        self.matcher.add_pattern("Test", "TEST", 0.8)
        
        # Test various case transformations
        upper_result = self.matcher.match_patterns(description.upper())
        lower_result = self.matcher.match_patterns(description.lower())
        
        # Both should have same match status (both None or both not None)
        assert (upper_result is None) == (lower_result is None)
        
        # If both match, they should match the same category
        if upper_result is not None and lower_result is not None:
            assert upper_result.category == lower_result.category
    
    def test_confidence_score_preservation_simple(self):
        """Simple test: Added patterns should preserve their confidence scores."""
        test_cases = [
            ("COSTCO", 0.0),
            ("FRED MEYER", 0.5),
            ("GAS", 1.0),
            ("TEST123", 0.75)
        ]
        
        for pattern, confidence in test_cases:
            matcher = PatternMatcher()  # Fresh matcher for each test
            matcher.add_pattern("Test", pattern, confidence)
            
            result = matcher.match_patterns(f"{pattern} EXTRA TEXT")
            assert result is not None
            assert result.confidence == confidence
    
    @given(st.text(min_size=3, max_size=20).filter(lambda x: x.strip() and not any(c in x for c in ".*+?^${}[]|()")))
    def test_specific_pattern_priority_property(self, base_pattern):
        """
        Property test: More specific patterns should be prioritized over general ones.
        **Feature: transaction-categorization, Property 9: Specific Pattern Priority**
        **Validates: Requirements 2.4**
        """
        matcher = PatternMatcher()
        
        # Add general pattern
        matcher.add_pattern("General", base_pattern, 0.7, "medium")
        
        # Add more specific pattern (longer)
        specific_pattern = f"{base_pattern} SPECIFIC"
        matcher.add_pattern("Specific", specific_pattern, 0.8, "very_high")
        
        # Test with description that matches both patterns
        test_description = f"{specific_pattern} EXTRA"
        result = matcher.match_patterns(test_description)
        
        # Should match the more specific pattern
        assert result is not None
        assert result.category == "Specific"
        assert result.pattern == specific_pattern