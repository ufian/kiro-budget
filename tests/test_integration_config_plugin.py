"""Integration tests for configuration and plugin systems."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from kiro_budget.utils.config_manager import ConfigManager
from kiro_budget.utils.plugin_manager import PluginManager
from kiro_budget.utils.file_scanner import ParserFactory
from kiro_budget.models.core import ParserConfig


class TestConfigPluginIntegration(unittest.TestCase):
    """Test integration between configuration and plugin systems"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.json')
        self.plugin_dir = os.path.join(self.temp_dir, 'plugins')
        os.makedirs(self.plugin_dir)
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_with_plugin_directories(self):
        """Test configuration loading with plugin directories"""
        test_config = {
            "raw_directory": "test_raw",
            "data_directory": "test_data",
            "plugin_directories": [self.plugin_dir],
            "institutions": {
                "test_bank": {
                    "parser_type": "csv",
                    "column_mappings": {
                        "date": "Date",
                        "amount": "Amount"
                    },
                    "date_format": "%m/%d/%Y",
                    "amount_format": "decimal",
                    "account_extraction_pattern": r"account_(\d+)"
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        # Load configuration
        config_manager = ConfigManager(config_path=self.config_file)
        config = config_manager.load_config()
        
        # Verify configuration
        self.assertEqual(config.raw_directory, "test_raw")
        self.assertEqual(config.plugin_directories, [self.plugin_dir])
        
        # Verify institution config
        test_bank_config = config_manager.get_institution_config("test_bank")
        self.assertIsNotNone(test_bank_config)
        self.assertEqual(test_bank_config.parser_type, "csv")
    
    def test_parser_factory_with_config_and_plugins(self):
        """Test ParserFactory integration with configuration and plugins"""
        test_config = {
            "plugin_directories": [self.plugin_dir]
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        # Load configuration
        config_manager = ConfigManager(config_path=self.config_file)
        config = config_manager.load_config()
        
        # Create parser factory (which initializes plugin manager)
        factory = ParserFactory(config)
        
        # Verify built-in parsers are available
        supported_formats = factory.get_supported_formats()
        self.assertIn('qfx', supported_formats)
        self.assertIn('csv', supported_formats)
        self.assertIn('pdf', supported_formats)
        
        # Test parser creation
        csv_parser = factory.get_parser_by_format('csv')
        self.assertIsNotNone(csv_parser)
        
        # Test file parsing capability
        self.assertTrue(factory.can_parse_file('test.csv'))
        self.assertTrue(factory.can_parse_file('test.qfx'))
        self.assertFalse(factory.can_parse_file('test.unknown'))
    
    def test_plugin_info_retrieval(self):
        """Test retrieving plugin information through ParserFactory"""
        config = ParserConfig(plugin_directories=[self.plugin_dir])
        factory = ParserFactory(config)
        
        plugin_info = factory.get_plugin_info()
        
        self.assertIn('available_plugins', plugin_info)
        self.assertIn('available_parsers', plugin_info)
        self.assertIn('plugin_details', plugin_info)
        
        # Should have built-in parsers
        self.assertIn('qfx', plugin_info['available_parsers'])
        self.assertIn('csv', plugin_info['available_parsers'])
        self.assertIn('pdf', plugin_info['available_parsers'])
    
    def test_config_template_with_plugin_structure(self):
        """Test configuration template includes plugin structure"""
        config_manager = ConfigManager()
        template_file = os.path.join(self.temp_dir, 'template.json')
        
        config_manager.save_config_template(template_file)
        
        # Load and verify template
        with open(template_file, 'r') as f:
            template = json.load(f)
        
        # Should include plugin directories
        self.assertIn('plugin_directories', template)
        self.assertIsInstance(template['plugin_directories'], list)
        
        # Should include institution configurations
        self.assertIn('institutions', template)
        self.assertIn('chase', template['institutions'])
        
        # Institution config should have required fields
        chase_config = template['institutions']['chase']
        self.assertIn('parser_type', chase_config)
        self.assertIn('column_mappings', chase_config)
        self.assertIn('date_format', chase_config)
        self.assertIn('custom_rules', chase_config)


if __name__ == '__main__':
    unittest.main()