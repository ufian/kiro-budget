"""
Machine Learning categorizer for transaction categorization using scikit-learn.
"""

import logging
import pickle
import os
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

from .interfaces import Categorizer
from .models import Transaction, CategoryResult, TransactionFeatures


class MLCategorizer(Categorizer):
    """
    Machine Learning categorizer that uses scikit-learn to predict transaction categories
    based on transaction descriptions, amounts, and other features.
    """
    
    def __init__(self, model_path: str = "ml_model.pkl", 
                 confidence_threshold: float = 0.6,
                 retrain_threshold: int = 100):
        """
        Initialize the ML categorizer.
        
        Args:
            model_path: Path to save/load the trained model
            confidence_threshold: Minimum confidence for predictions
            retrain_threshold: Number of new samples before retraining
        """
        self.logger = logging.getLogger(__name__)
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.retrain_threshold = retrain_threshold
        
        # ML components
        self.model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2
        )
        self.text_vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 2),
            stop_words='english',
            lowercase=True
        )
        self.label_encoder = LabelEncoder()
        
        # Training data storage
        self.training_data = []
        self.new_samples_count = 0
        self.is_trained = False
        
        # Feature extraction parameters
        self.amount_buckets = [
            (0, 10, "micro"),
            (10, 50, "small"),
            (50, 200, "medium"),
            (200, 1000, "large"),
            (1000, float('inf'), "very_large")
        ]
        
        # Load existing model if available
        self._load_model()
    
    def categorize(self, transaction: Transaction) -> Optional[CategoryResult]:
        """
        Categorize a transaction using the ML model.
        
        Args:
            transaction: The transaction to categorize
            
        Returns:
            CategoryResult if prediction confidence is above threshold, None otherwise
        """
        if not self.is_trained:
            self.logger.debug("ML model not trained, skipping ML categorization")
            return None
        
        try:
            # Extract features
            features = self.extract_features(transaction)
            
            # Make prediction
            prediction_proba = self.model.predict_proba([features])[0]
            predicted_class_idx = np.argmax(prediction_proba)
            confidence = prediction_proba[predicted_class_idx]
            
            # Check confidence threshold
            if confidence < self.confidence_threshold:
                self.logger.debug(f"ML prediction confidence {confidence:.3f} below threshold {self.confidence_threshold}")
                return None
            
            # Get category name
            category = self.label_encoder.inverse_transform([predicted_class_idx])[0]
            
            return CategoryResult(
                category=category,
                confidence=confidence,
                method="ml",
                reasoning=f"ML prediction with {confidence:.3f} confidence"
            )
            
        except Exception as e:
            self.logger.warning(f"ML categorization failed: {e}")
            return None
    
    def get_confidence_threshold(self) -> float:
        """Get the minimum confidence threshold for this categorizer."""
        return self.confidence_threshold
    
    def extract_features(self, transaction: Transaction) -> np.ndarray:
        """
        Extract features from a transaction for ML prediction.
        
        Args:
            transaction: Transaction to extract features from
            
        Returns:
            Feature vector as numpy array
        """
        # Text features (TF-IDF)
        text_features = self.text_vectorizer.transform([transaction.description]).toarray()[0]
        
        # Amount features
        amount_bucket = self._get_amount_bucket(abs(transaction.amount))
        amount_log = np.log1p(abs(transaction.amount))  # Log transform for better distribution
        
        # Temporal features
        day_of_week = transaction.date.weekday()
        hour_of_day = transaction.date.hour if hasattr(transaction.date, 'hour') else 12
        is_weekend = 1 if day_of_week >= 5 else 0
        
        # Account features (encoded as simple hash for now)
        account_hash = hash(transaction.account) % 100 if transaction.account else 0
        institution_hash = hash(transaction.institution) % 100 if transaction.institution else 0
        
        # Combine all features
        numerical_features = np.array([
            amount_log,
            amount_bucket,
            day_of_week,
            hour_of_day,
            is_weekend,
            account_hash,
            institution_hash
        ])
        
        # Concatenate text and numerical features
        features = np.concatenate([text_features, numerical_features])
        
        return features
    
    def train_model(self, training_data: List[Tuple[Transaction, str]]) -> Dict[str, Any]:
        """
        Train the ML model on labeled transaction data.
        
        Args:
            training_data: List of (transaction, category) tuples
            
        Returns:
            Training metrics and statistics
        """
        if len(training_data) < 10:
            self.logger.warning(f"Insufficient training data: {len(training_data)} samples (minimum 10 required)")
            return {"error": "Insufficient training data"}
        
        self.logger.info(f"Training ML model with {len(training_data)} samples")
        
        try:
            # Prepare data
            transactions, categories = zip(*training_data)
            
            # Extract text features
            descriptions = [t.description for t in transactions]
            self.text_vectorizer.fit(descriptions)
            
            # Encode labels
            self.label_encoder.fit(categories)
            encoded_labels = self.label_encoder.transform(categories)
            
            # Extract all features
            feature_matrix = np.array([self.extract_features(t) for t in transactions])
            
            # Split data for validation
            if len(training_data) >= 20:
                X_train, X_test, y_train, y_test = train_test_split(
                    feature_matrix, encoded_labels, 
                    test_size=0.2, 
                    random_state=42,
                    stratify=encoded_labels if len(np.unique(encoded_labels)) > 1 else None
                )
            else:
                # Use all data for training if dataset is small
                X_train, X_test = feature_matrix, feature_matrix
                y_train, y_test = encoded_labels, encoded_labels
            
            # Train model
            self.model.fit(X_train, y_train)
            self.is_trained = True
            
            # Evaluate model
            train_accuracy = accuracy_score(y_train, self.model.predict(X_train))
            test_accuracy = accuracy_score(y_test, self.model.predict(X_test))
            
            # Get feature importance
            feature_names = (
                [f"text_{i}" for i in range(self.text_vectorizer.max_features)] +
                ["amount_log", "amount_bucket", "day_of_week", "hour_of_day", 
                 "is_weekend", "account_hash", "institution_hash"]
            )
            
            # Store training data for incremental learning
            self.training_data = training_data
            self.new_samples_count = 0
            
            # Save model
            self._save_model()
            
            metrics = {
                "training_samples": len(training_data),
                "train_accuracy": train_accuracy,
                "test_accuracy": test_accuracy,
                "categories": list(self.label_encoder.classes_),
                "feature_count": len(feature_names),
                "model_trained": True
            }
            
            self.logger.info(f"ML model trained successfully: {train_accuracy:.3f} train accuracy, {test_accuracy:.3f} test accuracy")
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to train ML model: {e}")
            return {"error": str(e)}
    
    def update_with_feedback(self, transaction: Transaction, correct_category: str) -> None:
        """
        Update the model with user feedback for incremental learning.
        
        Args:
            transaction: The transaction that was manually categorized
            correct_category: The correct category assigned by the user
        """
        try:
            # Add to training data
            self.training_data.append((transaction, correct_category))
            self.new_samples_count += 1
            
            self.logger.debug(f"Added feedback sample: {transaction.description} -> {correct_category}")
            
            # Retrain if we have enough new samples
            if self.new_samples_count >= self.retrain_threshold:
                self.logger.info(f"Retraining ML model with {len(self.training_data)} total samples")
                self.train_model(self.training_data)
            
        except Exception as e:
            self.logger.warning(f"Failed to update ML model with feedback: {e}")
    
    def predict_category(self, features: TransactionFeatures) -> Optional[CategoryResult]:
        """
        Predict category from pre-extracted features.
        
        Args:
            features: Pre-extracted transaction features
            
        Returns:
            CategoryResult if prediction confidence is above threshold, None otherwise
        """
        if not self.is_trained:
            return None
        
        try:
            # Convert TransactionFeatures to feature vector
            if features.description_vector is not None:
                feature_vector = features.description_vector
            else:
                # Create minimal feature vector if description vector not available
                feature_vector = np.zeros(self.text_vectorizer.max_features + 7)
                
                if features.amount is not None:
                    feature_vector[-7] = np.log1p(abs(features.amount))
                    feature_vector[-6] = self._get_amount_bucket(abs(features.amount))
                
                if features.day_of_week is not None:
                    feature_vector[-5] = features.day_of_week
            
            # Make prediction
            prediction_proba = self.model.predict_proba([feature_vector])[0]
            predicted_class_idx = np.argmax(prediction_proba)
            confidence = prediction_proba[predicted_class_idx]
            
            if confidence < self.confidence_threshold:
                return None
            
            category = self.label_encoder.inverse_transform([predicted_class_idx])[0]
            
            return CategoryResult(
                category=category,
                confidence=confidence,
                method="ml",
                reasoning=f"ML prediction from features with {confidence:.3f} confidence"
            )
            
        except Exception as e:
            self.logger.warning(f"ML prediction from features failed: {e}")
            return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current ML model.
        
        Returns:
            Dictionary with model information and statistics
        """
        info = {
            "is_trained": self.is_trained,
            "confidence_threshold": self.confidence_threshold,
            "retrain_threshold": self.retrain_threshold,
            "training_samples": len(self.training_data),
            "new_samples_count": self.new_samples_count,
            "model_path": self.model_path
        }
        
        if self.is_trained:
            info.update({
                "categories": list(self.label_encoder.classes_),
                "feature_count": self.text_vectorizer.max_features + 7,
                "model_type": "RandomForestClassifier"
            })
        
        return info
    
    def _get_amount_bucket(self, amount: float) -> int:
        """
        Get the amount bucket index for a given amount.
        
        Args:
            amount: Transaction amount (absolute value)
            
        Returns:
            Bucket index (0-4)
        """
        for i, (min_val, max_val, _) in enumerate(self.amount_buckets):
            if min_val <= amount < max_val:
                return i
        return len(self.amount_buckets) - 1  # Default to largest bucket
    
    def _save_model(self) -> None:
        """Save the trained model to disk."""
        try:
            model_data = {
                'model': self.model,
                'text_vectorizer': self.text_vectorizer,
                'label_encoder': self.label_encoder,
                'training_data': self.training_data,
                'confidence_threshold': self.confidence_threshold,
                'retrain_threshold': self.retrain_threshold,
                'is_trained': self.is_trained,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(self.model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            self.logger.info(f"ML model saved to {self.model_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save ML model: {e}")
    
    def _load_model(self) -> None:
        """Load a previously trained model from disk."""
        if not os.path.exists(self.model_path):
            self.logger.debug(f"No existing ML model found at {self.model_path}")
            return
        
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.model = model_data['model']
            self.text_vectorizer = model_data['text_vectorizer']
            self.label_encoder = model_data['label_encoder']
            self.training_data = model_data.get('training_data', [])
            self.confidence_threshold = model_data.get('confidence_threshold', self.confidence_threshold)
            self.retrain_threshold = model_data.get('retrain_threshold', self.retrain_threshold)
            self.is_trained = model_data.get('is_trained', False)
            
            self.logger.info(f"ML model loaded from {self.model_path} with {len(self.training_data)} training samples")
            
        except Exception as e:
            self.logger.warning(f"Failed to load ML model: {e}")
            self.is_trained = False