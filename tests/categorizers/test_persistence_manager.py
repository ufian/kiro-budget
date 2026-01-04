"""
Tests for the categorization persistence manager.
"""

import os
import tempfile
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from kiro_budget.categorizers.persistence_manager import PersistenceManager
from kiro_budget.categorizers.models import Transaction, CategoryResult


class TestPersistenceManager:
    """Test cases for PersistenceManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.backup_dir = os.path.join(self.temp_dir, "backups")
        
        # Create test persistence manager
        self.persistence_manager = PersistenceManager(
            data_directory=self.temp_dir,
            backup_directory=self.backup_dir
        )
        
        # Create test transaction
        self.test_transaction = Transaction(
            date=datetime(2024, 1, 15),
            amount=-50.00,
            description="TEST MERCHANT #123",
            account="1234",
            institution="Test Bank",
            transaction_id="test_001"
        )
        
        # Create test category result
        self.test_result = CategoryResult(
            category="Test Category",
            confidence=0.85,
            method="pattern",
            reasoning="Test pattern match"
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test persistence manager initialization."""
        assert os.path.exists(self.temp_dir)
        assert os.path.exists(self.backup_dir)
        assert os.path.exists(self.persistence_manager.db_path)
    
    def test_store_category_assignment(self):
        """Test storing a category assignment."""
        success = self.persistence_manager.store_category_assignment(
            self.test_transaction, self.test_result
        )
        
        assert success is True
        
        # Verify storage
        retrieved_result = self.persistence_manager.get_category_assignment(self.test_transaction)
        assert retrieved_result is not None
        assert retrieved_result.category == "Test Category"
        assert retrieved_result.confidence == 0.85
        assert retrieved_result.method == "pattern"
    
    def test_update_category_assignment(self):
        """Test updating an existing category assignment."""
        # Store initial assignment
        self.persistence_manager.store_category_assignment(
            self.test_transaction, self.test_result
        )
        
        # Update with new result
        updated_result = CategoryResult(
            category="Updated Category",
            confidence=0.95,
            method="ai",
            reasoning="AI categorization"
        )
        
        success = self.persistence_manager.store_category_assignment(
            self.test_transaction, updated_result, reason="Manual correction"
        )
        
        assert success is True
        
        # Verify update
        retrieved_result = self.persistence_manager.get_category_assignment(self.test_transaction)
        assert retrieved_result.category == "Updated Category"
        assert retrieved_result.confidence == 0.95
        assert retrieved_result.method == "ai"
    
    def test_batch_store_assignments(self):
        """Test batch storing of category assignments."""
        # Create multiple test transactions
        transactions = []
        results = []
        
        for i in range(5):
            transaction = Transaction(
                date=datetime(2024, 1, 15 + i),
                amount=-25.00 * (i + 1),
                description=f"BATCH TEST {i}",
                account="1234",
                institution="Test Bank",
                transaction_id=f"batch_{i}"
            )
            
            result = CategoryResult(
                category=f"Category {i}",
                confidence=0.8 + (i * 0.02),
                method="pattern",
                reasoning=f"Batch test {i}"
            )
            
            transactions.append(transaction)
            results.append(result)
        
        # Batch store
        assignments = list(zip(transactions, results))
        stats = self.persistence_manager.batch_store_assignments(
            assignments, reason="Batch test"
        )
        
        assert stats['total'] == 5
        assert stats['stored'] == 5
        assert stats['failed'] == 0
        
        # Verify all stored
        for transaction in transactions:
            retrieved = self.persistence_manager.get_category_assignment(transaction)
            assert retrieved is not None
    
    def test_transaction_hash_generation(self):
        """Test transaction hash generation consistency."""
        # Same transaction should generate same hash
        hash1 = self.persistence_manager._generate_transaction_hash(self.test_transaction)
        hash2 = self.persistence_manager._generate_transaction_hash(self.test_transaction)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
        
        # Different transaction should generate different hash
        different_transaction = Transaction(
            date=datetime(2024, 1, 16),  # Different date
            amount=-50.00,
            description="TEST MERCHANT #123",
            account="1234",
            institution="Test Bank",
            transaction_id="test_002"
        )
        
        hash3 = self.persistence_manager._generate_transaction_hash(different_transaction)
        assert hash1 != hash3
    
    def test_get_nonexistent_assignment(self):
        """Test retrieving non-existent category assignment."""
        result = self.persistence_manager.get_category_assignment(self.test_transaction)
        assert result is None
    
    def test_update_csv_with_categories(self):
        """Test updating CSV file with category assignments."""
        # Create test CSV
        csv_data = {
            'date': ['2024-01-15', '2024-01-16'],
            'amount': [-50.00, -25.00],
            'description': ['TEST MERCHANT #123', 'ANOTHER MERCHANT'],
            'account': ['1234', '1234'],
            'institution': ['Test Bank', 'Test Bank']
        }
        
        df = pd.DataFrame(csv_data)
        df['date'] = pd.to_datetime(df['date'])
        
        csv_path = os.path.join(self.temp_dir, "test_transactions.csv")
        df.to_csv(csv_path, index=False)
        
        # Store category assignment for first transaction
        self.persistence_manager.store_category_assignment(
            self.test_transaction, self.test_result
        )
        
        # Update CSV
        success = self.persistence_manager.update_csv_with_categories(csv_path)
        assert success is True
        
        # Verify CSV update
        updated_df = pd.read_csv(csv_path)
        assert 'category' in updated_df.columns
        assert 'category_confidence' in updated_df.columns
        assert 'category_method' in updated_df.columns
        
        # First row should have category
        assert updated_df.iloc[0]['category'] == 'Test Category'
        assert updated_df.iloc[0]['category_confidence'] == 0.85
        
        # Second row should be uncategorized
        assert updated_df.iloc[1]['category'] == 'Uncategorized'
    
    def test_reassign_category_transactions(self):
        """Test reassigning transactions from one category to another."""
        # Store multiple transactions with same category
        transactions = []
        for i in range(3):
            transaction = Transaction(
                date=datetime(2024, 1, 15 + i),
                amount=-30.00,
                description=f"OLD CATEGORY MERCHANT {i}",
                account="1234",
                institution="Test Bank",
                transaction_id=f"reassign_{i}"
            )
            
            result = CategoryResult(
                category="Old Category",
                confidence=0.8,
                method="pattern",
                reasoning="Old pattern"
            )
            
            self.persistence_manager.store_category_assignment(transaction, result)
            transactions.append(transaction)
        
        # Reassign category
        reassigned_count = self.persistence_manager.reassign_category_transactions(
            "Old Category", "New Category"
        )
        
        assert reassigned_count == 3
        
        # Verify reassignment
        for transaction in transactions:
            retrieved = self.persistence_manager.get_category_assignment(transaction)
            assert retrieved.category == "New Category"
    
    def test_get_category_statistics(self):
        """Test getting category statistics."""
        # Store some test assignments
        categories = ["Groceries", "Gas", "Restaurants"]
        for i, category in enumerate(categories):
            transaction = Transaction(
                date=datetime(2024, 1, 15 + i),
                amount=-40.00,
                description=f"{category.upper()} MERCHANT",
                account="1234",
                institution="Test Bank",
                transaction_id=f"stats_{i}"
            )
            
            result = CategoryResult(
                category=category,
                confidence=0.9,
                method="pattern",
                reasoning="Stats test"
            )
            
            self.persistence_manager.store_category_assignment(transaction, result)
        
        # Get statistics
        stats = self.persistence_manager.get_category_statistics()
        
        assert stats['total_assignments'] == 3
        assert len(stats['category_distribution']) == 3
        assert stats['method_distribution']['pattern'] == 3
        assert stats['recent_assignments'] == 3  # All are recent
    
    def test_create_and_restore_backup(self):
        """Test creating and restoring backups."""
        # Store some data
        self.persistence_manager.store_category_assignment(
            self.test_transaction, self.test_result
        )
        
        # Create backup
        backup_path = self.persistence_manager.create_backup()
        assert os.path.exists(backup_path)
        
        # Modify data
        updated_result = CategoryResult(
            category="Modified Category",
            confidence=0.95,
            method="manual",
            reasoning="Manual update"
        )
        self.persistence_manager.store_category_assignment(
            self.test_transaction, updated_result
        )
        
        # Verify modification
        retrieved = self.persistence_manager.get_category_assignment(self.test_transaction)
        assert retrieved.category == "Modified Category"
        
        # Restore backup
        success = self.persistence_manager.restore_backup(backup_path)
        assert success is True
        
        # Verify restoration
        retrieved = self.persistence_manager.get_category_assignment(self.test_transaction)
        assert retrieved.category == "Test Category"
    
    def test_cleanup_old_backups(self):
        """Test cleaning up old backup files."""
        # Create some backup files with different ages
        import time
        
        # Create current backup
        backup1 = self.persistence_manager.create_backup("current_backup.db")
        
        # Create old backup by modifying file timestamp
        backup2 = self.persistence_manager.create_backup("old_backup.db")
        old_time = time.time() - (40 * 24 * 60 * 60)  # 40 days ago
        os.utime(backup2, (old_time, old_time))
        
        # Cleanup backups older than 30 days
        cleaned_count = self.persistence_manager.cleanup_old_backups(30)
        
        assert cleaned_count >= 1
        assert os.path.exists(backup1)  # Current backup should remain
        assert not os.path.exists(backup2)  # Old backup should be removed
    
    def test_validate_referential_integrity(self):
        """Test validating referential integrity."""
        # Store valid data
        self.persistence_manager.store_category_assignment(
            self.test_transaction, self.test_result
        )
        
        # Validate integrity
        validation = self.persistence_manager.validate_referential_integrity()
        
        assert validation['valid'] is True
        assert len(validation['issues']) == 0
    
    def test_repair_referential_integrity(self):
        """Test repairing referential integrity issues."""
        # This test would require manually corrupting the database
        # For now, just test that the repair function runs without error
        repair_result = self.persistence_manager.repair_referential_integrity()
        
        assert 'repairs_made' in repair_result
        assert 'total_repairs' in repair_result
    
    def test_nonexistent_csv_update(self):
        """Test updating non-existent CSV file."""
        success = self.persistence_manager.update_csv_with_categories("nonexistent.csv")
        assert success is False
    
    def test_nonexistent_backup_restore(self):
        """Test restoring from non-existent backup."""
        success = self.persistence_manager.restore_backup("nonexistent.db")
        assert success is False
    
    def test_empty_batch_store(self):
        """Test batch storing with empty list."""
        stats = self.persistence_manager.batch_store_assignments([])
        
        assert stats['total'] == 0
        assert stats['stored'] == 0
        assert stats['failed'] == 0
    
    def test_reassign_nonexistent_category(self):
        """Test reassigning non-existent category."""
        count = self.persistence_manager.reassign_category_transactions(
            "NonexistentCategory", "NewCategory"
        )
        
        assert count == 0