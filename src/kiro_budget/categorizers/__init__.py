"""
Transaction categorization module.

This module provides intelligent categorization of financial transactions using
multiple approaches: pattern matching, AI-powered categorization, and machine learning.
"""

from .models import Transaction, CategoryResult, CategoryMatch, PatternRule, CategoryDefinition
from .interfaces import Categorizer, PatternMatcherInterface, StorageInterface
from .pattern_matcher import PatternMatcher
from .storage import CategoryStorage
from .ai_categorizer import AICategorizer
from .ml_categorizer import MLCategorizer
from .category_engine import CategoryEngine

__all__ = [
    'Transaction',
    'CategoryResult', 
    'CategoryMatch',
    'PatternRule',
    'CategoryDefinition',
    'Categorizer',
    'PatternMatcherInterface',
    'StorageInterface',
    'PatternMatcher',
    'CategoryStorage',
    'AICategorizer',
    'MLCategorizer',
    'CategoryEngine',
]