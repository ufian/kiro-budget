"""Core data models for the financial data parser."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional


@dataclass
class AccountConfig:
    """Configuration for a single account.
    
    Attributes:
        account_id: Unique identifier for the account (e.g., last 4 digits)
        institution: Financial institution name (e.g., "firsttech", "chase")
        account_name: Human-readable account name (e.g., "Main Checking")
        account_type: Account classification - "debit" or "credit"
        description: Optional notes about the account
    """
    account_id: str
    institution: str
    account_name: str
    account_type: str  # "debit" or "credit"
    description: Optional[str] = None


@dataclass
class Transaction:
    """Unified transaction data structure"""
    date: datetime
    amount: Decimal
    description: str
    account: str
    institution: str
    transaction_id: Optional[str] = None
    category: Optional[str] = None
    balance: Optional[Decimal] = None


@dataclass
class EnrichedTransaction:
    """Transaction with account configuration applied.
    
    Extends the base Transaction with human-readable account name
    and account type from the account configuration.
    
    Attributes:
        date: Transaction date
        amount: Transaction amount
        description: Transaction description
        account: Raw account ID from source file
        institution: Financial institution name
        transaction_id: Unique transaction identifier
        category: Transaction category
        balance: Account balance after transaction
        account_name: Human-readable account name from config
        account_type: Account classification - "debit" or "credit"
    """
    date: datetime
    amount: Decimal
    description: str
    account: str
    institution: str
    transaction_id: Optional[str] = None
    category: Optional[str] = None
    balance: Optional[Decimal] = None
    account_name: str = ""
    account_type: str = "debit"


@dataclass
class ProcessingResult:
    """Result of file processing operation"""
    file_path: str
    institution: str
    transactions_count: int
    output_file: str
    processing_time: float
    errors: List[str]
    warnings: List[str]
    success: bool


@dataclass
class ParserConfig:
    """Configuration for parser behavior"""
    raw_directory: str = "raw"
    data_directory: str = "data"
    skip_processed: bool = True
    force_reprocess: bool = False
    date_formats: Optional[List[str]] = None
    institution_mappings: Optional[Dict[str, str]] = None
    column_mappings: Optional[Dict[str, Dict[str, List[str]]]] = None
    plugin_directories: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.date_formats is None:
            self.date_formats = [
                "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", 
                "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S",
                "%m/%d/%y", "%d/%m/%y", "%y-%m-%d"
            ]
        if self.institution_mappings is None:
            self.institution_mappings = {}
        if self.column_mappings is None:
            self.column_mappings = {}
        if self.plugin_directories is None:
            self.plugin_directories = []


@dataclass
class InstitutionConfig:
    """Institution-specific parsing configuration"""
    name: str
    parser_type: str
    column_mappings: Dict[str, str]
    date_format: str
    amount_format: str
    account_extraction_pattern: str
    custom_rules: Optional[Dict[str, Any]] = None