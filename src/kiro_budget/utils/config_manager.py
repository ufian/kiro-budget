"""Configuration management for the financial data parser."""

import json
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from ..models.core import ParserConfig, InstitutionConfig


logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages loading and validation of parser configuration"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager
        
        Args:
            config_path: Path to configuration file. If None, searches for default locations.
        """
        self.config_path = config_path
        self._config_cache: Optional[ParserConfig] = None
        self._institution_configs: Dict[str, InstitutionConfig] = {}
        
    def load_config(self, force_reload: bool = False) -> ParserConfig:
        """Load parser configuration from file or return default
        
        Args:
            force_reload: Force reload from file even if cached
            
        Returns:
            ParserConfig instance with loaded or default configuration
        """
        if self._config_cache is not None and not force_reload:
            return self._config_cache
            
        config_data = self._load_config_file()
        
        # Create ParserConfig with loaded data or defaults
        try:
            self._config_cache = ParserConfig(
                raw_directory=config_data.get('raw_directory', 'raw'),
                data_directory=config_data.get('data_directory', 'data'),
                skip_processed=config_data.get('skip_processed', True),
                force_reprocess=config_data.get('force_reprocess', False),
                date_formats=config_data.get('date_formats'),
                institution_mappings=config_data.get('institution_mappings'),
                column_mappings=config_data.get('column_mappings'),
                plugin_directories=config_data.get('plugin_directories')
            )
            
            # Load institution-specific configurations
            self._load_institution_configs(config_data.get('institutions', {}))
            
            logger.info(f"Configuration loaded successfully from {self.config_path or 'defaults'}")
            return self._config_cache
            
        except Exception as e:
            logger.warning(f"Error loading configuration: {e}. Using defaults.")
            self._config_cache = ParserConfig()
            return self._config_cache
    
    def _load_config_file(self) -> Dict[str, Any]:
        """Load configuration from file
        
        Returns:
            Dictionary with configuration data or empty dict if no file found
        """
        config_file = self._find_config_file()
        
        if not config_file or not os.path.exists(config_file):
            logger.info("No configuration file found, using defaults")
            return {}
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.endswith('.json'):
                    data = json.load(f)
                elif config_file.endswith(('.yml', '.yaml')):
                    data = yaml.safe_load(f)
                else:
                    logger.warning(f"Unsupported config file format: {config_file}")
                    return {}
                    
            self._validate_config_data(data)
            logger.info(f"Configuration loaded from {config_file}")
            return data
            
        except Exception as e:
            logger.error(f"Error reading configuration file {config_file}: {e}")
            return {}
    
    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations
        
        Returns:
            Path to configuration file or None if not found
        """
        if self.config_path:
            return self.config_path
            
        # Search in standard locations
        search_paths = [
            'parser_config.json',
            'parser_config.yml',
            'parser_config.yaml',
            'config/parser_config.json',
            'config/parser_config.yml',
            'config/parser_config.yaml',
            os.path.expanduser('~/.kiro_budget/config.json'),
            os.path.expanduser('~/.kiro_budget/config.yml'),
            '/etc/kiro_budget/config.json',
            '/etc/kiro_budget/config.yml'
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                return path
                
        return None
    
    def _validate_config_data(self, data: Dict[str, Any]) -> None:
        """Validate configuration data structure
        
        Args:
            data: Configuration data to validate
            
        Raises:
            ValueError: If configuration data is invalid
        """
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a dictionary")
            
        # Validate directory paths
        for dir_key in ['raw_directory', 'data_directory']:
            if dir_key in data:
                if not isinstance(data[dir_key], str):
                    raise ValueError(f"{dir_key} must be a string")
                if not data[dir_key].strip():
                    raise ValueError(f"{dir_key} cannot be empty")
        
        # Validate boolean fields
        for bool_key in ['skip_processed', 'force_reprocess']:
            if bool_key in data and not isinstance(data[bool_key], bool):
                raise ValueError(f"{bool_key} must be a boolean")
        
        # Validate date formats
        if 'date_formats' in data:
            if not isinstance(data['date_formats'], list):
                raise ValueError("date_formats must be a list")
            for fmt in data['date_formats']:
                if not isinstance(fmt, str):
                    raise ValueError("All date formats must be strings")
        
        # Validate mappings
        for mapping_key in ['institution_mappings', 'column_mappings']:
            if mapping_key in data:
                if not isinstance(data[mapping_key], dict):
                    raise ValueError(f"{mapping_key} must be a dictionary")
        
        # Validate plugin directories
        if 'plugin_directories' in data:
            if not isinstance(data['plugin_directories'], list):
                raise ValueError("plugin_directories must be a list")
            for path in data['plugin_directories']:
                if not isinstance(path, str):
                    raise ValueError("All plugin directory paths must be strings")
        
        # Validate institutions configuration
        if 'institutions' in data:
            if not isinstance(data['institutions'], dict):
                raise ValueError("institutions must be a dictionary")
            self._validate_institution_configs(data['institutions'])
    
    def _validate_institution_configs(self, institutions: Dict[str, Any]) -> None:
        """Validate institution-specific configurations
        
        Args:
            institutions: Dictionary of institution configurations
            
        Raises:
            ValueError: If institution configuration is invalid
        """
        for inst_name, inst_config in institutions.items():
            if not isinstance(inst_config, dict):
                raise ValueError(f"Institution config for {inst_name} must be a dictionary")
            
            required_fields = ['parser_type', 'column_mappings', 'date_format', 'amount_format']
            for field in required_fields:
                if field not in inst_config:
                    raise ValueError(f"Institution {inst_name} missing required field: {field}")
            
            # Validate parser_type
            valid_parser_types = ['qfx', 'csv', 'pdf']
            if inst_config['parser_type'] not in valid_parser_types:
                raise ValueError(f"Invalid parser_type for {inst_name}: {inst_config['parser_type']}")
            
            # Validate column_mappings
            if not isinstance(inst_config['column_mappings'], dict):
                raise ValueError(f"column_mappings for {inst_name} must be a dictionary")
            
            # Validate date_format and amount_format are strings
            for fmt_field in ['date_format', 'amount_format']:
                if not isinstance(inst_config[fmt_field], str):
                    raise ValueError(f"{fmt_field} for {inst_name} must be a string")
    
    def _load_institution_configs(self, institutions_data: Dict[str, Any]) -> None:
        """Load institution-specific configurations
        
        Args:
            institutions_data: Dictionary of institution configuration data
        """
        self._institution_configs.clear()
        
        for inst_name, inst_data in institutions_data.items():
            try:
                config = InstitutionConfig(
                    name=inst_name,
                    parser_type=inst_data['parser_type'],
                    column_mappings=inst_data['column_mappings'],
                    date_format=inst_data['date_format'],
                    amount_format=inst_data['amount_format'],
                    account_extraction_pattern=inst_data.get('account_extraction_pattern', ''),
                    custom_rules=inst_data.get('custom_rules')
                )
                self._institution_configs[inst_name] = config
                logger.debug(f"Loaded configuration for institution: {inst_name}")
                
            except Exception as e:
                logger.error(f"Error loading configuration for institution {inst_name}: {e}")
    
    def get_institution_config(self, institution_name: str) -> Optional[InstitutionConfig]:
        """Get configuration for a specific institution
        
        Args:
            institution_name: Name of the institution
            
        Returns:
            InstitutionConfig if found, None otherwise
        """
        return self._institution_configs.get(institution_name.lower())
    
    def get_all_institution_configs(self) -> Dict[str, InstitutionConfig]:
        """Get all institution configurations
        
        Returns:
            Dictionary mapping institution names to their configurations
        """
        return self._institution_configs.copy()
    
    def save_config_template(self, output_path: str) -> None:
        """Generate and save a configuration file template
        
        Args:
            output_path: Path where to save the template
        """
        template = {
            "raw_directory": "raw",
            "data_directory": "data",
            "skip_processed": True,
            "force_reprocess": False,
            "date_formats": [
                "%m/%d/%Y",
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%y",
                "%d/%m/%y",
                "%y-%m-%d"
            ],
            "institution_mappings": {
                "chase": "Chase Bank",
                "bofa": "Bank of America",
                "wells": "Wells Fargo",
                "citi": "Citibank"
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
                },
                "bank_of_america": {
                    "parser_type": "csv",
                    "column_mappings": {
                        "date": "Posted Date",
                        "amount": "Amount",
                        "description": "Payee",
                        "account": "Account"
                    },
                    "date_format": "%m/%d/%Y",
                    "amount_format": "decimal",
                    "account_extraction_pattern": r"account_(\d+)",
                    "custom_rules": {}
                }
            }
        }
        
        try:
            # Create directory if it doesn't exist (only if output_path has a directory component)
            output_dir = os.path.dirname(output_path)
            if output_dir:  # Only create directory if there's a directory component
                os.makedirs(output_dir, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                if output_path.endswith('.json'):
                    json.dump(template, f, indent=2)
                elif output_path.endswith(('.yml', '.yaml')):
                    yaml.dump(template, f, default_flow_style=False, indent=2)
                else:
                    # Default to JSON
                    json.dump(template, f, indent=2)
            
            logger.info(f"Configuration template saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving configuration template: {e}")
            raise
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values
        
        Args:
            updates: Dictionary of configuration updates
        """
        if self._config_cache is None:
            self.load_config()
        
        # Apply updates to cached config
        for key, value in updates.items():
            if hasattr(self._config_cache, key):
                setattr(self._config_cache, key, value)
                logger.debug(f"Updated configuration: {key} = {value}")
            else:
                logger.warning(f"Unknown configuration key: {key}")
    
    def reset_config(self) -> None:
        """Reset configuration cache, forcing reload on next access"""
        self._config_cache = None
        self._institution_configs.clear()
        logger.debug("Configuration cache reset")


def get_default_config_manager() -> ConfigManager:
    """Get a default configuration manager instance
    
    Returns:
        ConfigManager instance with default settings
    """
    return ConfigManager()