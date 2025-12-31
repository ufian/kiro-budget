"""Account configuration loader for enriching transactions with account metadata."""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from ..models.core import AccountConfig


logger = logging.getLogger(__name__)


class AccountConfigLoader:
    """Loads and validates account configuration from YAML file.
    
    The configuration file follows a hierarchical structure:
    institution → account_id → properties
    
    Example accounts.yaml:
        firsttech:
          "0547":
            account_name: "Main Checking"
            account_type: debit
            description: "Primary checking account"
        chase:
          "4521":
            account_name: "Sapphire Preferred"
            account_type: credit
    """
    
    VALID_ACCOUNT_TYPES = {"debit", "credit"}
    DEFAULT_ACCOUNT_TYPE = "debit"
    
    def __init__(self, config_path: str = "raw/accounts.yaml"):
        """Initialize the account configuration loader.
        
        Args:
            config_path: Path to the accounts.yaml configuration file.
                        Defaults to "raw/accounts.yaml".
        """
        self.config_path = config_path
        self._accounts: Dict[Tuple[str, str], AccountConfig] = {}
        self._loaded = False
    
    def load(self) -> bool:
        """Load configuration from file.
        
        Returns:
            True if configuration was loaded successfully, False otherwise.
            Returns True with empty config if file doesn't exist (graceful handling).
        """
        self._accounts.clear()
        self._loaded = False
        
        # Handle missing config file gracefully (Requirement 1.2)
        if not os.path.exists(self.config_path):
            logger.info(
                f"Account configuration file not found at {self.config_path}. "
                "Continuing without account enrichment."
            )
            self._loaded = True
            return True
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            # Handle YAML parsing errors gracefully (Requirement 1.3)
            logger.error(
                f"Invalid YAML syntax in {self.config_path}: {e}. "
                "Continuing without account enrichment."
            )
            self._loaded = True
            return False
        except Exception as e:
            logger.error(
                f"Error reading account configuration file {self.config_path}: {e}. "
                "Continuing without account enrichment."
            )
            self._loaded = True
            return False
        
        # Handle empty file or non-dict content
        if data is None:
            logger.info(
                f"Account configuration file {self.config_path} is empty. "
                "Continuing without account enrichment."
            )
            self._loaded = True
            return True
        
        if not isinstance(data, dict):
            logger.error(
                f"Account configuration must be a dictionary, got {type(data).__name__}. "
                "Continuing without account enrichment."
            )
            self._loaded = True
            return False
        
        # Parse hierarchical structure (Requirement 2.1)
        self._parse_config(data)
        
        self._loaded = True
        logger.info(
            f"Loaded {len(self._accounts)} account configuration(s) from {self.config_path}"
        )
        return True
    
    def _parse_config(self, data: Dict) -> None:
        """Parse the hierarchical configuration structure.
        
        Args:
            data: Parsed YAML data with institution → account_id → properties structure.
        """
        for institution, accounts in data.items():
            if not isinstance(institution, str):
                logger.warning(
                    f"Skipping invalid institution key: {institution} (must be string)"
                )
                continue
            
            if accounts is None:
                logger.warning(
                    f"Institution '{institution}' has no accounts configured"
                )
                continue
            
            if not isinstance(accounts, dict):
                logger.warning(
                    f"Skipping institution '{institution}': accounts must be a dictionary"
                )
                continue
            
            for account_id, properties in accounts.items():
                self._parse_account(institution, str(account_id), properties)
    
    def _parse_account(
        self, 
        institution: str, 
        account_id: str, 
        properties: Optional[Dict]
    ) -> None:
        """Parse and validate a single account configuration.
        
        Args:
            institution: Institution name (e.g., "firsttech", "chase")
            account_id: Account identifier (e.g., "0547")
            properties: Account properties dictionary
        """
        if properties is None:
            logger.warning(
                f"Skipping account '{account_id}' for '{institution}': no properties defined"
            )
            return
        
        if not isinstance(properties, dict):
            logger.warning(
                f"Skipping account '{account_id}' for '{institution}': "
                "properties must be a dictionary"
            )
            return
        
        # Validate required field: account_name (Requirement 2.2)
        account_name = properties.get('account_name')
        if not account_name:
            logger.warning(
                f"Skipping account '{account_id}' for '{institution}': "
                "missing required field 'account_name'"
            )
            return
        
        if not isinstance(account_name, str):
            logger.warning(
                f"Skipping account '{account_id}' for '{institution}': "
                "'account_name' must be a string"
            )
            return
        
        # Validate required field: account_type (Requirement 2.3, 2.4)
        account_type = properties.get('account_type')
        if not account_type:
            logger.warning(
                f"Account '{account_id}' for '{institution}': "
                f"missing 'account_type', defaulting to '{self.DEFAULT_ACCOUNT_TYPE}'"
            )
            account_type = self.DEFAULT_ACCOUNT_TYPE
        elif not isinstance(account_type, str):
            logger.warning(
                f"Account '{account_id}' for '{institution}': "
                f"'account_type' must be a string, defaulting to '{self.DEFAULT_ACCOUNT_TYPE}'"
            )
            account_type = self.DEFAULT_ACCOUNT_TYPE
        elif account_type.lower() not in self.VALID_ACCOUNT_TYPES:
            logger.warning(
                f"Account '{account_id}' for '{institution}': "
                f"invalid account_type '{account_type}', defaulting to '{self.DEFAULT_ACCOUNT_TYPE}'"
            )
            account_type = self.DEFAULT_ACCOUNT_TYPE
        else:
            account_type = account_type.lower()
        
        # Get optional description (Requirement 2.5)
        description = properties.get('description')
        if description is not None and not isinstance(description, str):
            logger.warning(
                f"Account '{account_id}' for '{institution}': "
                "'description' must be a string, ignoring"
            )
            description = None
        
        # Create AccountConfig and store with (institution, account_id) key
        config = AccountConfig(
            account_id=account_id,
            institution=institution.lower(),
            account_name=account_name,
            account_type=account_type,
            description=description
        )
        
        key = (institution.lower(), account_id)
        if key in self._accounts:
            logger.warning(
                f"Duplicate account configuration for '{account_id}' in '{institution}', "
                "using latest definition"
            )
        
        self._accounts[key] = config
        logger.debug(
            f"Loaded account config: {institution}/{account_id} -> {account_name} ({account_type})"
        )
    
    def get_account(
        self, 
        institution: str, 
        account_id: str
    ) -> Optional[AccountConfig]:
        """Get account configuration by institution and account_id.
        
        Args:
            institution: Institution name (case-insensitive)
            account_id: Account identifier
            
        Returns:
            AccountConfig if found, None otherwise.
        """
        if not self._loaded:
            self.load()
        
        key = (institution.lower(), account_id)
        return self._accounts.get(key)
    
    def get_all_accounts(self) -> List[AccountConfig]:
        """Get all configured accounts.
        
        Returns:
            List of all AccountConfig objects.
        """
        if not self._loaded:
            self.load()
        
        return list(self._accounts.values())
    
    def is_loaded(self) -> bool:
        """Check if configuration has been loaded.
        
        Returns:
            True if load() has been called, False otherwise.
        """
        return self._loaded
    
    def account_count(self) -> int:
        """Get the number of configured accounts.
        
        Returns:
            Number of account configurations loaded.
        """
        return len(self._accounts)
