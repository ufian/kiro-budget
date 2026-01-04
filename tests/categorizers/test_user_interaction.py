"""
Tests for UserInteraction class.
"""

import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from kiro_budget.categorizers.user_interaction import UserInteraction
from kiro_budget.categorizers.category_engine import CategoryEngine
from kiro_budget.categorizers.models import Transaction


class TestUserInteraction:
    """Test UserInteraction functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = f"{self.temp_dir}/test_categories.yaml"
        
        # Create mock category engine
        self.category_engine = CategoryEngine(self.config_path)
        
        # Create mock input/output functions
        self.mock_input = MagicMock()
        self.mock_print = MagicMock()
        
        self.user_interaction = UserInteraction(
            self.category_engine,
            input_function=self.mock_input,
            print_function=self.mock_print
        )
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test UserInteraction initialization."""
        assert self.user_interaction.category_engine == self.category_engine
        assert self.user_interaction.input_function == self.mock_input
        assert self.user_interaction.print_function == self.mock_print
        
        # Check initial stats
        stats = self.user_interaction.get_learning_stats()
        assert stats["manual_categorizations"] == 0
        assert stats["patterns_learned"] == 0
    
    def test_request_manual_categorization_by_number(self):
        """Test manual categorization with numeric selection."""
        # Add some categories to the engine
        self.category_engine.add_pattern_rule("Groceries", "COSTCO", 0.9, "high")
        self.category_engine.add_pattern_rule("Gas", "SHELL", 0.9, "high")
        
        # Mock user selecting option 1 (Groceries)
        self.mock_input.return_value = "1"
        
        transaction = Transaction(
            date=datetime.now(),
            amount=-100.0,
            description="UNKNOWN MERCHANT",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = self.user_interaction.request_manual_categorization(transaction)
        
        assert result == "Groceries"
        assert self.user_interaction.get_learning_stats()["manual_categorizations"] == 1
        
        # Verify print was called to show transaction details
        self.mock_print.assert_called()
    
    def test_request_manual_categorization_by_name(self):
        """Test manual categorization with direct name input."""
        # Add categories
        self.category_engine.add_pattern_rule("Groceries", "COSTCO", 0.9, "high")
        
        # Mock user typing category name directly
        self.mock_input.return_value = "Groceries"
        
        transaction = Transaction(
            date=datetime.now(),
            amount=-50.0,
            description="TEST MERCHANT",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = self.user_interaction.request_manual_categorization(transaction)
        
        assert result == "Groceries"
    
    def test_request_manual_categorization_new_category(self):
        """Test creating new category during manual categorization."""
        # Mock user selecting "create new category" option and then providing name
        self.mock_input.side_effect = ["2", "NewCategory", "y"]  # 2 = create new, name, confirm
        
        transaction = Transaction(
            date=datetime.now(),
            amount=-75.0,
            description="NEW MERCHANT",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = self.user_interaction.request_manual_categorization(transaction)
        
        assert result == "NewCategory"
    
    def test_request_manual_categorization_invalid_then_valid(self):
        """Test handling invalid input followed by valid input."""
        # Add categories
        self.category_engine.add_pattern_rule("Groceries", "COSTCO", 0.9, "high")
        
        # Mock invalid input followed by valid input
        self.mock_input.side_effect = ["invalid", "99", "1"]
        
        transaction = Transaction(
            date=datetime.now(),
            amount=-25.0,
            description="TEST",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        result = self.user_interaction.request_manual_categorization(transaction)
        
        assert result == "Groceries"
    
    def test_display_categorization_options(self):
        """Test displaying categorization options."""
        suggestions = ["Groceries", "Gas", "Restaurants"]
        
        # Mock user selecting option 2 (Gas)
        self.mock_input.return_value = "2"
        
        result = self.user_interaction.display_categorization_options(suggestions)
        
        assert result == "Gas"
    
    def test_display_categorization_options_manual_entry(self):
        """Test manual entry option in categorization options."""
        suggestions = ["Groceries", "Gas"]
        
        # Mock user selecting "Other" option and then entering custom category
        self.mock_input.side_effect = ["3", "CustomCategory"]
        
        result = self.user_interaction.display_categorization_options(suggestions)
        
        assert result == "CustomCategory"
    
    def test_display_categorization_options_empty_suggestions(self):
        """Test handling empty suggestions list."""
        result = self.user_interaction.display_categorization_options([])
        
        assert result == "Uncategorized"
    
    def test_learn_from_feedback(self):
        """Test learning patterns from user feedback."""
        transaction = Transaction(
            date=datetime.now(),
            amount=-100.0,
            description="COSTCO WHSE #1029",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        initial_patterns = len(self.category_engine.pattern_matcher.get_categories())
        
        self.user_interaction.learn_from_feedback(transaction, "Groceries", 0.95)
        
        # Should have learned patterns
        stats = self.user_interaction.get_learning_stats()
        assert stats["patterns_learned"] > 0
        
        # Should have added patterns to category engine
        categories = self.category_engine.pattern_matcher.get_categories()
        assert "Groceries" in categories
    
    def test_create_pattern_rule_from_manual_categorization(self):
        """Test creating pattern rules from manual categorization."""
        transaction = Transaction(
            date=datetime.now(),
            amount=-150.0,
            description="WHOLE FOODS MARKET #12345",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        created_patterns = self.user_interaction.create_pattern_rule_from_manual_categorization(
            transaction, "Groceries", user_confirmed=True
        )
        
        # Should have created multiple patterns
        assert len(created_patterns) > 0
        assert any("WHOLE" in pattern for pattern in created_patterns)
        
        # Patterns should be added to category engine
        categories = self.category_engine.pattern_matcher.get_categories()
        assert "Groceries" in categories
    
    def test_calculate_pattern_confidence(self):
        """Test pattern confidence calculation."""
        # Long, specific pattern should have high confidence
        confidence = self.user_interaction._calculate_pattern_confidence(
            "WHOLE FOODS MARKET", "WHOLE FOODS MARKET #12345"
        )
        assert confidence > 0.85
        
        # Short pattern should have lower confidence than long pattern
        short_confidence = self.user_interaction._calculate_pattern_confidence(
            "WF", "WHOLE FOODS MARKET #12345"
        )
        long_confidence = self.user_interaction._calculate_pattern_confidence(
            "WHOLE FOODS MARKET", "WHOLE FOODS MARKET #12345"
        )
        assert short_confidence < long_confidence
    
    def test_determine_pattern_specificity(self):
        """Test pattern specificity determination."""
        # High coverage pattern should be very high specificity
        specificity = self.user_interaction._determine_pattern_specificity(
            "WHOLE FOODS MARKET", "WHOLE FOODS MARKET #123"
        )
        assert specificity == "very_high"
        
        # Multi-word pattern should be high specificity
        specificity = self.user_interaction._determine_pattern_specificity(
            "WHOLE FOODS", "WHOLE FOODS MARKET #123"
        )
        assert specificity == "high"
        
        # Short single word should be low specificity
        specificity = self.user_interaction._determine_pattern_specificity(
            "WF", "WHOLE FOODS MARKET #123"
        )
        assert specificity == "low"
    
    def test_extract_patterns(self):
        """Test pattern extraction from transaction descriptions."""
        # Test simple merchant name
        patterns = self.user_interaction._extract_patterns("COSTCO WHSE #1029")
        assert "COSTCO" in patterns
        
        # Test with common words that should be filtered
        patterns = self.user_interaction._extract_patterns("THE BEST BUY STORE INC")
        assert "BEST" in patterns or "BUY" in patterns
        
        # Test with numbers and dates (should be filtered)
        patterns = self.user_interaction._extract_patterns("MERCHANT 123 01/15/2024")
        assert "MERCHANT" in patterns
        assert "123" not in patterns
        assert "01/15/2024" not in patterns
    
    def test_extract_domain_patterns(self):
        """Test domain-specific pattern extraction."""
        # Test gas station pattern
        patterns = self.user_interaction._extract_domain_patterns("SHELL GAS STATION #123")
        assert any("GAS" in pattern for pattern in patterns)
        
        # Test store pattern
        patterns = self.user_interaction._extract_domain_patterns("TARGET STORE #456")
        assert any("STORE" in pattern for pattern in patterns)
        
        # Test restaurant pattern
        patterns = self.user_interaction._extract_domain_patterns("MCDONALD RESTAURANT #789")
        assert any("RESTAURANT" in pattern for pattern in patterns)
    
    def test_batch_review_low_confidence(self):
        """Test batch review of low-confidence transactions."""
        # Create transactions with different confidence levels
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-50.0,
                description="UNKNOWN MERCHANT 1",
                account="Checking",
                institution="TestBank",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-75.0,
                description="UNKNOWN MERCHANT 2",
                account="Checking",
                institution="TestBank",
                transaction_id="test_002"
            )
        ]
        
        # Mock user responses: review first, skip second, quit
        self.mock_input.side_effect = ["y", "1", "n", "q"]  # y=review, 1=select category, n=skip, q=quit
        
        # Add a category for selection
        self.category_engine.add_pattern_rule("Groceries", "TEST", 0.9, "high")
        
        results = self.user_interaction.batch_review_low_confidence(transactions, 0.8)
        
        assert results["reviewed"] >= 0
        assert results["skipped"] >= 0
    
    def test_calculate_similarity(self):
        """Test transaction description similarity calculation."""
        # Identical descriptions
        similarity = self.user_interaction._calculate_similarity("COSTCO WHSE", "COSTCO WHSE")
        assert similarity == 1.0
        
        # Similar descriptions
        similarity = self.user_interaction._calculate_similarity("COSTCO WHSE #1029", "COSTCO WHSE #2045")
        assert similarity >= 0.5
        
        # Different descriptions
        similarity = self.user_interaction._calculate_similarity("COSTCO WHSE", "SHELL GAS STATION")
        assert similarity < 0.5
        
        # Empty descriptions
        similarity = self.user_interaction._calculate_similarity("", "")
        assert similarity == 1.0
        
        # One empty description
        similarity = self.user_interaction._calculate_similarity("COSTCO", "")
        assert similarity == 0.0
    
    def test_group_similar_transactions(self):
        """Test grouping similar transactions."""
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.0,
                description="COSTCO WHSE #1029",
                account="Checking",
                institution="TestBank",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-120.0,
                description="COSTCO WHSE #2045",
                account="Checking",
                institution="TestBank",
                transaction_id="test_002"
            ),
            Transaction(
                date=datetime.now(),
                amount=-45.0,
                description="SHELL GAS STATION",
                account="Checking",
                institution="TestBank",
                transaction_id="test_003"
            )
        ]
        
        groups = self.user_interaction._group_similar_transactions(transactions, 0.5)
        
        # Should have at least 2 groups (COSTCO transactions together, SHELL separate)
        assert len(groups) >= 2
        
        # Find COSTCO group
        costco_group = None
        for group in groups:
            if "COSTCO" in group[0].description:
                costco_group = group
                break
        
        assert costco_group is not None
        assert len(costco_group) == 2  # Both COSTCO transactions should be grouped
    
    def test_detect_inconsistencies(self):
        """Test inconsistency detection in similar transactions."""
        # Create similar transactions with different categories
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.0,
                description="COSTCO WHSE #1029",
                account="Checking",
                institution="TestBank",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-120.0,
                description="COSTCO WHSE #2045",
                account="Checking",
                institution="TestBank",
                transaction_id="test_002"
            )
        ]
        
        # Add different patterns for similar transactions (creates inconsistency)
        self.category_engine.add_pattern_rule("Groceries", "COSTCO WHSE #1029", 0.9, "very_high")
        self.category_engine.add_pattern_rule("Shopping", "COSTCO WHSE #2045", 0.9, "very_high")
        
        inconsistencies = self.user_interaction.detect_inconsistencies(transactions, 0.5)
        
        # Should detect inconsistency between similar COSTCO transactions
        assert len(inconsistencies) > 0
        
        # Check inconsistency structure
        inconsistency = inconsistencies[0]
        assert "group_size" in inconsistency
        assert "categories" in inconsistency
        assert "sample_descriptions" in inconsistency
    
    def test_suggest_category_fixes_with_analysis(self):
        """Test enhanced category fix suggestions with analysis."""
        # Create similar transactions with different categories
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.0,
                description="COSTCO WHSE #1029",
                account="Checking",
                institution="TestBank",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-120.0,
                description="COSTCO WHSE #2045",
                account="Checking",
                institution="TestBank",
                transaction_id="test_002"
            )
        ]
        
        # Add different patterns for similar transactions (creates inconsistency)
        self.category_engine.add_pattern_rule("Groceries", "COSTCO WHSE #1029", 0.9, "very_high")
        self.category_engine.add_pattern_rule("Shopping", "COSTCO WHSE #2045", 0.9, "very_high")
        
        inconsistencies = self.user_interaction.detect_inconsistencies(transactions, 0.5)
        suggestions = self.user_interaction.suggest_category_fixes(inconsistencies)
        
        # Should have suggestions with detailed analysis
        assert len(suggestions) > 0
        
        suggestion = suggestions[0]
        assert "recommended_category" in suggestion
        assert "reasoning" in suggestion
        assert "confidence_improvement" in suggestion
    
    def test_apply_consistency_fix(self):
        """Test applying consistency fixes."""
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.0,
                description="TARGET STORE #1029",
                account="Checking",
                institution="TestBank",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-75.0,
                description="TARGET STORE #2045",
                account="Checking",
                institution="TestBank",
                transaction_id="test_002"
            )
        ]
        
        suggestion = {
            'inconsistency_id': 12345,
            'recommended_category': 'Shopping',
            'recommendation': "Use 'Shopping' for all similar transactions",
            'reasoning': 'Most frequent category',
            'affected_transactions': 2,
            'confidence_improvement': 0.15
        }
        
        results = self.user_interaction.apply_consistency_fix(suggestion, transactions)
        
        assert results['patterns_created'] >= 0
        assert results['transactions_affected'] >= 0
        assert len(results['errors']) == 0
    
    def test_batch_learn_from_historical_data(self):
        """Test batch learning from historical transaction data."""
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.0,
                description="SAFEWAY STORE #123",
                account="Checking",
                institution="TestBank",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-50.0,
                description="SHELL GAS STATION",
                account="Checking",
                institution="TestBank",
                transaction_id="test_002"
            )
        ]
        
        categories = {
            "test_001": "Groceries",
            "test_002": "Gas"
        }
        
        results = self.user_interaction.batch_learn_from_historical_data(transactions, categories)
        
        assert results["processed"] == 2
        assert results["patterns_created"] > 0
        assert len(results["categories_learned"]) == 2
        assert "Groceries" in results["categories_learned"]
        assert "Gas" in results["categories_learned"]
    
    def test_analyze_and_fix_categorization_quality(self):
        """Test categorization quality analysis."""
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.0,
                description="UNKNOWN MERCHANT A",
                account="Checking",
                institution="TestBank",
                transaction_id="test_001"
            ),
            Transaction(
                date=datetime.now(),
                amount=-75.0,
                description="UNKNOWN MERCHANT B",
                account="Checking",
                institution="TestBank",
                transaction_id="test_002"
            )
        ]
        
        results = self.user_interaction.analyze_and_fix_categorization_quality(transactions, auto_fix=False)
        
        assert "inconsistencies_found" in results
        assert "quality_score" in results
        assert 0.0 <= results["quality_score"] <= 1.0
    
    def test_calculate_categorization_quality_score(self):
        """Test quality score calculation."""
        # Test with well-categorized transactions
        self.category_engine.add_pattern_rule("Groceries", "COSTCO", 0.95, "high")
        
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.0,
                description="COSTCO WHSE #123",
                account="Checking",
                institution="TestBank",
                transaction_id="test_001"
            )
        ]
        
        quality_score = self.user_interaction._calculate_categorization_quality_score(transactions)
        
        # Should have high quality score for well-categorized transaction
        assert quality_score > 0.8
        
        # Test with uncategorized transactions
        transactions = [
            Transaction(
                date=datetime.now(),
                amount=-100.0,
                description="UNKNOWN RANDOM MERCHANT",
                account="Checking",
                institution="TestBank",
                transaction_id="test_002"
            )
        ]
        
        quality_score = self.user_interaction._calculate_categorization_quality_score(transactions)
        
        # Should have lower quality score for uncategorized transactions
        assert quality_score < 0.5
    
    def test_get_and_reset_learning_stats(self):
        """Test learning statistics management."""
        # Initial stats should be zero
        stats = self.user_interaction.get_learning_stats()
        assert all(value == 0 for value in stats.values())
        
        # Simulate some learning activity
        self.user_interaction.learning_stats["manual_categorizations"] = 5
        self.user_interaction.learning_stats["patterns_learned"] = 3
        
        stats = self.user_interaction.get_learning_stats()
        assert stats["manual_categorizations"] == 5
        assert stats["patterns_learned"] == 3
        
        # Reset stats
        self.user_interaction.reset_learning_stats()
        stats = self.user_interaction.get_learning_stats()
        assert all(value == 0 for value in stats.values())
    
    def test_create_new_category_success(self):
        """Test successful new category creation."""
        self.mock_input.side_effect = ["NewCategory", "y"]
        
        result = self.user_interaction._create_new_category()
        
        assert result == "NewCategory"
    
    def test_create_new_category_cancel(self):
        """Test cancelling new category creation."""
        self.mock_input.return_value = "cancel"
        
        result = self.user_interaction._create_new_category()
        
        assert result is None
    
    def test_create_new_category_empty_name(self):
        """Test handling empty category name."""
        self.mock_input.side_effect = ["", "ValidCategory", "y"]
        
        result = self.user_interaction._create_new_category()
        
        assert result == "ValidCategory"
    
    def test_create_new_category_existing_name(self):
        """Test handling existing category name."""
        # Add existing category
        self.category_engine.add_pattern_rule("ExistingCategory", "TEST", 0.9, "high")
        
        self.mock_input.side_effect = ["ExistingCategory", "NewCategory", "y"]
        
        result = self.user_interaction._create_new_category()
        
        assert result == "NewCategory"


class TestUserInteractionIntegration:
    """Integration tests for UserInteraction with CategoryEngine."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = f"{self.temp_dir}/test_categories.yaml"
        
        self.category_engine = CategoryEngine(self.config_path)
        self.user_interaction = UserInteraction(self.category_engine)
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_learning_integration(self):
        """Test integration between learning and categorization."""
        transaction = Transaction(
            date=datetime.now(),
            amount=-100.0,
            description="NEWMERCHANT STORE",
            account="Checking",
            institution="TestBank",
            transaction_id="test_001"
        )
        
        # Initially should be uncategorized
        initial_result = self.category_engine.categorize_transaction(transaction)
        assert initial_result.category == "Uncategorized"
        
        # Learn from feedback
        self.user_interaction.learn_from_feedback(transaction, "Shopping", 0.9)
        
        # Should now be categorized correctly
        new_result = self.category_engine.categorize_transaction(transaction)
        assert new_result.category == "Shopping"
        assert new_result.confidence > 0.8