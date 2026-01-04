"""
Tests for the categorization configuration manager.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from kiro_budget.categorizers.config_manager import CategorizationConfigManager


class TestCategorizationConfigManager:
    """Test cases for CategorizationConfigManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_categories.yaml")
        
        # Create test configuration manager
        self.config_manager = CategorizationConfigManager(self.config_path)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test configuration manager initialization."""
        assert self.config_manager.config_path == Path(self.config_path)
        assert self.config_manager.storage is not None
        
        # Check default configuration is loaded
        ai_config = self.config_manager.get_ai_config()
        assert ai_config['enabled'] is True
        assert ai_config['primary_service'] == 'openai'
        
        ml_config = self.config_manager.get_ml_config()
        assert ml_config['enabled'] is True
        assert ml_config['model_type'] == 'random_forest'
    
    def test_update_ai_config(self):
        """Test updating AI configuration."""
        updates = {
            'enabled': False,
            'primary_service': 'claude',
            'max_cost_per_month': 100.0
        }
        
        self.config_manager.update_ai_config(updates)
        
        ai_config = self.config_manager.get_ai_config()
        assert ai_config['enabled'] is False
        assert ai_config['primary_service'] == 'claude'
        assert ai_config['max_cost_per_month'] == 100.0
    
    def test_update_ai_config_validation(self):
        """Test AI configuration validation."""
        # Test invalid service
        with pytest.raises(ValueError, match="Invalid AI service"):
            self.config_manager.update_ai_config({'primary_service': 'invalid'})
        
        # Test invalid enabled type
        with pytest.raises(ValueError, match="must be a boolean"):
            self.config_manager.update_ai_config({'enabled': 'yes'})
        
        # Test invalid cost type
        with pytest.raises(ValueError, match="must be a number"):
            self.config_manager.update_ai_config({'max_cost_per_month': 'fifty'})
    
    def test_update_ml_config(self):
        """Test updating ML configuration."""
        updates = {
            'enabled': False,
            'model_type': 'xgboost',
            'confidence_threshold': 0.8,
            'retrain_threshold': 200
        }
        
        self.config_manager.update_ml_config(updates)
        
        ml_config = self.config_manager.get_ml_config()
        assert ml_config['enabled'] is False
        assert ml_config['model_type'] == 'xgboost'
        assert ml_config['confidence_threshold'] == 0.8
        assert ml_config['retrain_threshold'] == 200
    
    def test_update_ml_config_validation(self):
        """Test ML configuration validation."""
        # Test invalid model type
        with pytest.raises(ValueError, match="Invalid ML model type"):
            self.config_manager.update_ml_config({'model_type': 'invalid'})
        
        # Test invalid confidence threshold
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            self.config_manager.update_ml_config({'confidence_threshold': 1.5})
        
        # Test invalid retrain threshold
        with pytest.raises(ValueError, match="must be an integer"):
            self.config_manager.update_ml_config({'retrain_threshold': 'many'})
    
    def test_api_key_management(self):
        """Test API key setting and retrieval."""
        # Test setting API key
        self.config_manager.set_api_key('openai', 'test-key-123', persist=False)
        
        # Test retrieving API key
        api_key = self.config_manager.get_api_key('openai')
        assert api_key == 'test-key-123'
        
        # Test unsupported service
        with pytest.raises(ValueError, match="Unsupported service"):
            self.config_manager.set_api_key('invalid', 'key')
    
    def test_export_category_rules(self):
        """Test exporting category rules."""
        export_path = os.path.join(self.temp_dir, "exported_rules.yaml")
        
        self.config_manager.export_category_rules(export_path, 'yaml')
        
        assert os.path.exists(export_path)
        
        # Verify export content
        import yaml
        with open(export_path, 'r') as f:
            exported_data = yaml.safe_load(f)
        
        assert 'export_metadata' in exported_data
        assert 'categories' in exported_data
        assert 'general_config' in exported_data
    
    def test_import_category_rules(self):
        """Test importing category rules."""
        # Create test import file
        import_data = {
            'categories': {
                'TestCategory': {
                    'patterns': [
                        {
                            'pattern': 'TEST_MERCHANT',
                            'confidence': 0.9,
                            'type': 'substring',
                            'specificity': 'high'
                        }
                    ]
                }
            },
            'general_config': {
                'default_category': 'TestDefault',
                'confidence_threshold': 0.8
            }
        }
        
        import_path = os.path.join(self.temp_dir, "import_rules.yaml")
        import yaml
        with open(import_path, 'w') as f:
            yaml.dump(import_data, f)
        
        # Import rules
        stats = self.config_manager.import_category_rules(import_path, 'merge')
        
        assert stats['categories_imported'] >= 1
        assert stats['patterns_imported'] >= 1
        
        # Verify import
        config = self.config_manager.storage.load_categories()
        assert 'TestCategory' in config['categories']
    
    def test_configuration_summary(self):
        """Test getting configuration summary."""
        summary = self.config_manager.get_configuration_summary()
        
        assert 'general' in summary
        assert 'ai' in summary
        assert 'ml' in summary
        
        # Check general section
        general = summary['general']
        assert 'version' in general
        assert 'total_categories' in general
        assert 'total_patterns' in general
        
        # Check AI section
        ai = summary['ai']
        assert 'enabled' in ai
        assert 'primary_service' in ai
        
        # Check ML section
        ml = summary['ml']
        assert 'enabled' in ml
        assert 'model_type' in ml
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        validation = self.config_manager.validate_configuration()
        
        assert 'valid' in validation
        assert 'issues' in validation
        assert 'warnings' in validation
        
        # Should be valid by default
        assert validation['valid'] is True
        assert len(validation['issues']) == 0
    
    def test_enable_disable_services(self):
        """Test enabling and disabling AI/ML services."""
        # Disable AI
        self.config_manager.enable_ai_categorization(False)
        ai_config = self.config_manager.get_ai_config()
        assert ai_config['enabled'] is False
        
        # Enable AI
        self.config_manager.enable_ai_categorization(True)
        ai_config = self.config_manager.get_ai_config()
        assert ai_config['enabled'] is True
        
        # Disable ML
        self.config_manager.enable_ml_categorization(False)
        ml_config = self.config_manager.get_ml_config()
        assert ml_config['enabled'] is False
        
        # Enable ML
        self.config_manager.enable_ml_categorization(True)
        ml_config = self.config_manager.get_ml_config()
        assert ml_config['enabled'] is True
    
    def test_backup_and_restore(self):
        """Test configuration backup and restore."""
        # Get initial AI config state
        initial_ai_config = self.config_manager.get_ai_config()
        initial_enabled = initial_ai_config['enabled']
        
        # Create backup
        backup_path = self.config_manager.create_backup()
        assert os.path.exists(backup_path)
        
        # Modify configuration
        self.config_manager.update_ai_config({'enabled': not initial_enabled})
        
        # Verify modification
        modified_ai_config = self.config_manager.get_ai_config()
        assert modified_ai_config['enabled'] == (not initial_enabled)
        
        # Restore backup
        self.config_manager.restore_backup(backup_path)
        
        # Reload configuration after restore
        self.config_manager._load_configuration()
        
        # Verify restoration
        ai_config = self.config_manager.get_ai_config()
        assert ai_config['enabled'] == initial_enabled
    
    def test_list_backups(self):
        """Test listing available backups."""
        # Create a backup
        self.config_manager.create_backup()
        
        # List backups
        backups = self.config_manager.list_backups()
        
        assert len(backups) >= 1
        assert 'filename' in backups[0]
        assert 'created_at' in backups[0]
        assert 'size_bytes' in backups[0]
    
    def test_reset_to_defaults(self):
        """Test resetting configuration to defaults."""
        # Modify configuration
        self.config_manager.update_ai_config({'enabled': False})
        self.config_manager.update_ml_config({'model_type': 'xgboost'})
        
        # Reset to defaults
        self.config_manager.reset_to_defaults()
        
        # Verify reset
        ai_config = self.config_manager.get_ai_config()
        ml_config = self.config_manager.get_ml_config()
        
        assert ai_config['enabled'] is True
        assert ml_config['model_type'] == 'random_forest'
    
    def test_invalid_import_file(self):
        """Test importing from invalid file."""
        # Test non-existent file
        with pytest.raises(FileNotFoundError):
            self.config_manager.import_category_rules('nonexistent.yaml', 'merge')
        
        # Test invalid format
        invalid_path = os.path.join(self.temp_dir, "invalid.yaml")
        with open(invalid_path, 'w') as f:
            f.write("invalid: yaml: content:")
        
        with pytest.raises(ValueError, match="Failed to parse import file"):
            self.config_manager.import_category_rules(invalid_path, 'merge')
    
    def test_merge_modes(self):
        """Test different merge modes for importing."""
        # Create existing category with full configuration
        existing_data = {
            'version': '1.0',
            'default_category': 'Uncategorized',
            'confidence_threshold': 0.7,
            'categories': {
                'ExistingCategory': {
                    'patterns': [
                        {
                            'pattern': 'EXISTING',
                            'confidence': 0.8,
                            'type': 'substring',
                            'specificity': 'medium'
                        }
                    ]
                }
            },
            'ai_config': {
                'enabled': True,
                'primary_service': 'openai'
            },
            'ml_config': {
                'enabled': True,
                'model_type': 'random_forest'
            }
        }
        
        # Save existing data
        self.config_manager.storage.save_categories(existing_data)
        
        # Create import data with same category
        import_data = {
            'categories': {
                'ExistingCategory': {
                    'patterns': [
                        {
                            'pattern': 'NEW_PATTERN',
                            'confidence': 0.9,
                            'type': 'substring',
                            'specificity': 'high'
                        }
                    ]
                }
            },
            'general_config': {
                'default_category': 'TestDefault',
                'confidence_threshold': 0.8
            }
        }
        
        import_path = os.path.join(self.temp_dir, "merge_test.yaml")
        import yaml
        with open(import_path, 'w') as f:
            yaml.dump(import_data, f)
        
        # Test skip mode
        stats = self.config_manager.import_category_rules(import_path, 'skip')
        assert stats['categories_skipped'] >= 1
        
        # Test replace mode
        stats = self.config_manager.import_category_rules(import_path, 'replace')
        assert stats['categories_replaced'] >= 1
        
        # Test merge mode
        stats = self.config_manager.import_category_rules(import_path, 'merge')
        # Should merge patterns from both sources