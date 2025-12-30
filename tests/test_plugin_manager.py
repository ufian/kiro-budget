"""Tests for plugin management."""

import os
import tempfile
import unittest
from typing import List, Type

from kiro_budget.utils.plugin_manager import PluginManager, ParserPlugin, SimpleParserPlugin
from kiro_budget.models.core import ParserConfig
from kiro_budget.parsers.base import FileParser
from kiro_budget.parsers.csv_parser import CSVParser


class MockParser(FileParser):
    """Mock parser for testing"""
    
    def parse(self, file_path: str):
        return []
    
    def get_supported_extensions(self):
        return ['.mock']
    
    def validate_file(self, file_path: str):
        return True


class MockPlugin(ParserPlugin):
    """Mock plugin for testing"""
    
    def get_name(self) -> str:
        return "mock_plugin"
    
    def get_parser_class(self) -> Type[FileParser]:
        return MockParser
    
    def get_supported_institutions(self) -> List[str]:
        return ["mock_bank"]
    
    def get_supported_extensions(self) -> List[str]:
        return [".mock"]
    
    def get_priority(self) -> int:
        return 5


class TestPluginManager(unittest.TestCase):
    """Test cases for PluginManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = ParserConfig()
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_builtin_parsers_registration(self):
        """Test that built-in parsers are registered"""
        manager = PluginManager(self.config)
        
        available_parsers = manager.get_available_parsers()
        
        # Should have built-in parsers
        self.assertIn('qfx', available_parsers)
        self.assertIn('csv', available_parsers)
        self.assertIn('pdf', available_parsers)
    
    def test_plugin_registration(self):
        """Test manual plugin registration"""
        manager = PluginManager(self.config)
        plugin = MockPlugin()
        
        manager.register_plugin(plugin)
        
        # Check plugin is registered
        self.assertIn('mock_plugin', manager.get_available_plugins())
        self.assertIn('mock_plugin', manager.get_available_parsers())
        
        # Check plugin info
        info = manager.get_plugin_info('mock_plugin')
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], 'mock_plugin')
        self.assertEqual(info['supported_institutions'], ['mock_bank'])
        self.assertEqual(info['supported_extensions'], ['.mock'])
        self.assertEqual(info['priority'], 5)
    
    def test_parser_selection_by_file(self):
        """Test parser selection based on file path"""
        manager = PluginManager(self.config)
        plugin = MockPlugin()
        manager.register_plugin(plugin)
        
        # Test plugin parser selection
        parser = manager.get_parser_for_file('test.mock', 'mock_bank')
        self.assertIsInstance(parser, MockParser)
        
        # Test built-in parser selection
        parser = manager.get_parser_for_file('test.csv')
        self.assertIsInstance(parser, CSVParser)
        
        # Test no parser found
        parser = manager.get_parser_for_file('test.unknown')
        self.assertIsNone(parser)
    
    def test_parser_selection_by_type(self):
        """Test parser selection by type"""
        manager = PluginManager(self.config)
        plugin = MockPlugin()
        manager.register_plugin(plugin)
        
        # Test plugin parser
        parser = manager.get_parser_by_type('mock_plugin')
        self.assertIsInstance(parser, MockParser)
        
        # Test built-in parser
        parser = manager.get_parser_by_type('csv')
        self.assertIsInstance(parser, CSVParser)
        
        # Test unknown type
        parser = manager.get_parser_by_type('unknown')
        self.assertIsNone(parser)
    
    def test_plugin_priority(self):
        """Test plugin priority handling"""
        manager = PluginManager(self.config)
        
        # Register low priority plugin
        low_priority_plugin = SimpleParserPlugin(
            name="low_priority",
            parser_class=MockParser,
            institutions=["test_bank"],
            extensions=[".test"],
            priority=1
        )
        manager.register_plugin(low_priority_plugin)
        
        # Register high priority plugin
        high_priority_plugin = SimpleParserPlugin(
            name="high_priority",
            parser_class=MockParser,
            institutions=["test_bank"],
            extensions=[".test"],
            priority=10
        )
        manager.register_plugin(high_priority_plugin)
        
        # High priority plugin should be selected
        parser = manager.get_parser_for_file('test.test', 'test_bank')
        self.assertIsInstance(parser, MockParser)
        
        # Check that high priority plugin is used
        info = manager.get_plugin_info('high_priority')
        self.assertEqual(info['priority'], 10)
    
    def test_simple_parser_plugin(self):
        """Test SimpleParserPlugin functionality"""
        plugin = SimpleParserPlugin(
            name="simple_test",
            parser_class=CSVParser,
            institutions=["test_institution"],
            extensions=[".csv"],
            priority=3
        )
        
        self.assertEqual(plugin.get_name(), "simple_test")
        self.assertEqual(plugin.get_parser_class(), CSVParser)
        self.assertEqual(plugin.get_supported_institutions(), ["test_institution"])
        self.assertEqual(plugin.get_supported_extensions(), [".csv"])
        self.assertEqual(plugin.get_priority(), 3)
        
        # Test can_handle_file
        self.assertTrue(plugin.can_handle_file("test.csv", "test_institution"))
        self.assertFalse(plugin.can_handle_file("test.pdf", "test_institution"))
        self.assertFalse(plugin.can_handle_file("test.csv", "other_institution"))
    
    def test_plugin_file_handling(self):
        """Test plugin file handling logic"""
        plugin = MockPlugin()
        
        # Should handle .mock files for mock_bank
        self.assertTrue(plugin.can_handle_file("test.mock", "mock_bank"))
        
        # Should not handle other extensions
        self.assertFalse(plugin.can_handle_file("test.csv", "mock_bank"))
        
        # Should not handle other institutions
        self.assertFalse(plugin.can_handle_file("test.mock", "other_bank"))
        
        # Should handle .mock files without institution specified
        self.assertTrue(plugin.can_handle_file("test.mock"))


if __name__ == '__main__':
    unittest.main()