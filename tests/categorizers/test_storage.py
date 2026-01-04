"""
Tests for CategoryStorage class with property-based testing.
"""

import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st, settings

from kiro_budget.categorizers.storage import CategoryStorage


class TestCategoryStorage:
    """Test CategoryStorage functionality."""
    
    def setup_method(self):
        """Set up test environment with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_categories.yaml"
        self.storage = CategoryStorage(str(self.config_path))
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_categories_creates_default_when_missing(self):
        """Test that load_categories creates default config when file doesn't exist."""
        config = self.storage.load_categories()
        
        assert config["version"] == "1.0"
        assert config["default_category"] == "Uncategorized"
        assert config["confidence_threshold"] == 0.7
        assert "categories" in config
        assert "ai_config" in config
        assert "ml_config" in config
        
        # Verify file was created
        assert self.config_path.exists()
    
    def test_save_and_load_categories_roundtrip(self):
        """Test that saving and loading categories preserves data."""
        test_config = {
            "version": "1.0",
            "default_category": "Test",
            "confidence_threshold": 0.8,
            "categories": {
                "TestCategory": {
                    "patterns": [
                        {
                            "pattern": "TEST",
                            "confidence": 0.9,
                            "type": "substring",
                            "specificity": "high"
                        }
                    ]
                }
            },
            "ai_config": {"enabled": False},
            "ml_config": {"enabled": False}
        }
        
        self.storage.save_categories(test_config)
        loaded_config = self.storage.load_categories()
        
        assert loaded_config["version"] == test_config["version"]
        assert loaded_config["default_category"] == test_config["default_category"]
        assert loaded_config["confidence_threshold"] == test_config["confidence_threshold"]
        assert "TestCategory" in loaded_config["categories"]
    
    def test_add_pattern_rule(self):
        """Test adding pattern rules to configuration."""
        self.storage.add_pattern_rule("Groceries", "COSTCO", 0.95, "high", "substring")
        
        config = self.storage.load_categories()
        assert "Groceries" in config["categories"]
        
        patterns = config["categories"]["Groceries"]["patterns"]
        assert len(patterns) == 1
        assert patterns[0]["pattern"] == "COSTCO"
        assert patterns[0]["confidence"] == 0.95
        assert patterns[0]["specificity"] == "high"
        assert patterns[0]["type"] == "substring"
    
    def test_backup_config(self):
        """Test configuration backup functionality."""
        # Create initial config
        test_config = {
            "version": "1.0", 
            "default_category": "Uncategorized",
            "confidence_threshold": 0.7,
            "categories": {}
        }
        self.storage.save_categories(test_config)
        
        # Create backup
        backup_path = self.storage.backup_config()
        
        assert Path(backup_path).exists()
        assert "categories_backup_" in backup_path
        assert backup_path.endswith(".yaml")
        
        # Verify backup content
        with open(backup_path, 'r') as f:
            backup_config = yaml.safe_load(f)
        assert backup_config["version"] == "1.0"
    
    def test_backup_config_nonexistent_file(self):
        """Test backup fails gracefully when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            self.storage.backup_config()
    
    def test_validate_config_valid(self):
        """Test validation of valid configuration."""
        valid_config = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": 0.7,
            "categories": {
                "Groceries": {
                    "patterns": [
                        {
                            "pattern": "COSTCO",
                            "confidence": 0.9,
                            "type": "substring",
                            "specificity": "high"
                        }
                    ]
                }
            }
        }
        
        result = self.storage.validate_config(valid_config)
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_config_missing_required_keys(self):
        """Test validation fails for missing required keys."""
        invalid_config = {"version": "1.0"}  # Missing required keys
        
        result = self.storage.validate_config(invalid_config)
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("Missing required key" in error for error in result["errors"])
    
    def test_validate_config_invalid_confidence_threshold(self):
        """Test validation fails for invalid confidence threshold."""
        invalid_config = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": 1.5,  # Invalid: > 1.0
            "categories": {}
        }
        
        result = self.storage.validate_config(invalid_config)
        assert result["valid"] is False
        assert any("confidence_threshold must be" in error for error in result["errors"])
    
    def test_validate_config_invalid_pattern(self):
        """Test validation fails for invalid pattern configuration."""
        invalid_config = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": 0.7,
            "categories": {
                "TestCategory": {
                    "patterns": [
                        {
                            "pattern": "TEST",
                            "confidence": 1.5,  # Invalid: > 1.0
                            "type": "invalid_type",  # Invalid type
                            "specificity": "invalid_specificity"  # Invalid specificity
                        }
                    ]
                }
            }
        }
        
        result = self.storage.validate_config(invalid_config)
        assert result["valid"] is False
        assert len(result["errors"]) >= 3  # Should have multiple errors
    
    def test_validate_config_invalid_regex(self):
        """Test validation fails for invalid regex patterns."""
        invalid_config = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": 0.7,
            "categories": {
                "TestCategory": {
                    "patterns": [
                        {
                            "pattern": "[invalid regex",  # Invalid regex
                            "confidence": 0.8,
                            "type": "regex",
                            "specificity": "medium"
                        }
                    ]
                }
            }
        }
        
        result = self.storage.validate_config(invalid_config)
        assert result["valid"] is False
        assert any("Invalid regex pattern" in error for error in result["errors"])
    
    def test_get_default_categories(self):
        """Test default categories structure."""
        defaults = self.storage.get_default_categories()
        
        assert defaults["version"] == "1.0"
        assert defaults["default_category"] == "Uncategorized"
        assert "categories" in defaults
        
        # Check some expected default categories
        expected_categories = ["Groceries", "Gas", "Restaurants", "Shopping", "Utilities"]
        for category in expected_categories:
            assert category in defaults["categories"]
            assert "patterns" in defaults["categories"][category]
            assert len(defaults["categories"][category]["patterns"]) > 0
    
    def test_create_default_config(self):
        """Test creating default configuration file."""
        self.storage.create_default_config()
        
        assert self.config_path.exists()
        
        config = self.storage.load_categories()
        assert "Groceries" in config["categories"]
        assert "Gas" in config["categories"]
        
        # Verify COSTCO GAS has higher specificity than COSTCO
        gas_patterns = config["categories"]["Gas"]["patterns"]
        costco_gas_pattern = next(p for p in gas_patterns if p["pattern"] == "COSTCO GAS")
        assert costco_gas_pattern["specificity"] == "very_high"
    
    def test_save_categories_invalid_config(self):
        """Test that saving invalid configuration raises error."""
        invalid_config = {
            "version": "1.0",
            "confidence_threshold": 2.0,  # Invalid
            "categories": {}
        }
        
        with pytest.raises(ValueError, match="Invalid configuration"):
            self.storage.save_categories(invalid_config)
    
    def test_load_categories_invalid_yaml(self):
        """Test handling of invalid YAML files."""
        # Write invalid YAML to file
        with open(self.config_path, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        with pytest.raises(ValueError, match="Invalid YAML"):
            self.storage.load_categories()


# Property-based tests
class TestCategoryStorageProperties:
    """Property-based tests for CategoryStorage."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_categories.yaml"
        self.storage = CategoryStorage(str(self.config_path))
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @given(
        category_name=st.text(alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd']), min_size=1, max_size=20).filter(lambda x: x.strip()),
        pattern=st.text(alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd', 'Pc']), min_size=1, max_size=50),
        confidence=st.floats(min_value=0.0, max_value=1.0),
        specificity=st.sampled_from(["low", "medium", "high", "very_high"])
    )
    @settings(deadline=None, max_examples=10)
    def test_property_add_pattern_rule_persistence(self, category_name, pattern, confidence, specificity):
        """
        Feature: transaction-categorization, Property 32: Human-Readable Storage Organization
        For any valid pattern rule addition, it should be persisted and retrievable.
        """
        # Add pattern rule
        self.storage.add_pattern_rule(category_name, pattern, confidence, specificity)
        
        # Load configuration and verify persistence
        config = self.storage.load_categories()
        
        assert category_name in config["categories"]
        patterns = config["categories"][category_name]["patterns"]
        
        # Find the added pattern
        added_pattern = next(
            (p for p in patterns if p["pattern"] == pattern and p["confidence"] == confidence),
            None
        )
        
        assert added_pattern is not None
        assert added_pattern["specificity"] == specificity
    
    @given(
        confidence_threshold=st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(deadline=None, max_examples=10)
    def test_property_configuration_validation_and_reload(self, confidence_threshold):
        """
        Feature: transaction-categorization, Property 33: Configuration Validation and Reload
        For any valid configuration change, validation should pass and reload should work.
        """
        # Create valid configuration with random threshold
        config = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": confidence_threshold,
            "categories": {}
        }
        
        # Validation should pass
        result = self.storage.validate_config(config)
        assert result["valid"] is True
        
        # Save and reload should work
        self.storage.save_categories(config)
        reloaded_config = self.storage.load_categories()
        
        assert reloaded_config["confidence_threshold"] == confidence_threshold
    
    @given(
        invalid_confidence=st.one_of(
            st.floats(min_value=-10.0, max_value=-0.1),
            st.floats(min_value=1.1, max_value=10.0),
            st.just(float('inf')),
            st.just(float('-inf')),
            st.just(float('nan'))
        )
    )
    @settings(deadline=None, max_examples=10)
    def test_property_invalid_confidence_rejection(self, invalid_confidence):
        """
        Property: Invalid confidence scores should be rejected during validation.
        """
        config = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": invalid_confidence,
            "categories": {}
        }
        
        result = self.storage.validate_config(config)
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    @given(
        category_names=st.lists(
            st.text(alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd']), min_size=1, max_size=10).filter(lambda x: x.strip()),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    @settings(deadline=None, max_examples=10)
    def test_property_multiple_categories_organization(self, category_names):
        """
        Property: Multiple categories should be organized clearly in storage.
        """
        # Add patterns for each category
        for category in category_names:
            self.storage.add_pattern_rule(category, f"PATTERN_{category}", 0.8, "medium")
        
        # Load and verify organization
        config = self.storage.load_categories()
        
        for category in category_names:
            assert category in config["categories"]
            assert "patterns" in config["categories"][category]
            assert len(config["categories"][category]["patterns"]) > 0
    
    def test_property_backup_preserves_data_integrity(self):
        """
        Property: Configuration backups should preserve complete data integrity.
        """
        # Create complex configuration
        original_config = self.storage.get_default_categories()
        self.storage.save_categories(original_config)
        
        # Create backup
        backup_path = self.storage.backup_config()
        
        # Load backup and compare
        with open(backup_path, 'r') as f:
            backup_config = yaml.safe_load(f)
        
        # Should be identical to original
        assert backup_config == original_config
    
    @given(
        pattern_type=st.sampled_from(["exact", "substring", "regex"])
    )
    @settings(deadline=None, max_examples=10)
    def test_property_pattern_type_validation(self, pattern_type):
        """
        Property: Valid pattern types should be accepted, invalid ones rejected.
        """
        valid_config = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": 0.7,
            "categories": {
                "TestCategory": {
                    "patterns": [
                        {
                            "pattern": "TEST",
                            "confidence": 0.8,
                            "type": pattern_type,
                            "specificity": "medium"
                        }
                    ]
                }
            }
        }
        
        result = self.storage.validate_config(valid_config)
        assert result["valid"] is True
        
        # Test invalid type
        valid_config["categories"]["TestCategory"]["patterns"][0]["type"] = "invalid_type"
        result = self.storage.validate_config(valid_config)
        assert result["valid"] is False