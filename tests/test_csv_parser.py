"""Tests for CSV parser functionality."""

import os
import tempfile
from datetime import datetime
from decimal import Decimal

import pytest

from kiro_budget.models.core import ParserConfig
from kiro_budget.parsers.csv_parser import CSVParser


class TestCSVParser:
    """Test cases for CSV parser"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = ParserConfig()
        self.parser = CSVParser(self.config)
    
    def test_supported_extensions(self):
        """Test that CSV parser supports correct extensions"""
        extensions = self.parser.get_supported_extensions()
        assert '.csv' in extensions
    
    def test_column_mapping_detection(self):
        """Test automatic column mapping detection"""
        headers = ['Date', 'Amount', 'Description', 'Account']
        mapping = self.parser.detect_column_mapping(headers)
        
        assert 'date' in mapping
        assert 'amount' in mapping
        assert 'description' in mapping
        assert 'account' in mapping
    
    def test_debit_credit_column_detection(self):
        """Test detection of separate debit/credit columns"""
        headers = ['Date', 'Debit', 'Credit', 'Description']
        mapping = self.parser.detect_column_mapping(headers)
        
        assert 'date' in mapping
        assert 'debit' in mapping
        assert 'credit' in mapping
        assert 'description' in mapping
    
    def test_parse_simple_csv(self):
        """Test parsing a simple CSV file"""
        csv_content = """Date,Amount,Description,Account
2024-01-01,100.50,Test Transaction,1234
2024-01-02,-25.00,Another Transaction,1234"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            transactions = self.parser.parse(temp_path)
            
            assert len(transactions) == 2
            
            # Check first transaction
            assert transactions[0].date == datetime(2024, 1, 1)
            assert transactions[0].amount == Decimal('100.50')
            assert transactions[0].description == 'Test Transaction'
            assert transactions[0].account == '1234'
            
            # Check second transaction
            assert transactions[1].date == datetime(2024, 1, 2)
            assert transactions[1].amount == Decimal('-25.00')
            assert transactions[1].description == 'Another Transaction'
            assert transactions[1].account == '1234'
            
        finally:
            os.unlink(temp_path)
    
    def test_parse_debit_credit_csv(self):
        """Test parsing CSV with separate debit/credit columns"""
        csv_content = """Date,Debit,Credit,Description
2024-01-01,,100.50,Deposit
2024-01-02,25.00,,Withdrawal"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            transactions = self.parser.parse(temp_path)
            
            assert len(transactions) == 2
            
            # Check deposit (credit should be positive)
            assert transactions[0].amount == Decimal('100.50')
            
            # Check withdrawal (debit should be negative)
            assert transactions[1].amount == Decimal('-25.00')
            
        finally:
            os.unlink(temp_path)
    
    def test_validate_file_nonexistent(self):
        """Test validation of non-existent file"""
        assert not self.parser.validate_file('/nonexistent/file.csv')
    
    def test_validate_file_wrong_extension(self):
        """Test validation of file with wrong extension"""
        with tempfile.NamedTemporaryFile(suffix='.txt') as f:
            assert not self.parser.validate_file(f.name)
    
    def test_validate_file_valid_csv(self):
        """Test validation of valid CSV file"""
        csv_content = "Date,Amount\n2024-01-01,100.00"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            assert self.parser.validate_file(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_parse_different_date_formats(self):
        """Test parsing CSV with different date formats"""
        csv_content = """Date,Amount,Description
01/15/2024,100.50,Test Transaction
2024-01-16,-25.00,Another Transaction"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            transactions = self.parser.parse(temp_path)
            
            assert len(transactions) == 2
            
            # Check first transaction with MM/DD/YYYY format
            assert transactions[0].date == datetime(2024, 1, 15)
            assert transactions[0].amount == Decimal('100.50')
            
            # Check second transaction with YYYY-MM-DD format
            assert transactions[1].date == datetime(2024, 1, 16)
            assert transactions[1].amount == Decimal('-25.00')
            
        finally:
            os.unlink(temp_path)
    
    def test_parse_currency_formats(self):
        """Test parsing CSV with different currency formats"""
        csv_content = """Date,Amount,Description
2024-01-01,$1234.56,Dollar amount
2024-01-02,(25.00),Negative in parentheses
2024-01-03,1000,No decimal"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name
        
        try:
            transactions = self.parser.parse(temp_path)
            
            assert len(transactions) == 3
            
            # Check dollar amount
            assert transactions[0].amount == Decimal('1234.56')
            
            # Check negative amount in parentheses
            assert transactions[1].amount == Decimal('-25.00')
            
            # Check amount without decimal
            assert transactions[2].amount == Decimal('1000')
            
        finally:
            os.unlink(temp_path)