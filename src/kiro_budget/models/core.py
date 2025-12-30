"""Core data models for the financial data parser."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional


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