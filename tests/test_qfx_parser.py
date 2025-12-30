"""Tests for QFX parser functionality."""

import os
import tempfile
from datetime import datetime
from decimal import Decimal

import pytest

from kiro_budget.models.core import ParserConfig
from kiro_budget.parsers.qfx_parser import QFXParser


class TestQFXParser:
    """Test cases for QFX parser"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ParserConfig()
        self.parser = QFXParser(self.config)
    
    def test_supported_extensions(self):
        """Test that QFX parser supports correct extensions"""
        extensions = self.parser.get_supported_extensions()
        assert '.qfx' in extensions
        assert '.ofx' in extensions
    
    def test_validate_file_nonexistent(self):
        """Test validation of non-existent file"""
        assert not self.parser.validate_file('/nonexistent/file.qfx')
    
    def test_validate_file_wrong_extension(self):
        """Test validation of file with wrong extension"""
        with tempfile.NamedTemporaryFile(suffix='.txt') as f:
            assert not self.parser.validate_file(f.name)
    
    def test_validate_file_invalid_content(self):
        """Test validation of file with invalid OFX content"""
        invalid_content = "This is not an OFX file"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.qfx', delete=False) as f:
            f.write(invalid_content)
            temp_path = f.name
        
        try:
            assert not self.parser.validate_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validate_file_valid_ofx_header(self):
        """Test validation of file with valid OFX header"""
        valid_content = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
</OFX>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ofx', delete=False) as f:
            f.write(valid_content)
            temp_path = f.name
        
        try:
            assert self.parser.validate_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_extract_account_info(self):
        """Test account information extraction"""
        # Mock account object
        class MockAccount:
            def __init__(self, account_id=None, number=None):
                self.account_id = account_id
                self.number = number
        
        # Test with account_id
        account = MockAccount(account_id="123456789")
        result = self.parser.extract_account_info(account)
        assert result == "6789"  # Last 4 digits
        
        # Test with number field
        account = MockAccount(number="987654321")
        result = self.parser.extract_account_info(account)
        assert result == "4321"  # Last 4 digits
        
        # Test with no valid account info
        account = MockAccount()
        result = self.parser.extract_account_info(account)
        assert result == "unknown"
    
    def test_integration_with_real_qfx(self):
        """Test parsing with real QFX file if available"""
        # Check for real QFX files in the raw directory
        qfx_files = []
        raw_dir = "kiro-budget/raw"
        
        if os.path.exists(raw_dir):
            for root, dirs, files in os.walk(raw_dir):
                for file in files:
                    if file.lower().endswith(('.qfx', '.ofx')):
                        qfx_files.append(os.path.join(root, file))
        
        if qfx_files:
            # Test with the first available QFX file
            qfx_file = qfx_files[0]
            
            # Test validation
            is_valid = self.parser.validate_file(qfx_file)
            assert is_valid
            
            # Test parsing
            transactions = self.parser.parse(qfx_file)
            assert isinstance(transactions, list)
            
            # If we got transactions, check they have required fields
            if transactions:
                first_txn = transactions[0]
                assert isinstance(first_txn.date, datetime)
                assert isinstance(first_txn.amount, Decimal)
                assert isinstance(first_txn.description, str)
                assert isinstance(first_txn.account, str)
                assert isinstance(first_txn.institution, str)
        else:
            pytest.skip("No real QFX files available for testing")