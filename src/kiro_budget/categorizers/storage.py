"""
Category storage and configuration management with YAML support.
"""

import os
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .interfaces import StorageInterface
from .models import CategoryDefinition, PatternRule


class CategoryStorage(StorageInterface):
    """
    Human-readable YAML-based storage for category rules and configurations.
    Provides backup functionality and validation for configuration changes.
    """
    
    def __init__(self, config_path: str = "categories.yaml"):
        """
        Initialize category storage with specified configuration file.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = Path(config_path)
        self.backup_dir = self.config_path.parent / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Default configuration structure
        self._default_config = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": 0.7,
            "categories": {},
            "ai_config": {
                "enabled": True,
                "primary_service": "openai",
                "fallback_service": "claude",
                "cache_responses": True,
                "max_cost_per_month": 50.0
            },
            "ml_config": {
                "enabled": True,
                "model_type": "random_forest",
                "retrain_threshold": 100,
                "confidence_threshold": 0.6
            }
        }
    
    def load_categories(self) -> Dict[str, Any]:
        """
        Load category configuration from YAML file.
        
        Returns:
            Dictionary containing the complete configuration
        """
        if not self.config_path.exists():
            # Create default configuration if file doesn't exist
            self.save_categories(self._default_config)
            return self._default_config.copy()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            # Validate and merge with defaults
            validated_config = self._validate_and_merge_config(config)
            return validated_config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    def save_categories(self, config: Dict[str, Any]) -> None:
        """
        Save category configuration to YAML file with backup.
        
        Args:
            config: Complete configuration dictionary to save
        """
        # Validate configuration before saving
        validation_result = self.validate_config(config)
        if not validation_result["valid"]:
            raise ValueError(f"Invalid configuration: {validation_result['errors']}")
        
        # Create backup before saving
        if self.config_path.exists():
            self.backup_config()
        
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False, 
                         allow_unicode=True, indent=2)
                
        except Exception as e:
            raise RuntimeError(f"Failed to save configuration: {e}")
    
    def add_pattern_rule(self, category: str, pattern: str, confidence: float, 
                        specificity: str = "medium", pattern_type: str = "substring") -> None:
        """
        Add a new pattern rule to the configuration.
        
        Args:
            category: Category name
            pattern: Pattern string
            confidence: Confidence score (0.0-1.0)
            specificity: Pattern specificity level
            pattern_type: Type of pattern matching
        """
        config = self.load_categories()
        
        # Initialize category if it doesn't exist
        if category not in config["categories"]:
            config["categories"][category] = {"patterns": []}
        
        # Add the new pattern
        new_pattern = {
            "pattern": pattern,
            "confidence": confidence,
            "type": pattern_type,
            "specificity": specificity
        }
        
        config["categories"][category]["patterns"].append(new_pattern)
        
        # Save updated configuration
        self.save_categories(config)
    
    def backup_config(self) -> str:
        """
        Create a timestamped backup of the current configuration.
        
        Returns:
            Path to the created backup file
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file {self.config_path} does not exist")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"categories_backup_{timestamp}.yaml"
        backup_path = self.backup_dir / backup_filename
        
        try:
            shutil.copy2(self.config_path, backup_path)
            return str(backup_path)
        except Exception as e:
            raise RuntimeError(f"Failed to create backup: {e}")
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration structure and content.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Dictionary with validation results: {"valid": bool, "errors": List[str]}
        """
        errors = []
        
        # Check required top-level keys
        required_keys = ["version", "default_category", "confidence_threshold", "categories"]
        for key in required_keys:
            if key not in config:
                errors.append(f"Missing required key: {key}")
        
        # Validate confidence threshold
        if "confidence_threshold" in config:
            threshold = config["confidence_threshold"]
            if not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
                errors.append("confidence_threshold must be a number between 0.0 and 1.0")
        
        # Validate categories structure
        if "categories" in config and isinstance(config["categories"], dict):
            for category_name, category_data in config["categories"].items():
                if not isinstance(category_name, str) or not category_name.strip():
                    errors.append(f"Category name must be a non-empty string: {category_name}")
                
                if not isinstance(category_data, dict):
                    errors.append(f"Category data must be a dictionary: {category_name}")
                    continue
                
                # Validate patterns
                if "patterns" in category_data:
                    if not isinstance(category_data["patterns"], list):
                        errors.append(f"Patterns must be a list for category: {category_name}")
                    else:
                        for i, pattern in enumerate(category_data["patterns"]):
                            pattern_errors = self._validate_pattern(pattern, category_name, i)
                            errors.extend(pattern_errors)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def get_default_categories(self) -> Dict[str, Any]:
        """
        Get default category configuration with common spending categories.
        
        Returns:
            Dictionary with default categories and patterns
        """
        default_categories = {
            "version": "1.0",
            "default_category": "Uncategorized",
            "confidence_threshold": 0.7,
            "categories": {
                "Groceries": {
                    "patterns": [
                        {"pattern": "COSTCO", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": "FRED MEYER", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "SAFEWAY", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "WHOLE FOODS", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": "TRADER JOE", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": ".*GROCERY.*", "confidence": 0.85, "type": "regex", "specificity": "medium"},
                        {"pattern": ".*MARKET.*", "confidence": 0.75, "type": "regex", "specificity": "low"}
                    ]
                },
                "Gas": {
                    "patterns": [
                        {"pattern": "COSTCO GAS", "confidence": 0.95, "type": "substring", "specificity": "very_high"},
                        {"pattern": ".*GAS.*", "confidence": 0.85, "type": "regex", "specificity": "high"},
                        {"pattern": "SHELL", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "CHEVRON", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "EXXON", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "BP ", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "ARCO", "confidence": 0.90, "type": "substring", "specificity": "high"}
                    ]
                },
                "Restaurants": {
                    "patterns": [
                        {"pattern": ".*RESTAURANT.*", "confidence": 0.85, "type": "regex", "specificity": "medium"},
                        {"pattern": "STARBUCKS", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": "MCDONALD", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": "SUBWAY", "confidence": 0.90, "type": "substring", "specificity": "medium"},
                        {"pattern": "CHIPOTLE", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": ".*PIZZA.*", "confidence": 0.85, "type": "regex", "specificity": "medium"},
                        {"pattern": ".*CAFE.*", "confidence": 0.80, "type": "regex", "specificity": "medium"}
                    ]
                },
                "Shopping": {
                    "patterns": [
                        {"pattern": "AMAZON", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "TARGET", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "WALMART", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "BEST BUY", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": ".*STORE.*", "confidence": 0.70, "type": "regex", "specificity": "low"}
                    ]
                },
                "Utilities": {
                    "patterns": [
                        {"pattern": ".*ELECTRIC.*", "confidence": 0.90, "type": "regex", "specificity": "high"},
                        {"pattern": ".*WATER.*", "confidence": 0.85, "type": "regex", "specificity": "medium"},
                        {"pattern": ".*INTERNET.*", "confidence": 0.90, "type": "regex", "specificity": "high"},
                        {"pattern": "COMCAST", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": "VERIZON", "confidence": 0.90, "type": "substring", "specificity": "high"},
                        {"pattern": "AT&T", "confidence": 0.90, "type": "substring", "specificity": "high"}
                    ]
                },
                "Transportation": {
                    "patterns": [
                        {"pattern": "UBER", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": "LYFT", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": ".*TRANSIT.*", "confidence": 0.85, "type": "regex", "specificity": "medium"},
                        {"pattern": ".*PARKING.*", "confidence": 0.85, "type": "regex", "specificity": "medium"}
                    ]
                },
                "Healthcare": {
                    "patterns": [
                        {"pattern": ".*MEDICAL.*", "confidence": 0.85, "type": "regex", "specificity": "medium"},
                        {"pattern": ".*PHARMACY.*", "confidence": 0.90, "type": "regex", "specificity": "high"},
                        {"pattern": "CVS", "confidence": 0.85, "type": "substring", "specificity": "medium"},
                        {"pattern": "WALGREENS", "confidence": 0.90, "type": "substring", "specificity": "high"}
                    ]
                },
                "Entertainment": {
                    "patterns": [
                        {"pattern": "NETFLIX", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": "SPOTIFY", "confidence": 0.95, "type": "substring", "specificity": "high"},
                        {"pattern": ".*THEATER.*", "confidence": 0.85, "type": "regex", "specificity": "medium"},
                        {"pattern": ".*MOVIE.*", "confidence": 0.80, "type": "regex", "specificity": "medium"}
                    ]
                }
            },
            "ai_config": {
                "enabled": True,
                "primary_service": "openai",
                "fallback_service": "claude",
                "cache_responses": True,
                "max_cost_per_month": 50.0
            },
            "ml_config": {
                "enabled": True,
                "model_type": "random_forest",
                "retrain_threshold": 100,
                "confidence_threshold": 0.6
            }
        }
        
        return default_categories
    
    def create_default_config(self) -> None:
        """Create default configuration file with common categories."""
        default_config = self.get_default_categories()
        self.save_categories(default_config)
    
    def _validate_pattern(self, pattern: Dict[str, Any], category_name: str, pattern_index: int) -> List[str]:
        """
        Validate a single pattern configuration.
        
        Args:
            pattern: Pattern dictionary to validate
            category_name: Name of the category containing this pattern
            pattern_index: Index of pattern in the list
            
        Returns:
            List of validation error messages
        """
        errors = []
        prefix = f"Category '{category_name}', pattern {pattern_index}"
        
        # Check required pattern fields
        required_fields = ["pattern", "confidence", "type"]
        for field in required_fields:
            if field not in pattern:
                errors.append(f"{prefix}: Missing required field '{field}'")
        
        # Validate confidence score
        if "confidence" in pattern:
            confidence = pattern["confidence"]
            if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
                errors.append(f"{prefix}: confidence must be between 0.0 and 1.0")
        
        # Validate pattern type
        if "type" in pattern:
            valid_types = ["exact", "substring", "regex"]
            if pattern["type"] not in valid_types:
                errors.append(f"{prefix}: type must be one of {valid_types}")
        
        # Validate specificity
        if "specificity" in pattern:
            valid_specificities = ["low", "medium", "high", "very_high"]
            if pattern["specificity"] not in valid_specificities:
                errors.append(f"{prefix}: specificity must be one of {valid_specificities}")
        
        # Validate regex patterns
        if pattern.get("type") == "regex" and "pattern" in pattern:
            try:
                import re
                re.compile(pattern["pattern"])
            except re.error as e:
                errors.append(f"{prefix}: Invalid regex pattern: {e}")
        
        return errors
    
    def _validate_and_merge_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration and merge with defaults for missing fields.
        
        Args:
            config: Configuration to validate and merge
            
        Returns:
            Validated and merged configuration
        """
        # Start with default configuration
        merged_config = self._default_config.copy()
        
        # Merge user configuration
        for key, value in config.items():
            if key == "categories" and isinstance(value, dict):
                # Merge categories carefully
                if "categories" not in merged_config:
                    merged_config["categories"] = {}
                merged_config["categories"].update(value)
            else:
                merged_config[key] = value
        
        return merged_config
    
    def add_category(self, name: str, category_data: Dict[str, Any]) -> bool:
        """
        Add a new category to the configuration.
        
        Args:
            name: Category name
            category_data: Category configuration data
            
        Returns:
            True if category was added successfully
        """
        try:
            config = self.load_categories()
            
            if "categories" not in config:
                config["categories"] = {}
            
            if name in config["categories"]:
                return False  # Category already exists
            
            config["categories"][name] = category_data
            self.save_categories(config)
            return True
            
        except Exception:
            return False
    
    def remove_category(self, name: str) -> bool:
        """
        Remove a category from the configuration.
        
        Args:
            name: Category name to remove
            
        Returns:
            True if category was removed successfully
        """
        try:
            config = self.load_categories()
            
            if "categories" not in config or name not in config["categories"]:
                return False  # Category doesn't exist
            
            del config["categories"][name]
            self.save_categories(config)
            return True
            
        except Exception:
            return False
    
    def update_category(self, name: str, category_data: Dict[str, Any], 
                       new_name: Optional[str] = None) -> bool:
        """
        Update an existing category's data.
        
        Args:
            name: Current category name
            category_data: New category data
            new_name: Optional new name for the category
            
        Returns:
            True if category was updated successfully
        """
        try:
            config = self.load_categories()
            
            if "categories" not in config or name not in config["categories"]:
                return False  # Category doesn't exist
            
            # Remove old category
            del config["categories"][name]
            
            # Add with new name (or same name)
            final_name = new_name if new_name else name
            config["categories"][final_name] = category_data
            
            self.save_categories(config)
            return True
            
        except Exception:
            return False
    
    def get_category_data(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get data for a specific category.
        
        Args:
            name: Category name
            
        Returns:
            Category data dictionary or None if not found
        """
        try:
            config = self.load_categories()
            return config.get("categories", {}).get(name)
        except Exception:
            return None
    
    def get_all_category_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Get data for all categories.
        
        Returns:
            Dictionary mapping category names to their data
        """
        try:
            config = self.load_categories()
            return config.get("categories", {})
        except Exception:
            return {}
    
    def category_exists(self, name: str) -> bool:
        """
        Check if a category exists.
        
        Args:
            name: Category name to check
            
        Returns:
            True if category exists
        """
        try:
            config = self.load_categories()
            return name in config.get("categories", {})
        except Exception:
            return False