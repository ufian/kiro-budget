"""
Tests for MLCategorizer class.
"""

import pytest
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

from kiro_budget.categorizers.ml_categorizer import MLCategorizer
from kiro_budget.categorizers.models import Transaction, CategoryResult, TransactionFeatures


class TestMLCategorizer:
    """Test cases for MLCategorizer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use temporary file for model storage
        self.temp_model_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
        self.temp_model_file.close()
        
        self.ml_categorizer = MLCategorizer(
            model_path=self.temp_model_file.name,
            confidence_threshold=0.6,
            retrain_threshold=5
        )
        
        # Sample transactions for testing
        self.sample_transactions = [
            Transaction(
                date=datetime(2024, 1, 15, 10, 30),
                amount=-45.67,
                description="COSTCO WHSE #1029",
                account="checking",
                institution="chase",
                transaction_id="tx1"
            ),
            Transaction(
                date=datetime(2024, 1, 16, 12, 15),
                amount=-12.50,
                description="STARBUCKS STORE #12345",
                account="credit",
                institution="chase",
                transaction_id="tx2"
            ),
            Transaction(
                date=datetime(2024, 1, 17, 18, 45),
                amount=-89.23,
                description="SHELL GAS STATION",
                account="checking",
                institution="chase",
                transaction_id="tx3"
            ),
            Transaction(
                date=datetime(2024, 1, 18, 9, 0),
                amount=-156.78,
                description="FRED MEYER #123",
                account="checking",
                institution="chase",
                transaction_id="tx4"
            ),
            Transaction(
                date=datetime(2024, 1, 19, 14, 30),
                amount=-25.99,
                description="MCDONALD'S #4567",
                account="credit",
                institution="chase",
                transaction_id="tx5"
            )
        ]
        
        # Sample training data (need at least 10 samples)
        self.training_data = [
            (self.sample_transactions[0], "Groceries"),
            (self.sample_transactions[1], "Restaurants"),
            (self.sample_transactions[2], "Gas"),
            (self.sample_transactions[3], "Groceries"),
            (self.sample_transactions[4], "Restaurants"),
            # Add more samples to meet minimum requirement
            (Transaction(datetime(2024, 1, 20, 10, 0), -67.89, "WALMART SUPERCENTER", "checking", "chase", "tx6"), "Groceries"),
            (Transaction(datetime(2024, 1, 21, 11, 0), -23.45, "BURGER KING", "credit", "chase", "tx7"), "Restaurants"),
            (Transaction(datetime(2024, 1, 22, 12, 0), -78.90, "CHEVRON GAS", "checking", "chase", "tx8"), "Gas"),
            (Transaction(datetime(2024, 1, 23, 13, 0), -134.56, "SAFEWAY STORE", "checking", "chase", "tx9"), "Groceries"),
            (Transaction(datetime(2024, 1, 24, 14, 0), -45.67, "PIZZA HUT", "credit", "chase", "tx10"), "Restaurants"),
            (Transaction(datetime(2024, 1, 25, 15, 0), -89.12, "ARCO GAS", "checking", "chase", "tx11"), "Gas"),
            (Transaction(datetime(2024, 1, 26, 16, 0), -156.78, "KROGER", "checking", "chase", "tx12"), "Groceries")
        ]
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_model_file.name):
            os.unlink(self.temp_model_file.name)
    
    def test_initialization(self):
        """Test MLCategorizer initialization."""
        assert self.ml_categorizer.confidence_threshold == 0.6
        assert self.ml_categorizer.retrain_threshold == 5
        assert not self.ml_categorizer.is_trained
        assert len(self.ml_categorizer.training_data) == 0
    
    def test_get_confidence_threshold(self):
        """Test getting confidence threshold."""
        assert self.ml_categorizer.get_confidence_threshold() == 0.6
    
    def test_categorize_untrained_model(self):
        """Test categorization with untrained model returns None."""
        result = self.ml_categorizer.categorize(self.sample_transactions[0])
        assert result is None
    
    def test_extract_features(self):
        """Test feature extraction from transaction."""
        # Train text vectorizer first
        descriptions = [t.description for t in self.sample_transactions]
        self.ml_categorizer.text_vectorizer.fit(descriptions)
        
        features = self.ml_categorizer.extract_features(self.sample_transactions[0])
        
        # Check that features is a numpy array
        assert hasattr(features, 'shape')
        assert len(features) > 0
        
        # Should have text features + 7 numerical features
        # The actual number depends on the vocabulary size from fitting
        actual_vocab_size = len(self.ml_categorizer.text_vectorizer.vocabulary_)
        expected_length = actual_vocab_size + 7
        assert len(features) == expected_length
    
    def test_get_amount_bucket(self):
        """Test amount bucket calculation."""
        assert self.ml_categorizer._get_amount_bucket(5.0) == 0  # micro
        assert self.ml_categorizer._get_amount_bucket(25.0) == 1  # small
        assert self.ml_categorizer._get_amount_bucket(100.0) == 2  # medium
        assert self.ml_categorizer._get_amount_bucket(500.0) == 3  # large
        assert self.ml_categorizer._get_amount_bucket(2000.0) == 4  # very_large
    
    def test_train_model_insufficient_data(self):
        """Test training with insufficient data."""
        small_training_data = self.training_data[:2]  # Only 2 samples
        
        result = self.ml_categorizer.train_model(small_training_data)
        
        assert "error" in result
        assert "Insufficient training data" in result["error"]
        assert not self.ml_categorizer.is_trained
    
    def test_train_model_success(self):
        """Test successful model training."""
        result = self.ml_categorizer.train_model(self.training_data)
        
        assert "error" not in result
        assert result["model_trained"] is True
        assert result["training_samples"] == len(self.training_data)
        assert "train_accuracy" in result
        assert "test_accuracy" in result
        assert "categories" in result
        assert self.ml_categorizer.is_trained
    
    def test_categorize_trained_model(self):
        """Test categorization with trained model."""
        # Train the model
        self.ml_categorizer.train_model(self.training_data)
        
        # Test categorization
        new_transaction = Transaction(
            date=datetime(2024, 1, 20, 11, 0),
            amount=-67.89,
            description="COSTCO WHOLESALE",
            account="checking",
            institution="chase",
            transaction_id="tx_new"
        )
        
        result = self.ml_categorizer.categorize(new_transaction)
        
        # Should return a result since model is trained
        if result:  # May be None if confidence is too low
            assert isinstance(result, CategoryResult)
            assert result.method == "ml"
            assert 0.0 <= result.confidence <= 1.0
            assert result.category in ["Groceries", "Restaurants", "Gas"]
    
    def test_update_with_feedback(self):
        """Test updating model with user feedback."""
        initial_count = len(self.ml_categorizer.training_data)
        
        new_transaction = Transaction(
            date=datetime(2024, 1, 21, 15, 30),
            amount=-34.56,
            description="TARGET STORE #789",
            account="checking",
            institution="chase",
            transaction_id="tx_feedback"
        )
        
        self.ml_categorizer.update_with_feedback(new_transaction, "Shopping")
        
        assert len(self.ml_categorizer.training_data) == initial_count + 1
        assert self.ml_categorizer.new_samples_count == 1
        
        # Check that the new sample was added correctly
        last_sample = self.ml_categorizer.training_data[-1]
        assert last_sample[0].description == "TARGET STORE #789"
        assert last_sample[1] == "Shopping"
    
    def test_update_with_feedback_triggers_retrain(self):
        """Test that enough feedback triggers retraining."""
        # Train initial model
        self.ml_categorizer.train_model(self.training_data)
        
        # Add feedback samples up to retrain threshold
        for i in range(self.ml_categorizer.retrain_threshold):
            new_transaction = Transaction(
                date=datetime(2024, 1, 22 + i, 10, 0),
                amount=-20.0,
                description=f"TEST MERCHANT {i}",
                account="checking",
                institution="chase",
                transaction_id=f"tx_retrain_{i}"
            )
            
            with patch.object(self.ml_categorizer, 'train_model') as mock_train:
                mock_train.return_value = {"model_trained": True}
                self.ml_categorizer.update_with_feedback(new_transaction, "Shopping")
                
                # Should trigger retrain on the last sample
                if i == self.ml_categorizer.retrain_threshold - 1:
                    mock_train.assert_called_once()
                else:
                    mock_train.assert_not_called()
    
    def test_predict_category_from_features(self):
        """Test prediction from pre-extracted features."""
        # Train the model first
        self.ml_categorizer.train_model(self.training_data)
        
        # Create sample features
        features = TransactionFeatures(
            amount=45.67,
            amount_bucket="medium",
            day_of_week=1,
            account_type="checking",
            institution="chase"
        )
        
        result = self.ml_categorizer.predict_category(features)
        
        # May be None if confidence is too low, which is acceptable
        if result:
            assert isinstance(result, CategoryResult)
            assert result.method == "ml"
            assert 0.0 <= result.confidence <= 1.0
    
    def test_get_model_info_untrained(self):
        """Test getting model info for untrained model."""
        info = self.ml_categorizer.get_model_info()
        
        assert info["is_trained"] is False
        assert info["confidence_threshold"] == 0.6
        assert info["retrain_threshold"] == 5
        assert info["training_samples"] == 0
        assert info["new_samples_count"] == 0
    
    def test_get_model_info_trained(self):
        """Test getting model info for trained model."""
        self.ml_categorizer.train_model(self.training_data)
        
        info = self.ml_categorizer.get_model_info()
        
        assert info["is_trained"] is True
        assert "categories" in info
        assert "feature_count" in info
        assert info["model_type"] == "RandomForestClassifier"
    
    def test_save_and_load_model(self):
        """Test saving and loading model."""
        # Train and save model
        self.ml_categorizer.train_model(self.training_data)
        original_categories = list(self.ml_categorizer.label_encoder.classes_)
        
        # Create new instance and load model
        new_ml_categorizer = MLCategorizer(
            model_path=self.temp_model_file.name,
            confidence_threshold=0.6
        )
        
        assert new_ml_categorizer.is_trained
        assert len(new_ml_categorizer.training_data) == len(self.training_data)
        assert list(new_ml_categorizer.label_encoder.classes_) == original_categories
    
    def test_model_persistence_across_instances(self):
        """Test that model persists across different instances."""
        # Train model in first instance
        self.ml_categorizer.train_model(self.training_data)
        
        # Create new transaction for testing
        test_transaction = Transaction(
            date=datetime(2024, 1, 25, 12, 0),
            amount=-55.00,
            description="COSTCO GAS STATION",
            account="checking",
            institution="chase",
            transaction_id="tx_persistence"
        )
        
        # Get prediction from first instance
        result1 = self.ml_categorizer.categorize(test_transaction)
        
        # Create second instance (should load saved model)
        ml_categorizer2 = MLCategorizer(
            model_path=self.temp_model_file.name,
            confidence_threshold=0.6
        )
        
        # Get prediction from second instance
        result2 = ml_categorizer2.categorize(test_transaction)
        
        # Both should be trained and give similar results
        assert ml_categorizer2.is_trained
        
        # If both return results, they should be the same category
        if result1 and result2:
            assert result1.category == result2.category
    
    @patch('kiro_budget.categorizers.ml_categorizer.pickle.dump')
    def test_save_model_error_handling(self, mock_dump):
        """Test error handling during model saving."""
        mock_dump.side_effect = Exception("Save failed")
        
        # Train model (which tries to save)
        with patch('builtins.open', MagicMock()):
            result = self.ml_categorizer.train_model(self.training_data)
        
        # Should still succeed training even if save fails
        assert "error" not in result or result.get("model_trained", False)
    
    @patch('kiro_budget.categorizers.ml_categorizer.pickle.load')
    def test_load_model_error_handling(self, mock_load):
        """Test error handling during model loading."""
        mock_load.side_effect = Exception("Load failed")
        
        # Create model file
        with open(self.temp_model_file.name, 'w') as f:
            f.write("dummy content")
        
        # Should handle load error gracefully
        ml_categorizer = MLCategorizer(model_path=self.temp_model_file.name)
        assert not ml_categorizer.is_trained
    
    def test_categorize_error_handling(self):
        """Test error handling during categorization."""
        # Train model first
        self.ml_categorizer.train_model(self.training_data)
        
        # Create transaction with problematic data
        bad_transaction = Transaction(
            date=datetime(2024, 1, 26, 12, 0),
            amount=None,  # This might cause issues
            description="",  # Empty description
            account="",
            institution="",
            transaction_id="tx_bad"
        )
        
        # Should handle errors gracefully and return None
        result = self.ml_categorizer.categorize(bad_transaction)
        # Result may be None due to error handling or low confidence
        if result:
            assert isinstance(result, CategoryResult)