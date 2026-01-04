"""
Configuration management for the transaction categorization system.
Handles AI/ML settings, API keys, and category rule import/export.
"""

import os
import json
import yaml
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging

from .storage import CategoryStorage
from .models import CategoryDefinition, PatternRule


class CategorizationConfigManager:
    """
    Manages configuration for the transaction categorization system.
    Handles AI/ML settings, API keys, and category rule import/export.
    """
    
    def __init__(self, config_path: str = "categories.yaml"):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to the main categories configuration file
        """
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path)
        self.storage = CategoryStorage(str(config_path))
        
        # Configuration sections
        self._ai_config = {}
        self._ml_config = {}
        self._general_config = {}
        
        # Load current configuration
        self._load_configuration()
    
    def get_ai_config(self) -> Dict[str, Any]:
        """
        Get AI categorization configuration.
        
        Returns:
            Dictionary with AI configuration settings
        """
        return self._ai_config.copy()
    
    def get_ml_config(self) -> Dict[str, Any]:
        """
        Get ML categorization configuration.
        
        Returns:
            Dictionary with ML configuration settings
        """
        return self._ml_config.copy()
    
    def get_general_config(self) -> Dict[str, Any]:
        """
        Get general categorization configuration.
        
        Returns:
            Dictionary with general configuration settings
        """
        return self._general_config.copy()
    
    def update_ai_config(self, updates: Dict[str, Any]) -> None:
        """
        Update AI categorization configuration.
        
        Args:
            updates: Dictionary of configuration updates
        """
        # Validate AI configuration updates
        valid_keys = {
            'enabled', 'primary_service', 'fallback_service', 'cache_responses',
            'max_cost_per_month', 'api_timeout', 'retry_attempts', 'rate_limit_per_minute'
        }
        
        for key, value in updates.items():
            if key not in valid_keys:
                self.logger.warning(f"Unknown AI config key: {key}")
                continue
            
            # Validate specific settings
            if key == 'enabled' and not isinstance(value, bool):
                raise ValueError("AI 'enabled' must be a boolean")
            elif key in ['primary_service', 'fallback_service'] and value not in ['openai', 'claude', 'none']:
                raise ValueError(f"Invalid AI service: {value}")
            elif key == 'max_cost_per_month' and not isinstance(value, (int, float)):
                raise ValueError("max_cost_per_month must be a number")
            elif key in ['api_timeout', 'retry_attempts', 'rate_limit_per_minute'] and not isinstance(value, int):
                raise ValueError(f"{key} must be an integer")
            
            self._ai_config[key] = value
        
        self._save_configuration()
        self.logger.info(f"Updated AI configuration: {list(updates.keys())}")
    
    def update_ml_config(self, updates: Dict[str, Any]) -> None:
        """
        Update ML categorization configuration.
        
        Args:
            updates: Dictionary of configuration updates
        """
        # Validate ML configuration updates
        valid_keys = {
            'enabled', 'model_type', 'retrain_threshold', 'confidence_threshold',
            'model_path', 'feature_extraction', 'training_data_limit'
        }
        
        for key, value in updates.items():
            if key not in valid_keys:
                self.logger.warning(f"Unknown ML config key: {key}")
                continue
            
            # Validate specific settings
            if key == 'enabled' and not isinstance(value, bool):
                raise ValueError("ML 'enabled' must be a boolean")
            elif key == 'model_type' and value not in ['random_forest', 'xgboost', 'naive_bayes']:
                raise ValueError(f"Invalid ML model type: {value}")
            elif key in ['retrain_threshold', 'training_data_limit'] and not isinstance(value, int):
                raise ValueError(f"{key} must be an integer")
            elif key == 'confidence_threshold' and not (0.0 <= value <= 1.0):
                raise ValueError("confidence_threshold must be between 0.0 and 1.0")
            
            self._ml_config[key] = value
        
        self._save_configuration()
        self.logger.info(f"Updated ML configuration: {list(updates.keys())}")
    
    def update_general_config(self, updates: Dict[str, Any]) -> None:
        """
        Update general categorization configuration.
        
        Args:
            updates: Dictionary of configuration updates
        """
        # Validate general configuration updates
        valid_keys = {
            'confidence_threshold', 'default_category', 'version',
            'auto_learn_patterns', 'backup_retention_days'
        }
        
        for key, value in updates.items():
            if key not in valid_keys:
                self.logger.warning(f"Unknown general config key: {key}")
                continue
            
            # Validate specific settings
            if key == 'confidence_threshold' and not (0.0 <= value <= 1.0):
                raise ValueError("confidence_threshold must be between 0.0 and 1.0")
            elif key in ['default_category', 'version'] and not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            elif key == 'auto_learn_patterns' and not isinstance(value, bool):
                raise ValueError("auto_learn_patterns must be a boolean")
            elif key == 'backup_retention_days' and not isinstance(value, int):
                raise ValueError("backup_retention_days must be an integer")
            
            self._general_config[key] = value
        
        self._save_configuration()
        self.logger.info(f"Updated general configuration: {list(updates.keys())}")
    
    def set_api_key(self, service: str, api_key: str, persist: bool = True) -> None:
        """
        Set API key for external services.
        
        Args:
            service: Service name ('openai', 'claude', etc.)
            api_key: API key string
            persist: Whether to persist the key to environment or config
        """
        if service not in ['openai', 'claude']:
            raise ValueError(f"Unsupported service: {service}")
        
        # Set environment variable
        env_var = f"{service.upper()}_API_KEY"
        os.environ[env_var] = api_key
        
        if persist:
            # Store in AI config (encrypted or reference to env var)
            if 'api_keys' not in self._ai_config:
                self._ai_config['api_keys'] = {}
            
            # Store reference to environment variable for security
            self._ai_config['api_keys'][service] = f"${env_var}"
            self._save_configuration()
        
        self.logger.info(f"API key set for {service}")
    
    def get_api_key(self, service: str) -> Optional[str]:
        """
        Get API key for external services.
        
        Args:
            service: Service name ('openai', 'claude', etc.)
            
        Returns:
            API key string or None if not found
        """
        # Try environment variable first
        env_var = f"{service.upper()}_API_KEY"
        api_key = os.environ.get(env_var)
        
        if api_key:
            return api_key
        
        # Try configuration file
        api_keys = self._ai_config.get('api_keys', {})
        key_ref = api_keys.get(service)
        
        if key_ref and key_ref.startswith('$'):
            # Reference to environment variable
            env_name = key_ref[1:]  # Remove $ prefix
            return os.environ.get(env_name)
        
        return key_ref
    
    def export_category_rules(self, output_path: str, format: str = 'yaml') -> None:
        """
        Export category rules to a file.
        
        Args:
            output_path: Path to save the exported rules
            format: Export format ('yaml', 'json')
        """
        if format not in ['yaml', 'json']:
            raise ValueError("Format must be 'yaml' or 'json'")
        
        # Load current configuration
        config = self.storage.load_categories()
        
        # Create export data with metadata
        export_data = {
            'export_metadata': {
                'version': config.get('version', '1.0'),
                'exported_at': datetime.now().isoformat(),
                'exported_by': 'kiro-budget-categorization',
                'total_categories': len(config.get('categories', {})),
                'total_patterns': sum(
                    len(cat_data.get('patterns', []))
                    for cat_data in config.get('categories', {}).values()
                )
            },
            'categories': config.get('categories', {}),
            'general_config': {
                'default_category': config.get('default_category'),
                'confidence_threshold': config.get('confidence_threshold')
            }
        }
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Write export file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                if format == 'yaml':
                    yaml.dump(export_data, f, default_flow_style=False, 
                             sort_keys=False, allow_unicode=True, indent=2)
                else:  # json
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Category rules exported to {output_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to export category rules: {e}")
            raise
    
    def import_category_rules(self, input_path: str, merge_mode: str = 'merge') -> Dict[str, Any]:
        """
        Import category rules from a file.
        
        Args:
            input_path: Path to the file containing rules to import
            merge_mode: How to handle conflicts ('merge', 'replace', 'skip')
            
        Returns:
            Dictionary with import results and statistics
        """
        if merge_mode not in ['merge', 'replace', 'skip']:
            raise ValueError("merge_mode must be 'merge', 'replace', or 'skip'")
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Import file not found: {input_path}")
        
        # Load import data
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                if input_path.endswith('.yaml') or input_path.endswith('.yml'):
                    import_data = yaml.safe_load(f)
                else:  # assume json
                    import_data = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse import file: {e}")
        
        # Validate import data structure
        if not isinstance(import_data, dict):
            raise ValueError("Import data must be a dictionary")
        
        if 'categories' not in import_data:
            raise ValueError("Import data must contain 'categories' section")
        
        # Load current configuration
        current_config = self.storage.load_categories()
        current_categories = current_config.get('categories', {})
        
        # Import statistics
        stats = {
            'categories_imported': 0,
            'categories_skipped': 0,
            'categories_replaced': 0,
            'patterns_imported': 0,
            'patterns_skipped': 0,
            'conflicts_resolved': 0
        }
        
        # Process imported categories
        imported_categories = import_data['categories']
        
        for category_name, category_data in imported_categories.items():
            if category_name in current_categories:
                if merge_mode == 'skip':
                    stats['categories_skipped'] += 1
                    continue
                elif merge_mode == 'replace':
                    current_categories[category_name] = category_data
                    stats['categories_replaced'] += 1
                    stats['patterns_imported'] += len(category_data.get('patterns', []))
                else:  # merge
                    # Merge patterns
                    current_patterns = current_categories[category_name].get('patterns', [])
                    imported_patterns = category_data.get('patterns', [])
                    
                    # Create pattern lookup for conflict detection
                    current_pattern_lookup = {p['pattern']: p for p in current_patterns}
                    
                    for imported_pattern in imported_patterns:
                        pattern_text = imported_pattern['pattern']
                        
                        if pattern_text in current_pattern_lookup:
                            # Conflict - use imported pattern (higher confidence wins)
                            if imported_pattern.get('confidence', 0) > current_pattern_lookup[pattern_text].get('confidence', 0):
                                # Replace with imported pattern
                                for i, p in enumerate(current_patterns):
                                    if p['pattern'] == pattern_text:
                                        current_patterns[i] = imported_pattern
                                        break
                                stats['conflicts_resolved'] += 1
                            else:
                                stats['patterns_skipped'] += 1
                        else:
                            # No conflict - add pattern
                            current_patterns.append(imported_pattern)
                            stats['patterns_imported'] += 1
                    
                    current_categories[category_name]['patterns'] = current_patterns
            else:
                # New category
                current_categories[category_name] = category_data
                stats['categories_imported'] += 1
                stats['patterns_imported'] += len(category_data.get('patterns', []))
        
        # Update configuration
        current_config['categories'] = current_categories
        
        # Update general config if provided
        if 'general_config' in import_data:
            general_config = import_data['general_config']
            for key, value in general_config.items():
                if key in ['default_category', 'confidence_threshold'] and value is not None:
                    current_config[key] = value
        
        # Save updated configuration
        self.storage.save_categories(current_config)
        
        self.logger.info(f"Category rules imported from {input_path}: {stats}")
        return stats
    
    def enable_ai_categorization(self, enabled: bool = True) -> None:
        """
        Enable or disable AI categorization.
        
        Args:
            enabled: Whether to enable AI categorization
        """
        self.update_ai_config({'enabled': enabled})
    
    def enable_ml_categorization(self, enabled: bool = True) -> None:
        """
        Enable or disable ML categorization.
        
        Args:
            enabled: Whether to enable ML categorization
        """
        self.update_ml_config({'enabled': enabled})
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current configuration.
        
        Returns:
            Dictionary with configuration summary
        """
        # Load current categories
        config = self.storage.load_categories()
        categories = config.get('categories', {})
        
        # Count patterns by type
        pattern_stats = {'substring': 0, 'regex': 0, 'exact': 0}
        total_patterns = 0
        
        for category_data in categories.values():
            for pattern in category_data.get('patterns', []):
                pattern_type = pattern.get('type', 'substring')
                pattern_stats[pattern_type] = pattern_stats.get(pattern_type, 0) + 1
                total_patterns += 1
        
        return {
            'general': {
                'version': config.get('version'),
                'default_category': config.get('default_category'),
                'confidence_threshold': config.get('confidence_threshold'),
                'total_categories': len(categories),
                'total_patterns': total_patterns,
                'pattern_types': pattern_stats
            },
            'ai': {
                'enabled': self._ai_config.get('enabled', True),
                'primary_service': self._ai_config.get('primary_service', 'openai'),
                'fallback_service': self._ai_config.get('fallback_service', 'claude'),
                'cache_responses': self._ai_config.get('cache_responses', True),
                'max_cost_per_month': self._ai_config.get('max_cost_per_month', 50.0),
                'api_keys_configured': list(self._ai_config.get('api_keys', {}).keys())
            },
            'ml': {
                'enabled': self._ml_config.get('enabled', True),
                'model_type': self._ml_config.get('model_type', 'random_forest'),
                'confidence_threshold': self._ml_config.get('confidence_threshold', 0.6),
                'retrain_threshold': self._ml_config.get('retrain_threshold', 100),
                'model_path': self._ml_config.get('model_path', 'ml_model.pkl')
            }
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate the current configuration and return any issues.
        
        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []
        
        # Validate AI configuration
        if self._ai_config.get('enabled', True):
            primary_service = self._ai_config.get('primary_service', 'openai')
            if not self.get_api_key(primary_service):
                issues.append(f"AI enabled but no API key found for {primary_service}")
            
            fallback_service = self._ai_config.get('fallback_service', 'claude')
            if fallback_service != 'none' and not self.get_api_key(fallback_service):
                warnings.append(f"No API key found for fallback service {fallback_service}")
        
        # Validate ML configuration
        if self._ml_config.get('enabled', True):
            model_path = self._ml_config.get('model_path', 'ml_model.pkl')
            if not os.path.exists(model_path):
                warnings.append(f"ML model file not found: {model_path}")
        
        # Validate categories configuration
        try:
            config = self.storage.load_categories()
            validation_result = self.storage.validate_config(config)
            if not validation_result['valid']:
                issues.extend(validation_result['errors'])
        except Exception as e:
            issues.append(f"Failed to validate categories configuration: {e}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    def _load_configuration(self) -> None:
        """Load configuration from storage."""
        try:
            config = self.storage.load_categories()
            
            # Load AI configuration with proper defaults
            default_ai_config = {
                'enabled': True,
                'primary_service': 'openai',
                'fallback_service': 'claude',
                'cache_responses': True,
                'max_cost_per_month': 50.0
            }
            self._ai_config = config.get('ai_config', default_ai_config.copy())
            # Ensure all required keys exist
            for key, value in default_ai_config.items():
                if key not in self._ai_config:
                    self._ai_config[key] = value
            
            # Load ML configuration with proper defaults
            default_ml_config = {
                'enabled': True,
                'model_type': 'random_forest',
                'retrain_threshold': 100,
                'confidence_threshold': 0.6
            }
            self._ml_config = config.get('ml_config', default_ml_config.copy())
            # Ensure all required keys exist
            for key, value in default_ml_config.items():
                if key not in self._ml_config:
                    self._ml_config[key] = value
            
            # Load general configuration
            self._general_config = {
                'version': config.get('version', '1.0'),
                'default_category': config.get('default_category', 'Uncategorized'),
                'confidence_threshold': config.get('confidence_threshold', 0.7)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            # Use defaults
            self._ai_config = {'enabled': True, 'primary_service': 'openai'}
            self._ml_config = {'enabled': True, 'model_type': 'random_forest'}
            self._general_config = {'version': '1.0', 'default_category': 'Uncategorized'}
    
    def _save_configuration(self) -> None:
        """Save configuration to storage."""
        try:
            # Load current config
            config = self.storage.load_categories()
            
            # Update with current settings
            config['ai_config'] = self._ai_config
            config['ml_config'] = self._ml_config
            config.update(self._general_config)
            
            # Save updated config
            self.storage.save_categories(config)
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        # Create default configuration
        default_config = self.storage.get_default_categories()
        
        # Save default configuration
        self.storage.save_categories(default_config)
        
        # Reload configuration
        self._load_configuration()
        
        self.logger.info("Configuration reset to defaults")
    
    def create_backup(self) -> str:
        """
        Create a backup of the current configuration.
        
        Returns:
            Path to the created backup file
        """
        # Ensure current configuration is saved to disk before backing up
        self._save_configuration()
        
        return self.storage.backup_config()
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List available configuration backups.
        
        Returns:
            List of backup information dictionaries
        """
        backup_dir = self.storage.backup_dir
        backups = []
        
        if backup_dir.exists():
            for backup_file in backup_dir.glob("categories_backup_*.yaml"):
                try:
                    stat = backup_file.stat()
                    backups.append({
                        'filename': backup_file.name,
                        'path': str(backup_file),
                        'created_at': datetime.fromtimestamp(stat.st_ctime),
                        'size_bytes': stat.st_size
                    })
                except Exception as e:
                    self.logger.warning(f"Error reading backup file {backup_file}: {e}")
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return backups
    
    def restore_backup(self, backup_path: str) -> None:
        """
        Restore configuration from a backup file.
        
        Args:
            backup_path: Path to the backup file to restore
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        try:
            # Copy backup file to main config location
            shutil.copy2(backup_path, self.config_path)
            
            # Force reload configuration from the restored file
            self._load_configuration()
            
            self.logger.info(f"Configuration restored from backup: {backup_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            raise