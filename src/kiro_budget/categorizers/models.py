"""
Core data models for transaction categorization.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import numpy as np


@dataclass
class Transaction:
    """Represents a financial transaction to be categorized."""
    date: datetime
    amount: float
    description: str
    account: str
    institution: str
    transaction_id: str
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    balance: Optional[float] = None
    source_file: Optional[str] = None


@dataclass
class CategoryResult:
    """Result of categorizing a transaction."""
    category: str
    confidence: float
    method: str  # "pattern", "ai", "ml", "manual"
    reasoning: Optional[str] = None
    
    def __post_init__(self):
        """Validate confidence score is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class CategoryMatch:
    """Represents a pattern match for categorization."""
    category: str
    pattern: str
    confidence: float
    match_type: str  # "exact", "substring", "regex", "fuzzy"
    specificity: str = "medium"  # "low", "medium", "high", "very_high"
    
    def __post_init__(self):
        """Validate confidence score and specificity."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {self.confidence}")
        
        valid_specificities = ["low", "medium", "high", "very_high"]
        if self.specificity not in valid_specificities:
            raise ValueError(f"Specificity must be one of {valid_specificities}, got {self.specificity}")


@dataclass
class PatternRule:
    """Configuration for a categorization pattern."""
    pattern: str
    confidence: float
    type: str  # "exact", "substring", "regex"
    specificity: str = "medium"  # "low", "medium", "high", "very_high"
    case_sensitive: bool = False
    
    def __post_init__(self):
        """Validate pattern rule configuration."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {self.confidence}")
        
        valid_types = ["exact", "substring", "regex"]
        if self.type not in valid_types:
            raise ValueError(f"Pattern type must be one of {valid_types}, got {self.type}")
        
        valid_specificities = ["low", "medium", "high", "very_high"]
        if self.specificity not in valid_specificities:
            raise ValueError(f"Specificity must be one of {valid_specificities}, got {self.specificity}")


@dataclass
class CategoryDefinition:
    """Definition of a spending category with its patterns."""
    patterns: list[PatternRule]
    parent_category: Optional[str] = None
    aliases: Optional[list[str]] = None
    
    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.aliases is None:
            self.aliases = []


@dataclass
class TransactionFeatures:
    """Feature representation of a transaction for ML categorization."""
    description_vector: Optional[np.ndarray] = None
    amount: Optional[float] = None
    amount_bucket: Optional[str] = None
    day_of_week: Optional[int] = None
    account_type: Optional[str] = None
    institution: Optional[str] = None