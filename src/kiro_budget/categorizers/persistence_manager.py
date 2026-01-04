"""
Data persistence and backup manager for transaction categorization.
Handles category assignments, referential integrity, and data backup/restore.
"""

import os
import json
import sqlite3
import pandas as pd
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
import logging
import hashlib

from .models import Transaction, CategoryResult


class PersistenceManager:
    """
    Manages persistence of category assignments and maintains referential integrity
    between transactions and categories.
    """
    
    def __init__(self, data_directory: str = "data", backup_directory: str = "data/backups"):
        """
        Initialize persistence manager.
        
        Args:
            data_directory: Directory containing transaction data
            backup_directory: Directory for storing backups
        """
        self.logger = logging.getLogger(__name__)
        self.data_directory = Path(data_directory)
        self.backup_directory = Path(backup_directory)
        
        # Database for category assignments
        self.db_path = self.data_directory / "categorization.db"
        
        # Ensure directories exist
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize SQLite database for category assignments."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create category assignments table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS category_assignments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_hash TEXT UNIQUE NOT NULL,
                        transaction_date TEXT NOT NULL,
                        amount REAL NOT NULL,
                        description TEXT NOT NULL,
                        account TEXT NOT NULL,
                        institution TEXT NOT NULL,
                        category TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        method TEXT NOT NULL,
                        assigned_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(transaction_hash)
                    )
                """)
                
                # Create category history table for tracking changes
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS category_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_hash TEXT NOT NULL,
                        old_category TEXT,
                        new_category TEXT NOT NULL,
                        old_confidence REAL,
                        new_confidence REAL NOT NULL,
                        old_method TEXT,
                        new_method TEXT NOT NULL,
                        changed_at TEXT NOT NULL,
                        reason TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_transaction_hash ON category_assignments(transaction_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON category_assignments(category)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON category_assignments(transaction_date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_institution ON category_assignments(institution)")
                
                conn.commit()
                self.logger.info("Category assignments database initialized")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _generate_transaction_hash(self, transaction: Transaction) -> str:
        """
        Generate a unique hash for a transaction.
        
        Args:
            transaction: Transaction object
            
        Returns:
            SHA-256 hash string
        """
        # Create a string representation of the transaction
        transaction_str = f"{transaction.date.isoformat()}|{transaction.amount}|{transaction.description}|{transaction.account}|{transaction.institution}"
        
        # Generate SHA-256 hash
        return hashlib.sha256(transaction_str.encode('utf-8')).hexdigest()
    
    def store_category_assignment(self, transaction: Transaction, result: CategoryResult, 
                                reason: Optional[str] = None) -> bool:
        """
        Store or update a category assignment for a transaction.
        
        Args:
            transaction: Transaction object
            result: CategoryResult with category assignment
            reason: Optional reason for the assignment/change
            
        Returns:
            True if stored successfully
        """
        try:
            transaction_hash = self._generate_transaction_hash(transaction)
            now = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if assignment already exists
                cursor.execute(
                    "SELECT category, confidence, method FROM category_assignments WHERE transaction_hash = ?",
                    (transaction_hash,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    old_category, old_confidence, old_method = existing
                    
                    # Only update if category actually changed
                    if old_category != result.category or abs(old_confidence - result.confidence) > 0.01:
                        # Record history
                        cursor.execute("""
                            INSERT INTO category_history 
                            (transaction_hash, old_category, new_category, old_confidence, 
                             new_confidence, old_method, new_method, changed_at, reason)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            transaction_hash, old_category, result.category,
                            old_confidence, result.confidence,
                            old_method, result.method, now, reason
                        ))
                        
                        # Update assignment
                        cursor.execute("""
                            UPDATE category_assignments 
                            SET category = ?, confidence = ?, method = ?, updated_at = ?
                            WHERE transaction_hash = ?
                        """, (result.category, result.confidence, result.method, now, transaction_hash))
                        
                        self.logger.debug(f"Updated category assignment: {old_category} -> {result.category}")
                else:
                    # Insert new assignment
                    cursor.execute("""
                        INSERT INTO category_assignments 
                        (transaction_hash, transaction_date, amount, description, account, 
                         institution, category, confidence, method, assigned_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        transaction_hash, transaction.date.isoformat(), transaction.amount,
                        transaction.description, transaction.account, transaction.institution,
                        result.category, result.confidence, result.method, now, now
                    ))
                    
                    self.logger.debug(f"Stored new category assignment: {result.category}")
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to store category assignment: {e}")
            return False
    
    def get_category_assignment(self, transaction: Transaction) -> Optional[CategoryResult]:
        """
        Get the stored category assignment for a transaction.
        
        Args:
            transaction: Transaction object
            
        Returns:
            CategoryResult if found, None otherwise
        """
        try:
            transaction_hash = self._generate_transaction_hash(transaction)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT category, confidence, method 
                    FROM category_assignments 
                    WHERE transaction_hash = ?
                """, (transaction_hash,))
                
                result = cursor.fetchone()
                if result:
                    category, confidence, method = result
                    return CategoryResult(
                        category=category,
                        confidence=confidence,
                        method=method,
                        reasoning="Retrieved from persistent storage"
                    )
                
        except Exception as e:
            self.logger.error(f"Failed to get category assignment: {e}")
        
        return None
    
    def batch_store_assignments(self, assignments: List[Tuple[Transaction, CategoryResult]], 
                              reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Store multiple category assignments in batch.
        
        Args:
            assignments: List of (transaction, result) tuples
            reason: Optional reason for the assignments
            
        Returns:
            Dictionary with batch operation results
        """
        stats = {
            'total': len(assignments),
            'stored': 0,
            'updated': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                for transaction, result in assignments:
                    try:
                        transaction_hash = self._generate_transaction_hash(transaction)
                        
                        # Check if assignment exists
                        cursor.execute(
                            "SELECT category, confidence, method FROM category_assignments WHERE transaction_hash = ?",
                            (transaction_hash,)
                        )
                        existing = cursor.fetchone()
                        
                        if existing:
                            old_category, old_confidence, old_method = existing
                            
                            if old_category != result.category or abs(old_confidence - result.confidence) > 0.01:
                                # Record history
                                cursor.execute("""
                                    INSERT INTO category_history 
                                    (transaction_hash, old_category, new_category, old_confidence, 
                                     new_confidence, old_method, new_method, changed_at, reason)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    transaction_hash, old_category, result.category,
                                    old_confidence, result.confidence,
                                    old_method, result.method, now, reason
                                ))
                                
                                # Update assignment
                                cursor.execute("""
                                    UPDATE category_assignments 
                                    SET category = ?, confidence = ?, method = ?, updated_at = ?
                                    WHERE transaction_hash = ?
                                """, (result.category, result.confidence, result.method, now, transaction_hash))
                                
                                stats['updated'] += 1
                        else:
                            # Insert new assignment
                            cursor.execute("""
                                INSERT INTO category_assignments 
                                (transaction_hash, transaction_date, amount, description, account, 
                                 institution, category, confidence, method, assigned_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                transaction_hash, transaction.date.isoformat(), transaction.amount,
                                transaction.description, transaction.account, transaction.institution,
                                result.category, result.confidence, result.method, now, now
                            ))
                            
                            stats['stored'] += 1
                            
                    except Exception as e:
                        stats['failed'] += 1
                        stats['errors'].append(f"Failed to store assignment for {transaction.description}: {e}")
                
                conn.commit()
                self.logger.info(f"Batch stored {stats['stored']} new and updated {stats['updated']} category assignments")
                
        except Exception as e:
            self.logger.error(f"Failed batch store operation: {e}")
            stats['errors'].append(f"Batch operation failed: {e}")
        
        return stats
    
    def update_csv_with_categories(self, csv_path: str, output_path: Optional[str] = None) -> bool:
        """
        Update a CSV file with stored category assignments.
        
        Args:
            csv_path: Path to the CSV file to update
            output_path: Optional output path (defaults to overwriting input)
            
        Returns:
            True if successful
        """
        if not os.path.exists(csv_path):
            self.logger.error(f"CSV file not found: {csv_path}")
            return False
        
        if output_path is None:
            output_path = csv_path
        
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            df['date'] = pd.to_datetime(df['date'])
            
            # Add category columns if they don't exist
            if 'category' not in df.columns:
                df['category'] = 'Uncategorized'
            if 'category_confidence' not in df.columns:
                df['category_confidence'] = 0.0
            if 'category_method' not in df.columns:
                df['category_method'] = 'none'
            
            # Update with stored assignments
            updated_count = 0
            
            with sqlite3.connect(self.db_path) as conn:
                for idx, row in df.iterrows():
                    # Create transaction hash
                    transaction_str = f"{row['date'].isoformat()}|{row['amount']}|{row['description']}|{row['account']}|{row['institution']}"
                    transaction_hash = hashlib.sha256(transaction_str.encode('utf-8')).hexdigest()
                    
                    # Look up assignment
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT category, confidence, method 
                        FROM category_assignments 
                        WHERE transaction_hash = ?
                    """, (transaction_hash,))
                    
                    result = cursor.fetchone()
                    if result:
                        category, confidence, method = result
                        df.at[idx, 'category'] = category
                        df.at[idx, 'category_confidence'] = confidence
                        df.at[idx, 'category_method'] = method
                        updated_count += 1
            
            # Save updated CSV
            df.to_csv(output_path, index=False)
            self.logger.info(f"Updated {updated_count} transactions in CSV file: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update CSV with categories: {e}")
            return False
    
    def reassign_category_transactions(self, old_category: str, new_category: str) -> int:
        """
        Reassign all transactions from one category to another.
        
        Args:
            old_category: Current category name
            new_category: New category name
            
        Returns:
            Number of transactions reassigned
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                # Get all transactions with the old category
                cursor.execute("""
                    SELECT transaction_hash, confidence, method 
                    FROM category_assignments 
                    WHERE category = ?
                """, (old_category,))
                
                transactions = cursor.fetchall()
                
                if not transactions:
                    return 0
                
                # Record history for all changes
                for transaction_hash, confidence, method in transactions:
                    cursor.execute("""
                        INSERT INTO category_history 
                        (transaction_hash, old_category, new_category, old_confidence, 
                         new_confidence, old_method, new_method, changed_at, reason)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        transaction_hash, old_category, new_category,
                        confidence, confidence, method, method, now,
                        f"Category reassignment: {old_category} -> {new_category}"
                    ))
                
                # Update all assignments
                cursor.execute("""
                    UPDATE category_assignments 
                    SET category = ?, updated_at = ?
                    WHERE category = ?
                """, (new_category, now, old_category))
                
                conn.commit()
                
                reassigned_count = len(transactions)
                self.logger.info(f"Reassigned {reassigned_count} transactions from '{old_category}' to '{new_category}'")
                return reassigned_count
                
        except Exception as e:
            self.logger.error(f"Failed to reassign category transactions: {e}")
            return 0
    
    def get_category_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored category assignments.
        
        Returns:
            Dictionary with category statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total assignments
                cursor.execute("SELECT COUNT(*) FROM category_assignments")
                total_assignments = cursor.fetchone()[0]
                
                # Category distribution
                cursor.execute("""
                    SELECT category, COUNT(*) as count, AVG(confidence) as avg_confidence
                    FROM category_assignments 
                    GROUP BY category 
                    ORDER BY count DESC
                """)
                category_distribution = [
                    {'category': row[0], 'count': row[1], 'avg_confidence': row[2]}
                    for row in cursor.fetchall()
                ]
                
                # Method distribution
                cursor.execute("""
                    SELECT method, COUNT(*) as count 
                    FROM category_assignments 
                    GROUP BY method 
                    ORDER BY count DESC
                """)
                method_distribution = dict(cursor.fetchall())
                
                # Recent activity (last 30 days)
                thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM category_assignments 
                    WHERE assigned_at >= ?
                """, (thirty_days_ago,))
                recent_assignments = cursor.fetchone()[0]
                
                # History count
                cursor.execute("SELECT COUNT(*) FROM category_history")
                total_changes = cursor.fetchone()[0]
                
                return {
                    'total_assignments': total_assignments,
                    'total_changes': total_changes,
                    'recent_assignments': recent_assignments,
                    'category_distribution': category_distribution,
                    'method_distribution': method_distribution
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get category statistics: {e}")
            return {}
    
    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """
        Create a backup of the category assignments database.
        
        Args:
            backup_name: Optional custom backup name
            
        Returns:
            Path to the created backup file
        """
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"categorization_backup_{timestamp}.db"
        
        backup_path = self.backup_directory / backup_name
        
        try:
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            # Also backup any CSV files with categories
            csv_backup_dir = self.backup_directory / f"csv_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            csv_backup_dir.mkdir(exist_ok=True)
            
            # Find CSV files with category columns
            for csv_file in self.data_directory.rglob("*.csv"):
                try:
                    df = pd.read_csv(csv_file, nrows=1)  # Just read header
                    if 'category' in df.columns:
                        # Copy CSV file to backup
                        backup_csv_path = csv_backup_dir / csv_file.name
                        shutil.copy2(csv_file, backup_csv_path)
                except Exception:
                    continue  # Skip files that can't be read
            
            self.logger.info(f"Created backup: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            raise
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore category assignments from a backup.
        
        Args:
            backup_path: Path to the backup file
            
        Returns:
            True if successful
        """
        if not os.path.exists(backup_path):
            self.logger.error(f"Backup file not found: {backup_path}")
            return False
        
        try:
            # Create backup of current database
            current_backup = self.create_backup("pre_restore_backup.db")
            self.logger.info(f"Created backup of current database: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, self.db_path)
            
            self.logger.info(f"Restored category assignments from backup: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            return False
    
    def cleanup_old_backups(self, days_to_keep: int = 30) -> int:
        """
        Clean up old backup files.
        
        Args:
            days_to_keep: Number of days of backups to keep
            
        Returns:
            Number of files cleaned up
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cleaned_count = 0
        
        try:
            for backup_file in self.backup_directory.glob("*.db"):
                try:
                    file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        backup_file.unlink()
                        cleaned_count += 1
                        self.logger.debug(f"Cleaned up old backup: {backup_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up backup {backup_file}: {e}")
            
            # Also clean up old CSV backup directories
            for backup_dir in self.backup_directory.glob("csv_backup_*"):
                try:
                    dir_time = datetime.fromtimestamp(backup_dir.stat().st_mtime)
                    if dir_time < cutoff_date:
                        shutil.rmtree(backup_dir)
                        cleaned_count += 1
                        self.logger.debug(f"Cleaned up old CSV backup directory: {backup_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up backup directory {backup_dir}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} old backup files")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old backups: {e}")
            return 0
    
    def validate_referential_integrity(self) -> Dict[str, Any]:
        """
        Validate referential integrity between transactions and categories.
        
        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check for orphaned history records
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM category_history h 
                    LEFT JOIN category_assignments a ON h.transaction_hash = a.transaction_hash 
                    WHERE a.transaction_hash IS NULL
                """)
                orphaned_history = cursor.fetchone()[0]
                
                if orphaned_history > 0:
                    warnings.append(f"Found {orphaned_history} orphaned history records")
                
                # Check for invalid confidence scores
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM category_assignments 
                    WHERE confidence < 0 OR confidence > 1
                """)
                invalid_confidence = cursor.fetchone()[0]
                
                if invalid_confidence > 0:
                    issues.append(f"Found {invalid_confidence} assignments with invalid confidence scores")
                
                # Check for empty categories
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM category_assignments 
                    WHERE category IS NULL OR category = ''
                """)
                empty_categories = cursor.fetchone()[0]
                
                if empty_categories > 0:
                    issues.append(f"Found {empty_categories} assignments with empty categories")
                
                # Check for duplicate transaction hashes
                cursor.execute("""
                    SELECT transaction_hash, COUNT(*) 
                    FROM category_assignments 
                    GROUP BY transaction_hash 
                    HAVING COUNT(*) > 1
                """)
                duplicates = cursor.fetchall()
                
                if duplicates:
                    issues.append(f"Found {len(duplicates)} duplicate transaction hashes")
        
        except Exception as e:
            issues.append(f"Failed to validate referential integrity: {e}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    def repair_referential_integrity(self) -> Dict[str, Any]:
        """
        Attempt to repair referential integrity issues.
        
        Returns:
            Dictionary with repair results
        """
        repairs = []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Remove orphaned history records
                cursor.execute("""
                    DELETE FROM category_history 
                    WHERE transaction_hash NOT IN (
                        SELECT transaction_hash FROM category_assignments
                    )
                """)
                orphaned_removed = cursor.rowcount
                if orphaned_removed > 0:
                    repairs.append(f"Removed {orphaned_removed} orphaned history records")
                
                # Fix invalid confidence scores
                cursor.execute("""
                    UPDATE category_assignments 
                    SET confidence = CASE 
                        WHEN confidence < 0 THEN 0.0
                        WHEN confidence > 1 THEN 1.0
                        ELSE confidence
                    END
                    WHERE confidence < 0 OR confidence > 1
                """)
                confidence_fixed = cursor.rowcount
                if confidence_fixed > 0:
                    repairs.append(f"Fixed {confidence_fixed} invalid confidence scores")
                
                # Fix empty categories
                cursor.execute("""
                    UPDATE category_assignments 
                    SET category = 'Uncategorized'
                    WHERE category IS NULL OR category = ''
                """)
                empty_fixed = cursor.rowcount
                if empty_fixed > 0:
                    repairs.append(f"Fixed {empty_fixed} empty categories")
                
                conn.commit()
                
        except Exception as e:
            repairs.append(f"Error during repair: {e}")
        
        return {
            'repairs_made': repairs,
            'total_repairs': len(repairs)
        }