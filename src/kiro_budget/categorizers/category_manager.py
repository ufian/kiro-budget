"""
Category management system for transaction categorization.
"""

import logging
from typing import List, Dict, Optional, Set, Any
from datetime import datetime

from .models import Transaction, CategoryResult
from .storage import CategoryStorage
from .interfaces import CategoryManagerInterface


class CategoryManager(CategoryManagerInterface):
    """
    Manages category lifecycle including creation, modification, deletion,
    and hierarchical organization.
    """
    
    def __init__(self, storage: CategoryStorage):
        """
        Initialize category manager.
        
        Args:
            storage: CategoryStorage instance for persistence
        """
        self.logger = logging.getLogger(__name__)
        self.storage = storage
        
        # Cache for performance
        self._category_cache = {}
        self._hierarchy_cache = {}
        self._last_cache_update = None
    
    def add_category(self, name: str, parent: Optional[str] = None, 
                    description: Optional[str] = None) -> bool:
        """
        Add a new category with optional parent for hierarchy.
        
        Args:
            name: Category name (must be unique)
            parent: Optional parent category name
            description: Optional category description
            
        Returns:
            True if category was added successfully
        """
        try:
            # Validate category name
            if not self._validate_category_name(name):
                return False
            
            # Check if category already exists
            if self.category_exists(name):
                self.logger.warning(f"Category '{name}' already exists")
                return False
            
            # Validate parent exists if specified
            if parent and not self.category_exists(parent):
                self.logger.error(f"Parent category '{parent}' does not exist")
                return False
            
            # Add category to storage
            category_data = {
                "name": name,
                "parent": parent,
                "description": description or "",
                "created_at": datetime.now().isoformat(),
                "patterns": []
            }
            
            success = self.storage.add_category(name, category_data)
            if success:
                self._invalidate_cache()
                self.logger.info(f"Added category: {name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to add category '{name}': {e}")
            return False
    def remove_category(self, name: str, reassign_to: Optional[str] = None) -> bool:
        """
        Remove a category and optionally reassign its transactions.
        
        Args:
            name: Category name to remove
            reassign_to: Optional category to reassign transactions to
            
        Returns:
            True if category was removed successfully
        """
        try:
            # Check if category exists
            if not self.category_exists(name):
                self.logger.warning(f"Category '{name}' does not exist")
                return False
            
            # Validate reassignment target if specified
            if reassign_to and not self.category_exists(reassign_to):
                self.logger.error(f"Reassignment target '{reassign_to}' does not exist")
                return False
            
            # Check for child categories
            children = self.get_child_categories(name)
            if children:
                self.logger.error(f"Cannot remove category '{name}' - has child categories: {children}")
                return False
            
            # Remove category from storage
            success = self.storage.remove_category(name)
            if success:
                self._invalidate_cache()
                self.logger.info(f"Removed category: {name}")
                
                # TODO: Implement transaction reassignment when integrated with transaction storage
                if reassign_to:
                    self.logger.info(f"Transactions would be reassigned to: {reassign_to}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to remove category '{name}': {e}")
            return False
    
    def modify_category(self, name: str, new_name: Optional[str] = None,
                       new_parent: Optional[str] = None,
                       new_description: Optional[str] = None) -> bool:
        """
        Modify an existing category's properties.
        
        Args:
            name: Current category name
            new_name: New category name (optional)
            new_parent: New parent category (optional)
            new_description: New description (optional)
            
        Returns:
            True if category was modified successfully
        """
        try:
            # Check if category exists
            if not self.category_exists(name):
                self.logger.error(f"Category '{name}' does not exist")
                return False
            
            # Validate new name if specified
            if new_name and new_name != name:
                if not self._validate_category_name(new_name):
                    return False
                if self.category_exists(new_name):
                    self.logger.error(f"Category '{new_name}' already exists")
                    return False
            
            # Validate new parent if specified
            if new_parent and not self.category_exists(new_parent):
                self.logger.error(f"Parent category '{new_parent}' does not exist")
                return False
            
            # Check for circular hierarchy if changing parent
            if new_parent and self._would_create_circular_hierarchy(name, new_parent):
                self.logger.error(f"Cannot set '{new_parent}' as parent - would create circular hierarchy")
                return False
            
            # Get current category data
            category_data = self.storage.get_category_data(name)
            if not category_data:
                return False
            
            # Update fields
            if new_name:
                category_data["name"] = new_name
            if new_parent is not None:  # Allow setting to None (remove parent)
                category_data["parent"] = new_parent
            if new_description is not None:
                category_data["description"] = new_description
            
            category_data["modified_at"] = datetime.now().isoformat()
            
            # Update in storage
            success = self.storage.update_category(name, category_data, new_name)
            if success:
                self._invalidate_cache()
                self.logger.info(f"Modified category: {name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to modify category '{name}': {e}")
            return False
    
    def category_exists(self, name: str) -> bool:
        """Check if a category exists."""
        return self.storage.category_exists(name)
    
    def get_all_categories(self) -> List[str]:
        """Get list of all category names."""
        return self.storage.get_categories()
    
    def get_category_hierarchy(self) -> Dict[str, List[str]]:
        """
        Get category hierarchy as parent -> children mapping.
        
        Returns:
            Dictionary mapping parent categories to their children
        """
        if self._hierarchy_cache and self._is_cache_valid():
            return self._hierarchy_cache.copy()
        
        hierarchy = {}
        categories = self.storage.get_all_category_data()
        
        for name, data in categories.items():
            parent = data.get("parent")
            if parent:
                if parent not in hierarchy:
                    hierarchy[parent] = []
                hierarchy[parent].append(name)
            else:
                # Root categories
                if None not in hierarchy:
                    hierarchy[None] = []
                hierarchy[None].append(name)
        
        self._hierarchy_cache = hierarchy
        self._last_cache_update = datetime.now()
        
        return hierarchy.copy()
    
    def get_child_categories(self, parent: str) -> List[str]:
        """Get direct child categories of a parent."""
        hierarchy = self.get_category_hierarchy()
        return hierarchy.get(parent, [])
    
    def get_root_categories(self) -> List[str]:
        """Get categories with no parent (root level)."""
        hierarchy = self.get_category_hierarchy()
        return hierarchy.get(None, [])
    
    def get_category_path(self, name: str) -> List[str]:
        """
        Get full path from root to category.
        
        Args:
            name: Category name
            
        Returns:
            List of category names from root to target
        """
        if not self.category_exists(name):
            return []
        
        path = []
        current = name
        
        # Traverse up the hierarchy
        while current:
            path.insert(0, current)
            category_data = self.storage.get_category_data(current)
            if not category_data:
                break
            current = category_data.get("parent")
        
        return path
    
    def validate_hierarchy(self) -> List[str]:
        """
        Validate category hierarchy for consistency.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        categories = self.storage.get_all_category_data()
        
        for name, data in categories.items():
            parent = data.get("parent")
            if parent:
                # Check parent exists
                if not self.category_exists(parent):
                    errors.append(f"Category '{name}' has non-existent parent '{parent}'")
                
                # Check for circular references
                if self._has_circular_reference(name, set()):
                    errors.append(f"Category '{name}' has circular hierarchy reference")
        
        return errors
    
    def _validate_category_name(self, name: str) -> bool:
        """Validate category name format and content."""
        if not name or not name.strip():
            self.logger.error("Category name cannot be empty")
            return False
        
        if len(name.strip()) > 100:
            self.logger.error("Category name too long (max 100 characters)")
            return False
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in name for char in invalid_chars):
            self.logger.error(f"Category name contains invalid characters: {invalid_chars}")
            return False
        
        return True
    
    def _would_create_circular_hierarchy(self, category: str, new_parent: str) -> bool:
        """Check if setting new_parent would create circular hierarchy."""
        # Walk up from new_parent to see if we reach category
        current = new_parent
        visited = set()
        
        while current and current not in visited:
            if current == category:
                return True
            
            visited.add(current)
            category_data = self.storage.get_category_data(current)
            if not category_data:
                break
            current = category_data.get("parent")
        
        return False
    
    def _has_circular_reference(self, category: str, visited: Set[str]) -> bool:
        """Check for circular references in hierarchy."""
        if category in visited:
            return True
        
        visited.add(category)
        category_data = self.storage.get_category_data(category)
        if not category_data:
            return False
        
        parent = category_data.get("parent")
        if parent:
            return self._has_circular_reference(parent, visited.copy())
        
        return False
    
    def _invalidate_cache(self) -> None:
        """Invalidate internal caches."""
        self._category_cache.clear()
        self._hierarchy_cache.clear()
        self._last_cache_update = None
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._last_cache_update:
            return False
        
        # Cache valid for 5 minutes
        cache_age = (datetime.now() - self._last_cache_update).total_seconds()
        return cache_age < 300