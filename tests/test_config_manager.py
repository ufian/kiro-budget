"""Tests for configuration management."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from kiro_budget.utils.config_manager import ConfigManager
from kiro_budget.models.core import ParserConfig, InstitutionConfig


class TestConfigManager(unittest.TestCase):
    """Test cases for ConfigManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.json')
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_default_config_loading(self):
        """Test loading default configuration when no file exists"""
        manager = ConfigManager(config_path="nonexistent_file.json")
        config = manager.load_config()
        
        self.assertIsInstance(config, ParserConfig)
        self.assertEqual(config.raw_directory, "raw")
        self.assertEqual(config.data_directory, "data")
        self.assertTrue(config.skip_processed)
        self.assertFalse(config.force_reprocess)
    
    def test_config_file_loading(self):
        """Test loading configuration from JSON file"""
        test_config = {
            "raw_directory": "test_raw",
            "data_directory": "test_data",
            "skip_processed": False,
            "force_reprocess": True,
            "date_formats": ["%Y-%m-%d", "%m/%d/%Y"],
            "institution_mappings": {
                "chase": "Chase Bank"
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        manager = ConfigManager(config_path=self.config_file)
        config = manager.load_config()
        
        self.assertEqual(config.raw_directory, "test_raw")
        self.assertEqual(config.data_directory, "test_data")
        self.assertFalse(config.skip_processed)
        self.assertTrue(config.force_reprocess)
        self.assertEqual(config.date_formats, ["%Y-%m-%d", "%m/%d/%Y"])
        self.assertEqual(config.institution_mappings["chase"], "Chase Bank")
    
    def test_institution_config_loading(self):
        """Test loading institution-specific configurations"""
        test_config = {
            "institutions": {
                "chase": {
                    "parser_type": "qfx",
                    "column_mappings": {
                        "date": "Date",
                        "amount": "Amount"
                    },
                    "date_format": "%m/%d/%Y",
                    "amount_format": "decimal",
                    "account_extraction_pattern": r"statements-(\d{4})-"
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        manager = ConfigManager(config_path=self.config_file)
        manager.load_config()
        
        chase_config = manager.get_institution_config("chase")
        self.assertIsNotNone(chase_config)
        self.assertEqual(chase_config.name, "chase")
        self.assertEqual(chase_config.parser_type, "qfx")
        self.assertEqual(chase_config.date_format, "%m/%d/%Y")
    
    def test_config_validation(self):
        """Test configuration validation"""
        # Test invalid configuration
        invalid_config = {
            "raw_directory": "",  # Empty directory
            "skip_processed": "not_a_boolean",  # Wrong type
            "date_formats": "not_a_list"  # Wrong type
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(invalid_config, f)
        
        manager = ConfigManager(config_path=self.config_file)
        # Should fall back to defaults on validation error
        config = manager.load_config()
        
        # Should use defaults due to validation failure
        self.assertEqual(config.raw_directory, "raw")
        self.assertTrue(config.skip_processed)
        self.assertIsInstance(config.date_formats, list)
    
    def test_config_template_generation(self):
        """Test configuration template generation"""
        template_file = os.path.join(self.temp_dir, 'template.json')
        
        manager = ConfigManager()
        manager.save_config_template(template_file)
        
        self.assertTrue(os.path.exists(template_file))
        
        # Load and verify template
        with open(template_file, 'r') as f:
            template = json.load(f)
        
        self.assertIn('raw_directory', template)
        self.assertIn('data_directory', template)
        self.assertIn('institutions', template)
        self.assertIn('chase', template['institutions'])
    
    def test_config_caching(self):
        """Test configuration caching"""
        test_config = {"raw_directory": "cached_test"}
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        manager = ConfigManager(config_path=self.config_file)
        
        # First load
        config1 = manager.load_config()
        self.assertEqual(config1.raw_directory, "cached_test")
        
        # Modify file
        test_config["raw_directory"] = "modified_test"
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        # Second load (should use cache)
        config2 = manager.load_config()
        self.assertEqual(config2.raw_directory, "cached_test")  # Still cached
        
        # Force reload
        config3 = manager.load_config(force_reload=True)
        self.assertEqual(config3.raw_directory, "modified_test")  # Now updated


if __name__ == '__main__':
    unittest.main()