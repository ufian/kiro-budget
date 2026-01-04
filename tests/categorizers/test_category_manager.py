"""
Tests for CategoryManager class.
"""

import tempfile
from unittest.mock import MagicMock

import pytest

from kiro_budget.categorizers.category_manager import CategoryManager
from kiro_budget.categorizers.storage import CategoryStorage


class TestCategoryManager:
    """Test CategoryManager functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = f"{self.temp_dir}/test_categories.yaml"
        
        self.storage = CategoryStorage(self.config_path)
        self.category_manager = CategoryManager(self.storage)
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test CategoryManager initialization."""
        assert self.category_manager.storage == self.storage
        assert self.category_manager._category_cache == {}
        assert self.category_manager._hierarchy_cache == {}
        assert self.category_manager._last_cache_update is None
    
    def test_add_category_success(self):
        """Test successful category addition."""
        result = self.category_manager.add_category("TestCategory", description="Test description")
        
        assert result is True
        assert self.category_manager.category_exists("TestCategory")
        
        # Check category data
        category_data = self.storage.get_category_data("TestCategory")
        assert category_data["name"] == "TestCategory"
        assert category_data["description"] == "Test description"
        assert category_data["parent"] is None
        assert "created_at" in category_data
    
    def test_add_category_with_parent(self):
        """Test adding category with parent."""
        # Add parent first
        self.category_manager.add_category("Parent")
        
        # Add child
        result = self.category_manager.add_category("Child", parent="Parent")
        
        assert result is True
        assert self.category_manager.category_exists("Child")
        
        category_data = self.storage.get_category_data("Child")
        assert category_data["parent"] == "Parent"
    
    def test_add_category_duplicate(self):
        """Test adding duplicate category."""
        self.category_manager.add_category("TestCategory")
        
        # Try to add same category again
        result = self.category_manager.add_category("TestCategory")
        
        assert result is False
    
    def test_add_category_invalid_parent(self):
        """Test adding category with non-existent parent."""
        result = self.category_manager.add_category("Child", parent="NonExistentParent")
        
        assert result is False
        assert not self.category_manager.category_exists("Child")
    
    def test_add_category_invalid_name(self):
        """Test adding category with invalid name."""
        # Empty name
        result = self.category_manager.add_category("")
        assert result is False
        
        # Name with invalid characters
        result = self.category_manager.add_category("Invalid/Name")
        assert result is False
        
        # Name too long
        long_name = "x" * 101
        result = self.category_manager.add_category(long_name)
        assert result is False
    
    def test_remove_category_success(self):
        """Test successful category removal."""
        self.category_manager.add_category("TestCategory")
        
        result = self.category_manager.remove_category("TestCategory")
        
        assert result is True
        assert not self.category_manager.category_exists("TestCategory")
    
    def test_remove_category_nonexistent(self):
        """Test removing non-existent category."""
        result = self.category_manager.remove_category("NonExistent")
        
        assert result is False
    
    def test_remove_category_with_children(self):
        """Test removing category that has children."""
        self.category_manager.add_category("Parent")
        self.category_manager.add_category("Child", parent="Parent")
        
        result = self.category_manager.remove_category("Parent")
        
        assert result is False  # Should fail because it has children
        assert self.category_manager.category_exists("Parent")
    
    def test_modify_category_name(self):
        """Test modifying category name."""
        self.category_manager.add_category("OldName")
        
        result = self.category_manager.modify_category("OldName", new_name="NewName")
        
        assert result is True
        assert not self.category_manager.category_exists("OldName")
        assert self.category_manager.category_exists("NewName")
    
    def test_modify_category_parent(self):
        """Test modifying category parent."""
        self.category_manager.add_category("Parent")
        self.category_manager.add_category("Child")
        
        result = self.category_manager.modify_category("Child", new_parent="Parent")
        
        assert result is True
        
        category_data = self.storage.get_category_data("Child")
        assert category_data["parent"] == "Parent"
    
    def test_modify_category_description(self):
        """Test modifying category description."""
        self.category_manager.add_category("TestCategory")
        
        result = self.category_manager.modify_category("TestCategory", new_description="New description")
        
        assert result is True
        
        category_data = self.storage.get_category_data("TestCategory")
        assert category_data["description"] == "New description"
    
    def test_modify_category_nonexistent(self):
        """Test modifying non-existent category."""
        result = self.category_manager.modify_category("NonExistent", new_name="NewName")
        
        assert result is False
    
    def test_modify_category_circular_hierarchy(self):
        """Test preventing circular hierarchy."""
        self.category_manager.add_category("Parent")
        self.category_manager.add_category("Child", parent="Parent")
        
        # Try to make Parent a child of Child (circular)
        result = self.category_manager.modify_category("Parent", new_parent="Child")
        
        assert result is False
    
    def test_get_category_hierarchy(self):
        """Test getting category hierarchy."""
        # Create hierarchy: Root -> Parent -> Child
        self.category_manager.add_category("Root")
        self.category_manager.add_category("Parent", parent="Root")
        self.category_manager.add_category("Child", parent="Parent")
        self.category_manager.add_category("Orphan")  # No parent
        
        hierarchy = self.category_manager.get_category_hierarchy()
        
        assert "Root" in hierarchy
        assert "Parent" in hierarchy["Root"]
        assert "Child" in hierarchy["Parent"]
        assert "Orphan" in hierarchy[None]  # Root level
    
    def test_get_child_categories(self):
        """Test getting child categories."""
        self.category_manager.add_category("Parent")
        self.category_manager.add_category("Child1", parent="Parent")
        self.category_manager.add_category("Child2", parent="Parent")
        
        children = self.category_manager.get_child_categories("Parent")
        
        assert len(children) == 2
        assert "Child1" in children
        assert "Child2" in children
    
    def test_get_root_categories(self):
        """Test getting root categories."""
        self.category_manager.add_category("Root1")
        self.category_manager.add_category("Root2")
        self.category_manager.add_category("Child", parent="Root1")
        
        roots = self.category_manager.get_root_categories()
        
        assert len(roots) == 2
        assert "Root1" in roots
        assert "Root2" in roots
        assert "Child" not in roots
    
    def test_get_category_path(self):
        """Test getting category path."""
        self.category_manager.add_category("Root")
        self.category_manager.add_category("Parent", parent="Root")
        self.category_manager.add_category("Child", parent="Parent")
        
        path = self.category_manager.get_category_path("Child")
        
        assert path == ["Root", "Parent", "Child"]
    
    def test_get_category_path_nonexistent(self):
        """Test getting path for non-existent category."""
        path = self.category_manager.get_category_path("NonExistent")
        
        assert path == []
    
    def test_validate_hierarchy_valid(self):
        """Test hierarchy validation with valid hierarchy."""
        self.category_manager.add_category("Parent")
        self.category_manager.add_category("Child", parent="Parent")
        
        errors = self.category_manager.validate_hierarchy()
        
        assert len(errors) == 0
    
    def test_validate_hierarchy_invalid_parent(self):
        """Test hierarchy validation with invalid parent reference."""
        # Manually create invalid configuration
        self.storage.add_category("Child", {
            "name": "Child",
            "parent": "NonExistentParent",
            "description": "",
            "patterns": []
        })
        
        errors = self.category_manager.validate_hierarchy()
        
        assert len(errors) > 0
        assert "non-existent parent" in errors[0].lower()
    
    def test_cache_invalidation(self):
        """Test that cache is invalidated on modifications."""
        self.category_manager.add_category("TestCategory")
        
        # Access hierarchy to populate cache
        hierarchy = self.category_manager.get_category_hierarchy()
        assert self.category_manager._hierarchy_cache
        
        # Modify category - should invalidate cache
        self.category_manager.add_category("AnotherCategory")
        assert not self.category_manager._hierarchy_cache
    
    def test_validate_category_name(self):
        """Test category name validation."""
        # Valid names
        assert self.category_manager._validate_category_name("ValidName")
        assert self.category_manager._validate_category_name("Valid Name")
        assert self.category_manager._validate_category_name("Valid-Name_123")
        
        # Invalid names
        assert not self.category_manager._validate_category_name("")
        assert not self.category_manager._validate_category_name("   ")
        assert not self.category_manager._validate_category_name("Invalid/Name")
        assert not self.category_manager._validate_category_name("Invalid\\Name")
        assert not self.category_manager._validate_category_name("Invalid:Name")
        assert not self.category_manager._validate_category_name("x" * 101)  # Too long


class TestCategoryManagerIntegration:
    """Integration tests for CategoryManager with real storage."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = f"{self.temp_dir}/test_categories.yaml"
        
        self.storage = CategoryStorage(self.config_path)
        self.category_manager = CategoryManager(self.storage)
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_persistence_across_instances(self):
        """Test that categories persist across CategoryManager instances."""
        # Add category with first instance
        self.category_manager.add_category("PersistentCategory", description="Test")
        
        # Create new instance
        new_manager = CategoryManager(CategoryStorage(self.config_path))
        
        # Should still exist
        assert new_manager.category_exists("PersistentCategory")
        
        category_data = new_manager.storage.get_category_data("PersistentCategory")
        assert category_data["description"] == "Test"
    
    def test_complex_hierarchy_operations(self):
        """Test complex hierarchy operations."""
        # Build complex hierarchy
        categories = [
            ("Expenses", None),
            ("Fixed", "Expenses"),
            ("Variable", "Expenses"),
            ("Housing", "Fixed"),
            ("Utilities", "Fixed"),
            ("Food", "Variable"),
            ("Entertainment", "Variable"),
            ("Groceries", "Food"),
            ("Restaurants", "Food")
        ]
        
        for name, parent in categories:
            result = self.category_manager.add_category(name, parent=parent)
            assert result is True
        
        # Test hierarchy structure
        hierarchy = self.category_manager.get_category_hierarchy()
        
        # Check root
        assert "Expenses" in hierarchy[None]
        
        # Check second level
        assert "Fixed" in hierarchy["Expenses"]
        assert "Variable" in hierarchy["Expenses"]
        
        # Check third level
        assert "Housing" in hierarchy["Fixed"]
        assert "Utilities" in hierarchy["Fixed"]
        assert "Food" in hierarchy["Variable"]
        assert "Entertainment" in hierarchy["Variable"]
        
        # Check fourth level
        assert "Groceries" in hierarchy["Food"]
        assert "Restaurants" in hierarchy["Food"]
        
        # Test paths
        assert self.category_manager.get_category_path("Groceries") == ["Expenses", "Variable", "Food", "Groceries"]
        assert self.category_manager.get_category_path("Housing") == ["Expenses", "Fixed", "Housing"]