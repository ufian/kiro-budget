#!/usr/bin/env python3
"""
Demonstration of the configuration and plugin system.

This script shows how to:
1. Load configuration from files
2. Use the plugin system
3. Create custom parsers via plugins
4. Integrate everything with the ParserFactory
"""

import json
import os
import tempfile
from pathlib import Path

# Add the src directory to the path so we can import kiro_budget
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from kiro_budget.utils.config_manager import ConfigManager
from kiro_budget.utils.plugin_manager import PluginManager, SimpleParserPlugin
from kiro_budget.utils.file_scanner import ParserFactory
from kiro_budget.models.core import ParserConfig
from kiro_budget.parsers.csv_parser import CSVParser


def create_sample_config():
    """Create a sample configuration file"""
    config = {
        "raw_directory": "raw",
        "data_directory": "data",
        "skip_processed": True,
        "force_reprocess": False,
        "date_formats": [
            "%m/%d/%Y",
            "%Y-%m-%d",
            "%d/%m/%Y"
        ],
        "institution_mappings": {
            "chase": "Chase Bank",
            "bofa": "Bank of America",
            "wells": "Wells Fargo"
        },
        "column_mappings": {
            "chase": {
                "date": ["Date", "Transaction Date"],
                "amount": ["Amount", "Debit", "Credit"],
                "description": ["Description", "Memo"]
            }
        },
        "plugin_directories": [
            "plugins",
            "~/.kiro_budget/plugins"
        ],
        "institutions": {
            "chase": {
                "parser_type": "qfx",
                "column_mappings": {
                    "date": "Date",
                    "amount": "Amount",
                    "description": "Description",
                    "account": "Account"
                },
                "date_format": "%m/%d/%Y",
                "amount_format": "decimal",
                "account_extraction_pattern": r"statements-(\d{4})-",
                "custom_rules": {
                    "skip_pending": True,
                    "merge_transfers": False
                }
            }
        }
    }
    return config


def demo_config_manager():
    """Demonstrate configuration management"""
    print("=== Configuration Manager Demo ===")
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_data = create_sample_config()
        json.dump(config_data, f, indent=2)
        config_file = f.name
    
    try:
        # Load configuration
        config_manager = ConfigManager(config_path=config_file)
        config = config_manager.load_config()
        
        print(f"Raw directory: {config.raw_directory}")
        print(f"Data directory: {config.data_directory}")
        print(f"Date formats: {config.date_formats}")
        print(f"Institution mappings: {config.institution_mappings}")
        
        # Get institution-specific config
        chase_config = config_manager.get_institution_config("chase")
        if chase_config:
            print(f"Chase parser type: {chase_config.parser_type}")
            print(f"Chase date format: {chase_config.date_format}")
            print(f"Chase custom rules: {chase_config.custom_rules}")
        
        print("✓ Configuration loaded successfully\n")
        
    finally:
        os.unlink(config_file)


def demo_plugin_manager():
    """Demonstrate plugin management"""
    print("=== Plugin Manager Demo ===")
    
    # Create configuration with plugin directories
    config = ParserConfig(plugin_directories=["plugins"])
    
    # Initialize plugin manager
    plugin_manager = PluginManager(config)
    
    print(f"Available parsers: {plugin_manager.get_available_parsers()}")
    print(f"Available plugins: {plugin_manager.get_available_plugins()}")
    
    # Create a custom plugin
    custom_plugin = SimpleParserPlugin(
        name="custom_chase_csv",
        parser_class=CSVParser,
        institutions=["chase", "jpmorgan_chase"],
        extensions=[".csv"],
        priority=5
    )
    
    # Register the plugin
    plugin_manager.register_plugin(custom_plugin)
    
    print(f"After adding custom plugin:")
    print(f"Available parsers: {plugin_manager.get_available_parsers()}")
    print(f"Available plugins: {plugin_manager.get_available_plugins()}")
    
    # Get plugin info
    plugin_info = plugin_manager.get_plugin_info("custom_chase_csv")
    if plugin_info:
        print(f"Custom plugin info: {plugin_info}")
    
    # Test parser selection
    parser = plugin_manager.get_parser_for_file("chase_account.csv", "chase")
    if parser:
        print(f"Selected parser for chase CSV: {type(parser).__name__}")
    
    print("✓ Plugin system working correctly\n")


def demo_parser_factory_integration():
    """Demonstrate ParserFactory integration with config and plugins"""
    print("=== ParserFactory Integration Demo ===")
    
    # Create configuration
    config = ParserConfig(
        raw_directory="raw",
        data_directory="data",
        plugin_directories=["plugins"]
    )
    
    # Create parser factory (automatically initializes plugin manager)
    factory = ParserFactory(config)
    
    print(f"Supported formats: {factory.get_supported_formats()}")
    
    # Test parser selection for different files
    test_files = [
        ("chase_account.qfx", "chase"),
        ("bofa_statement.csv", "bank_of_america"),
        ("wells_statement.pdf", "wells_fargo"),
        ("unknown_file.txt", None)
    ]
    
    for file_path, institution in test_files:
        parser = factory.get_parser_for_file(file_path, institution)
        if parser:
            print(f"✓ {file_path} -> {type(parser).__name__}")
        else:
            print(f"✗ {file_path} -> No parser found")
    
    # Get plugin information
    plugin_info = factory.get_plugin_info()
    print(f"Plugin info: {plugin_info}")
    
    print("✓ ParserFactory integration working correctly\n")


def demo_config_template():
    """Demonstrate configuration template generation"""
    print("=== Configuration Template Demo ===")
    
    config_manager = ConfigManager()
    
    # Create temporary file for template
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        template_file = f.name
    
    try:
        # Generate template
        config_manager.save_config_template(template_file)
        
        # Read and display template
        with open(template_file, 'r') as f:
            template = json.load(f)
        
        print("Generated configuration template:")
        print(json.dumps(template, indent=2))
        print("✓ Configuration template generated successfully\n")
        
    finally:
        os.unlink(template_file)


def main():
    """Run all demonstrations"""
    print("Financial Data Parser - Configuration and Plugin System Demo")
    print("=" * 60)
    
    try:
        demo_config_manager()
        demo_plugin_manager()
        demo_parser_factory_integration()
        demo_config_template()
        
        print("🎉 All demonstrations completed successfully!")
        print("\nKey Features Demonstrated:")
        print("• Configuration loading from JSON/YAML files")
        print("• Institution-specific configuration support")
        print("• Plugin system for extensible parsers")
        print("• Parser selection based on file type and institution")
        print("• Integration between configuration and plugin systems")
        print("• Configuration template generation")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()