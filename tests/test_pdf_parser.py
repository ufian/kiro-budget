"""Tests for PDF parser functionality."""

import os
import tempfile
import unittest
from decimal import Decimal
from datetime import datetime

from kiro_budget.parsers.pdf_parser import PDFParser
from kiro_budget.models.core import ParserConfig


class TestPDFParser(unittest.TestCase):
    """Test cases for PDFParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ParserConfig()
        self.parser = PDFParser(self.config)
    
    def test_supported_extensions(self):
        """Test that PDF parser supports correct extensions."""
        extensions = self.parser.get_supported_extensions()
        self.assertEqual(extensions, ['.pdf'])
    
    def test_validate_file_nonexistent(self):
        """Test validation of non-existent file."""
        result = self.parser.validate_file('nonexistent.pdf')
        self.assertFalse(result)
    
    def test_validate_file_wrong_extension(self):
        """Test validation of file with wrong extension."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b'test content')
            tmp_path = tmp.name
        
        try:
            result = self.parser.validate_file(tmp_path)
            self.assertFalse(result)
        finally:
            os.unlink(tmp_path)
    
    def test_looks_like_transaction_line(self):
        """Test transaction line detection."""
        # Chase format
        chase_line = "10/15 Amazon.com Amzn.com/bill WA -3.86"
        self.assertTrue(self.parser._looks_like_transaction_line(chase_line))
        
        # Standard format with date and amount
        standard_line = "2024-10-15 Purchase at store $25.99"
        self.assertTrue(self.parser._looks_like_transaction_line(standard_line))
        
        # Line without transaction data
        non_transaction = "This is just regular text"
        self.assertFalse(self.parser._looks_like_transaction_line(non_transaction))
    
    def test_parse_text_line_chase_format(self):
        """Test parsing Chase-specific format."""
        line = "10/15 Amazon.com Amzn.com/bill WA -3.86"
        file_path = "raw/chase/statements-8147-.pdf"
        institution = "chase"
        
        transaction = self.parser._parse_text_line(line, file_path, institution)
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.date.month, 10)
        self.assertEqual(transaction.date.day, 15)
        self.assertEqual(transaction.amount, Decimal('-3.86'))
        self.assertEqual(transaction.description, "Amazon.com Amzn.com/bill WA")
        self.assertEqual(transaction.account, "8147")
        self.assertEqual(transaction.institution, "chase")
    
    def test_parse_text_line_positive_amount(self):
        """Test parsing line with positive amount."""
        line = "10/03 AMAZON MKTPL*NV46R2L51 Amzn.com/bill WA 52.20"
        file_path = "raw/chase/statements-8147-.pdf"
        institution = "chase"
        
        transaction = self.parser._parse_text_line(line, file_path, institution)
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('52.20'))
        self.assertEqual(transaction.description, "AMAZON MKTPL*NV46R2L51 Amzn.com/bill WA")
    
    def test_parse_invalid_line(self):
        """Test parsing invalid line returns None."""
        line = "This is not a transaction line"
        file_path = "raw/chase/statements-8147-.pdf"
        institution = "chase"
        
        transaction = self.parser._parse_text_line(line, file_path, institution)
        self.assertIsNone(transaction)
    
    def test_identify_columns(self):
        """Test column identification in table headers."""
        # Valid header with all required columns
        header = ["Date", "Description", "Amount", "Balance"]
        mapping = self.parser._identify_columns(header)
        
        self.assertIsNotNone(mapping)
        self.assertIn('date', mapping)
        self.assertIn('amount', mapping)
        self.assertEqual(mapping['date'], 0)
        self.assertEqual(mapping['description'], 1)
        self.assertEqual(mapping['amount'], 2)
        self.assertEqual(mapping['balance'], 3)
    
    def test_identify_columns_missing_required(self):
        """Test column identification with missing required columns."""
        # Header missing amount column
        header = ["Date", "Description", "Balance"]
        mapping = self.parser._identify_columns(header)
        
        self.assertIsNone(mapping)  # Should return None if missing required columns
    
    def test_identify_columns_case_insensitive(self):
        """Test column identification is case insensitive."""
        header = ["DATE", "DESCRIPTION", "AMOUNT"]
        mapping = self.parser._identify_columns(header)
        
        self.assertIsNotNone(mapping)
        self.assertIn('date', mapping)
        self.assertIn('amount', mapping)
    
    def test_integration_with_real_pdf(self):
        """Test parsing with real PDF file if available."""
        pdf_file = "raw/chase/20251104-statements-8147-.pdf"
        
        if os.path.exists(pdf_file):
            # Test validation
            is_valid = self.parser.validate_file(pdf_file)
            self.assertTrue(is_valid)
            
            # Test parsing
            transactions = self.parser.parse(pdf_file)
            self.assertGreater(len(transactions), 0)
            
            # Check first transaction has required fields
            first_txn = transactions[0]
            self.assertIsInstance(first_txn.date, datetime)
            self.assertIsInstance(first_txn.amount, Decimal)
            self.assertIsInstance(first_txn.description, str)
            self.assertEqual(first_txn.institution, "Chase")
            self.assertEqual(first_txn.account, "8147")
        else:
            self.skipTest("Real PDF file not available for testing")


if __name__ == '__main__':
    unittest.main()