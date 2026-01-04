"""
Interfaces for categorization components.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from .models import Transaction, CategoryResult, CategoryMatch


class Categorizer(ABC):
    """Abstract base class for transaction categorizers."""
    
    @abstractmethod
    def categorize(self, transaction: Transaction) -> Optional[CategoryResult]:
        """
        Categorize a single transaction.
        
        Args:
            transaction: The transaction to categorize
            
        Returns:
            CategoryResult if categorization successful, None otherwise
        """
        pass
    
    @abstractmethod
    def get_confidence_threshold(self) -> float:
        """Get the minimum confidence threshold for this categorizer."""
        pass


class PatternMatcherInterface(ABC):
    """Interface for pattern-based categorization."""
    
    @abstractmethod
    def match_patterns(self, description: str) -> Optional[CategoryMatch]:
        """
        Find the best matching pattern for a transaction description.
        
        Args:
            description: Transaction description to match
            
        Returns:
            Best CategoryMatch if found, None otherwise
        """
        pass
    
    @abstractmethod
    def add_pattern(self, category: str, pattern: str, confidence: float, 
                   specificity: str = "medium") -> None:
        """
        Add a new pattern rule.
        
        Args:
            category: Category name
            pattern: Pattern string
            confidence: Confidence score (0.0-1.0)
            specificity: Pattern specificity level
        """
        pass
    
    @abstractmethod
    def get_matching_patterns(self, description: str) -> List[CategoryMatch]:
        """
        Get all patterns that match a description.
        
        Args:
            description: Transaction description
            
        Returns:
            List of all matching CategoryMatch objects
        """
        pass


class StorageInterface(ABC):
    """Interface for category configuration storage."""
    
    @abstractmethod
    def load_categories(self) -> dict:
        """Load category configuration from storage."""
        pass
    
    @abstractmethod
    def save_categories(self, config: dict) -> None:
        """Save category configuration to storage."""
        pass
    
    @abstractmethod
    def backup_config(self) -> str:
        """Create a backup of current configuration."""
        pass


class UserInteractionInterface(ABC):
    """Interface for user interaction and learning capabilities."""
    
    @abstractmethod
    def request_manual_categorization(self, transaction: Transaction, 
                                    suggestions: List[str] = None) -> str:
        """Request manual categorization from user."""
        pass
    
    @abstractmethod
    def learn_from_feedback(self, transaction: Transaction, category: str, 
                          confidence: float = 0.9) -> None:
        """Learn from user feedback."""
        pass


class CategoryManagerInterface(ABC):
    """Interface for category management operations."""
    
    @abstractmethod
    def add_category(self, name: str, parent: Optional[str] = None, 
                    description: Optional[str] = None) -> bool:
        """Add a new category."""
        pass
    
    @abstractmethod
    def remove_category(self, name: str, reassign_to: Optional[str] = None) -> bool:
        """Remove a category."""
        pass
    
    @abstractmethod
    def modify_category(self, name: str, new_name: Optional[str] = None,
                       new_parent: Optional[str] = None,
                       new_description: Optional[str] = None) -> bool:
        """Modify an existing category."""
        pass
    
    @abstractmethod
    def category_exists(self, name: str) -> bool:
        """Check if a category exists."""
        pass
    
    @abstractmethod
    def get_all_categories(self) -> List[str]:
        """Get list of all category names."""
        pass