"""Tests for account configuration loader."""

import os
import tempfile
import unittest
from pathlib import Path

import yaml

from kiro_budget.utils.account_config import AccountConfigLoader
from kiro_budget.models.core import AccountConfig


class TestAccountConfigLoader(unittest.TestCase):
    """Test cases for AccountConfigLoader"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'accounts.yaml')
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _write_yaml(self, data):
        """Helper to write YAML config file"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f)
    
    # =========================================================================
    # Task 2.1: Basic loading and parsing tests
    # =========================================================================
    
    def test_load_valid_config(self):
        """Test loading a valid configuration file"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'debit',
                    'description': 'Primary checking account'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        result = loader.load()
        
        self.assertTrue(result)
        self.assertEqual(loader.account_count(), 1)
        
        account = loader.get_account('firsttech', '0547')
        self.assertIsNotNone(account)
        self.assertEqual(account.account_name, 'Main Checking')
        self.assertEqual(account.account_type, 'debit')
        self.assertEqual(account.description, 'Primary checking account')
    
    def test_load_multiple_institutions(self):
        """Test loading configuration with multiple institutions (Requirement 1.4)"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'debit'
                }
            },
            'chase': {
                '4521': {
                    'account_name': 'Sapphire Preferred',
                    'account_type': 'credit'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        self.assertEqual(loader.account_count(), 2)
        
        firsttech_account = loader.get_account('firsttech', '0547')
        self.assertIsNotNone(firsttech_account)
        self.assertEqual(firsttech_account.account_name, 'Main Checking')
        
        chase_account = loader.get_account('chase', '4521')
        self.assertIsNotNone(chase_account)
        self.assertEqual(chase_account.account_name, 'Sapphire Preferred')
    
    def test_hierarchical_structure(self):
        """Test parsing hierarchical structure (Requirement 2.1)"""
        config_data = {
            'firsttech': {
                '0125': {
                    'account_name': 'Primary Savings',
                    'account_type': 'debit'
                },
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'debit'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        self.assertEqual(loader.account_count(), 2)
        
        # Verify both accounts are accessible
        savings = loader.get_account('firsttech', '0125')
        checking = loader.get_account('firsttech', '0547')
        
        self.assertIsNotNone(savings)
        self.assertIsNotNone(checking)
        self.assertEqual(savings.account_name, 'Primary Savings')
        self.assertEqual(checking.account_name, 'Main Checking')
    
    def test_get_all_accounts(self):
        """Test getting all configured accounts"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'debit'
                }
            },
            'chase': {
                '4521': {
                    'account_name': 'Sapphire Preferred',
                    'account_type': 'credit'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        all_accounts = loader.get_all_accounts()
        self.assertEqual(len(all_accounts), 2)
        
        account_names = {acc.account_name for acc in all_accounts}
        self.assertIn('Main Checking', account_names)
        self.assertIn('Sapphire Preferred', account_names)
    
    def test_case_insensitive_institution_lookup(self):
        """Test that institution lookup is case-insensitive"""
        config_data = {
            'FirstTech': {
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'debit'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        # Should find account regardless of case
        account1 = loader.get_account('firsttech', '0547')
        account2 = loader.get_account('FIRSTTECH', '0547')
        account3 = loader.get_account('FirstTech', '0547')
        
        self.assertIsNotNone(account1)
        self.assertIsNotNone(account2)
        self.assertIsNotNone(account3)
    
    # =========================================================================
    # Task 2.2: Validation tests
    # =========================================================================
    
    def test_missing_account_name_skipped(self):
        """Test that accounts without account_name are skipped (Requirement 2.2)"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_type': 'debit'
                    # Missing account_name
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        self.assertEqual(loader.account_count(), 0)
        self.assertIsNone(loader.get_account('firsttech', '0547'))
    
    def test_invalid_account_type_defaults_to_debit(self):
        """Test that invalid account_type defaults to 'debit' (Requirement 2.4)"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'invalid_type'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        account = loader.get_account('firsttech', '0547')
        self.assertIsNotNone(account)
        self.assertEqual(account.account_type, 'debit')
    
    def test_missing_account_type_defaults_to_debit(self):
        """Test that missing account_type defaults to 'debit'"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Main Checking'
                    # Missing account_type
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        account = loader.get_account('firsttech', '0547')
        self.assertIsNotNone(account)
        self.assertEqual(account.account_type, 'debit')
    
    def test_valid_account_types(self):
        """Test that valid account types are accepted (Requirement 2.3)"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Checking',
                    'account_type': 'debit'
                },
                '0548': {
                    'account_name': 'Credit Card',
                    'account_type': 'credit'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        debit_account = loader.get_account('firsttech', '0547')
        credit_account = loader.get_account('firsttech', '0548')
        
        self.assertEqual(debit_account.account_type, 'debit')
        self.assertEqual(credit_account.account_type, 'credit')
    
    def test_account_type_case_insensitive(self):
        """Test that account_type is case-insensitive"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Checking',
                    'account_type': 'DEBIT'
                },
                '0548': {
                    'account_name': 'Credit Card',
                    'account_type': 'Credit'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        debit_account = loader.get_account('firsttech', '0547')
        credit_account = loader.get_account('firsttech', '0548')
        
        self.assertEqual(debit_account.account_type, 'debit')
        self.assertEqual(credit_account.account_type, 'credit')
    
    def test_optional_description(self):
        """Test that description is optional (Requirement 2.5)"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'debit'
                    # No description
                },
                '0548': {
                    'account_name': 'Savings',
                    'account_type': 'debit',
                    'description': 'Emergency fund'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        no_desc = loader.get_account('firsttech', '0547')
        with_desc = loader.get_account('firsttech', '0548')
        
        self.assertIsNone(no_desc.description)
        self.assertEqual(with_desc.description, 'Emergency fund')
    
    # =========================================================================
    # Task 2.3: Error handling tests
    # =========================================================================
    
    def test_missing_config_file(self):
        """Test graceful handling of missing config file (Requirement 1.2)"""
        loader = AccountConfigLoader('nonexistent/path/accounts.yaml')
        result = loader.load()
        
        # Should return True (graceful handling) but with no accounts
        self.assertTrue(result)
        self.assertEqual(loader.account_count(), 0)
        self.assertTrue(loader.is_loaded())
    
    def test_invalid_yaml_syntax(self):
        """Test graceful handling of invalid YAML (Requirement 1.3)"""
        # Write invalid YAML
        with open(self.config_file, 'w') as f:
            f.write("invalid: yaml: content: [unclosed")
        
        loader = AccountConfigLoader(self.config_file)
        result = loader.load()
        
        # Should return False but continue gracefully
        self.assertFalse(result)
        self.assertEqual(loader.account_count(), 0)
        self.assertTrue(loader.is_loaded())
    
    def test_empty_config_file(self):
        """Test handling of empty config file"""
        # Write empty file
        with open(self.config_file, 'w') as f:
            f.write("")
        
        loader = AccountConfigLoader(self.config_file)
        result = loader.load()
        
        self.assertTrue(result)
        self.assertEqual(loader.account_count(), 0)
    
    def test_non_dict_root(self):
        """Test handling of non-dictionary root element"""
        with open(self.config_file, 'w') as f:
            f.write("- item1\n- item2")  # YAML list instead of dict
        
        loader = AccountConfigLoader(self.config_file)
        result = loader.load()
        
        self.assertFalse(result)
        self.assertEqual(loader.account_count(), 0)
    
    def test_auto_load_on_get_account(self):
        """Test that get_account auto-loads if not loaded"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'debit'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        # Don't call load() explicitly
        
        account = loader.get_account('firsttech', '0547')
        self.assertIsNotNone(account)
        self.assertTrue(loader.is_loaded())
    
    def test_get_nonexistent_account(self):
        """Test getting an account that doesn't exist"""
        config_data = {
            'firsttech': {
                '0547': {
                    'account_name': 'Main Checking',
                    'account_type': 'debit'
                }
            }
        }
        self._write_yaml(config_data)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        # Non-existent account_id
        self.assertIsNone(loader.get_account('firsttech', '9999'))
        # Non-existent institution
        self.assertIsNone(loader.get_account('unknown', '0547'))


class TestAccountConfigLoaderMultiInstitution(unittest.TestCase):
    """Test cases for multi-institution isolation (Property 6)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'accounts.yaml')
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_same_account_id_different_institutions(self):
        """Test that same account_id in different institutions are isolated"""
        config_data = {
            'firsttech': {
                '1234': {
                    'account_name': 'FirstTech Checking',
                    'account_type': 'debit'
                }
            },
            'chase': {
                '1234': {
                    'account_name': 'Chase Credit',
                    'account_type': 'credit'
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        loader = AccountConfigLoader(self.config_file)
        loader.load()
        
        firsttech_account = loader.get_account('firsttech', '1234')
        chase_account = loader.get_account('chase', '1234')
        
        self.assertIsNotNone(firsttech_account)
        self.assertIsNotNone(chase_account)
        
        # Verify they are different accounts
        self.assertEqual(firsttech_account.account_name, 'FirstTech Checking')
        self.assertEqual(firsttech_account.account_type, 'debit')
        
        self.assertEqual(chase_account.account_name, 'Chase Credit')
        self.assertEqual(chase_account.account_type, 'credit')


if __name__ == '__main__':
    unittest.main()
