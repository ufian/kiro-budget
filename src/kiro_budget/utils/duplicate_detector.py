"""Transaction duplicate detection and merging utilities."""

import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
from ..models.core import Transaction


class DuplicateDetector:
    """Detects and handles duplicate transactions across multiple sources"""
    
    def __init__(self, date_tolerance_days: int = 3, amount_tolerance: float = 0.01):
        """
        Initialize duplicate detector
        
        Args:
            date_tolerance_days: Number of days tolerance for date matching (increased to 3 for posting vs transaction dates)
            amount_tolerance: Amount tolerance for fuzzy matching (absolute value)
        """
        self.date_tolerance_days = date_tolerance_days
        self.amount_tolerance = amount_tolerance
    
    def detect_duplicates(self, transactions: List[Transaction], ignore_transaction_ids: bool = False) -> Dict[str, List[Transaction]]:
        """
        Detect duplicate transactions and group them
        
        Args:
            transactions: List of all transactions to check
            ignore_transaction_ids: If True, use fuzzy matching even for transactions with IDs
            
        Returns:
            Dictionary mapping signature to list of duplicate transactions
        """
        # Group transactions by signature
        signature_groups = {}
        
        for transaction in transactions:
            signature = self._generate_transaction_signature(transaction, ignore_transaction_id=ignore_transaction_ids)
            
            if signature not in signature_groups:
                signature_groups[signature] = []
            
            signature_groups[signature].append(transaction)
        
        # For fuzzy matching (when ignoring transaction IDs), validate date tolerance
        if ignore_transaction_ids:
            validated_groups = {}
            for signature, group in signature_groups.items():
                if len(group) > 1:
                    # Cluster transactions by date proximity
                    date_clusters = self._validate_date_tolerance_in_group(group)
                    for sub_sig, cluster in date_clusters.items():
                        # Create unique signature combining original sig and date cluster
                        unique_sig = f"{signature}_{sub_sig}"
                        validated_groups[unique_sig] = cluster
            return validated_groups
        else:
            # Return only groups with duplicates
            return {sig: txns for sig, txns in signature_groups.items() if len(txns) > 1}
    
    def _validate_date_tolerance_in_group(self, transactions: List[Transaction]) -> Dict[str, List[Transaction]]:
        """
        Cluster transactions by date proximity and return groups of duplicates.
        
        Transactions with the same signature but different dates (beyond tolerance)
        are separate transactions, not duplicates. This method clusters them
        so that only transactions within date_tolerance_days of each other
        are considered duplicates.
        
        Args:
            transactions: List of transactions with the same signature
            
        Returns:
            Dictionary mapping sub-signature to list of duplicate transactions
        """
        if len(transactions) <= 1:
            return {}
        
        # Sort by date for clustering
        sorted_txns = sorted(transactions, key=lambda t: t.date)
        
        # Cluster transactions by date proximity
        clusters = []
        current_cluster = [sorted_txns[0]]
        
        for txn in sorted_txns[1:]:
            # Check if this transaction is within tolerance of any in current cluster
            in_cluster = False
            for cluster_txn in current_cluster:
                date_diff = abs((txn.date - cluster_txn.date).days)
                if date_diff <= self.date_tolerance_days:
                    in_cluster = True
                    break
            
            if in_cluster:
                current_cluster.append(txn)
            else:
                # Start a new cluster
                if len(current_cluster) > 1:
                    clusters.append(current_cluster)
                current_cluster = [txn]
        
        # Don't forget the last cluster
        if len(current_cluster) > 1:
            clusters.append(current_cluster)
        
        # Convert clusters to dictionary with unique sub-signatures
        result = {}
        for i, cluster in enumerate(clusters):
            # Use the first transaction's date to create a unique sub-signature
            sub_sig = f"cluster_{cluster[0].date.strftime('%Y%m%d')}_{i}"
            result[sub_sig] = cluster
        
        return result
    
    def merge_duplicate_transactions(self, duplicate_groups: Dict[str, List[Transaction]]) -> List[Transaction]:
        """
        Merge duplicate transactions, keeping the best version of each
        
        Args:
            duplicate_groups: Dictionary of duplicate transaction groups
            
        Returns:
            List of merged transactions (one per group)
        """
        merged_transactions = []
        
        for signature, duplicates in duplicate_groups.items():
            merged_transaction = self._merge_transaction_group(duplicates)
            merged_transactions.append(merged_transaction)
        
        return merged_transactions
    
    def deduplicate_transactions(self, transactions: List[Transaction], use_fuzzy_matching: bool = True) -> Tuple[List[Transaction], Dict[str, int]]:
        """
        Remove duplicates from transaction list and return statistics
        
        Args:
            transactions: List of transactions to deduplicate
            use_fuzzy_matching: If True, use fuzzy matching instead of transaction IDs
            
        Returns:
            Tuple of (deduplicated_transactions, duplicate_stats)
        """
        duplicate_groups = self.detect_duplicates(transactions, ignore_transaction_ids=use_fuzzy_matching)
        
        if not duplicate_groups:
            return transactions, {}
        
        # Get unique transactions (not in any duplicate group)
        duplicate_transaction_ids = set()
        for group in duplicate_groups.values():
            for txn in group:
                duplicate_transaction_ids.add(id(txn))
        
        unique_transactions = [
            txn for txn in transactions 
            if id(txn) not in duplicate_transaction_ids
        ]
        
        # Add merged duplicates
        merged_duplicates = self.merge_duplicate_transactions(duplicate_groups)
        
        # Combine unique and merged transactions
        final_transactions = unique_transactions + merged_duplicates
        
        # Generate statistics
        stats = {
            'total_input_transactions': len(transactions),
            'duplicate_groups_found': len(duplicate_groups),
            'total_duplicates_removed': len(transactions) - len(final_transactions),
            'final_transaction_count': len(final_transactions)
        }
        
        return final_transactions, stats
    
    def find_cross_file_duplicates(self, transactions_by_file: Dict[str, List[Transaction]]) -> Dict[str, Dict[str, List[Transaction]]]:
        """
        Find duplicates across multiple files using fuzzy matching
        
        Args:
            transactions_by_file: Dictionary mapping file paths to transaction lists
            
        Returns:
            Dictionary mapping file paths to their duplicate groups
        """
        # Combine all transactions with source file tracking
        all_transactions = []
        transaction_to_file = {}
        
        for file_path, transactions in transactions_by_file.items():
            for txn in transactions:
                all_transactions.append(txn)
                transaction_to_file[id(txn)] = file_path
        
        # Detect duplicates across all transactions using fuzzy matching (ignore transaction IDs)
        duplicate_groups = self.detect_duplicates(all_transactions, ignore_transaction_ids=True)
        
        # Group duplicates by source file
        file_duplicates = {}
        for file_path in transactions_by_file.keys():
            file_duplicates[file_path] = {}
        
        for signature, duplicates in duplicate_groups.items():
            # Group duplicates by their source files
            files_in_group = set()
            for txn in duplicates:
                files_in_group.add(transaction_to_file[id(txn)])
            
            # Only consider cross-file duplicates
            if len(files_in_group) > 1:
                for file_path in files_in_group:
                    file_transactions = [
                        txn for txn in duplicates 
                        if transaction_to_file[id(txn)] == file_path
                    ]
                    if file_transactions:
                        file_duplicates[file_path][signature] = file_transactions
        
        return file_duplicates
    
    def _generate_transaction_signature(self, transaction: Transaction, ignore_transaction_id: bool = False) -> str:
        """
        Generate a signature for transaction matching
        
        Args:
            transaction: Transaction to generate signature for
            ignore_transaction_id: If True, always use fuzzy matching instead of transaction ID
        
        Uses multiple strategies:
        1. Transaction ID if available and not ignored (most reliable)
        2. Amount + description hash (fuzzy matching - excludes date for flexibility)
        """
        # Strategy 1: Use transaction ID if available and not ignored
        if transaction.transaction_id and not ignore_transaction_id:
            return f"id:{transaction.transaction_id}"
        
        # Strategy 2: Generate signature from key fields (excluding date for flexibility)
        # Normalize description for better matching
        description = self._normalize_description(transaction.description or "")
        
        # Create signature components (exclude date to allow for posting vs transaction date differences)
        amount_str = f"{abs(transaction.amount):.2f}"  # Use absolute value
        account_str = transaction.account or ""
        
        # Create hash of normalized components (without date)
        signature_data = f"{amount_str}|{description}|{account_str}"
        signature_hash = hashlib.md5(signature_data.encode('utf-8')).hexdigest()[:12]
        
        return f"sig:{signature_hash}"
    
    def _normalize_description(self, description: str) -> str:
        """Normalize transaction description for better matching"""
        if not description:
            return ""
        
        # Convert to lowercase and remove extra whitespace
        normalized = description.lower().strip()
        
        # Remove common variations that don't affect matching
        replacements = [
            # Remove location codes and reference numbers
            (r'\s+\d{2,}\s*$', ''),  # Trailing numbers
            (r'\s+[A-Z]{2}\s*$', ''),  # Trailing state codes like "WA", "CA"
            (r'\s+#\d+', ''),  # Store numbers like "#0658"
            (r'\*[A-Z0-9]+', ''),  # Reference codes like "*NK9M63AJ1"
            (r'\s+amzn\.com/bill\s+wa\s*$', ''),  # Amazon billing location
            # Normalize common merchant name variations
            (r'\s+&\s+', ' and '),
            (r'\s+llc\s*$', ''),
            (r'\s+inc\s*$', ''),
            (r'\s+co\s*$', ''),
            # Remove city/state information at the end
            (r'\s+[a-z]+\s+wa\s*$', ''),  # " bellevue wa", " redmond wa", etc.
            (r'\s+[a-z]+\s+[a-z]{2}\s*$', ''),  # " city st" format
            # Normalize common patterns
            (r'tst\*', ''),  # Remove "TST*" prefix
            (r'sq \*', ''),  # Remove "SQ *" prefix
            (r'amazon\.com\*', 'amazon '),  # Normalize Amazon formats
            (r'amazon mktpl\*', 'amazon '),  # Normalize Amazon marketplace
        ]
        
        import re
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def _merge_transaction_group(self, transactions: List[Transaction]) -> Transaction:
        """
        Merge a group of duplicate transactions into a single best version
        
        Priority order:
        1. Transaction with transaction_id (QFX/OFX data)
        2. Transaction with most complete data
        3. Most recent transaction
        """
        if len(transactions) == 1:
            return transactions[0]
        
        # Sort by priority
        def transaction_priority(txn):
            score = 0
            
            # Prefer transactions with transaction_id
            if txn.transaction_id:
                score += 1000
            
            # Prefer transactions with more complete data
            if txn.category:
                score += 100
            if txn.balance is not None:
                score += 50
            if txn.description and len(txn.description) > 10:
                score += 25
            
            # Prefer more recent processing (assuming later in list = more recent)
            score += transactions.index(txn)
            
            return score
        
        # Get the best transaction
        best_transaction = max(transactions, key=transaction_priority)
        
        # Merge additional data from other transactions if missing
        merged = Transaction(
            date=best_transaction.date,
            amount=best_transaction.amount,
            description=best_transaction.description,
            account=best_transaction.account,
            institution=best_transaction.institution,
            transaction_id=best_transaction.transaction_id,
            category=best_transaction.category,
            balance=best_transaction.balance
        )
        
        # Fill in missing data from other transactions
        for txn in transactions:
            if not merged.description and txn.description:
                merged.description = txn.description
            if not merged.category and txn.category:
                merged.category = txn.category
            if merged.balance is None and txn.balance is not None:
                merged.balance = txn.balance
            if not merged.transaction_id and txn.transaction_id:
                merged.transaction_id = txn.transaction_id
        
        return merged
    
    def _transactions_match(self, txn1: Transaction, txn2: Transaction) -> bool:
        """
        Check if two transactions are likely duplicates using fuzzy matching
        """
        # Check transaction IDs first (exact match required)
        if txn1.transaction_id and txn2.transaction_id:
            return txn1.transaction_id == txn2.transaction_id
        
        # Check date tolerance
        date_diff = abs((txn1.date - txn2.date).days)
        if date_diff > self.date_tolerance_days:
            return False
        
        # Check amount tolerance
        amount_diff = abs(txn1.amount - txn2.amount)
        if amount_diff > self.amount_tolerance:
            return False
        
        # Check account match
        if txn1.account != txn2.account:
            return False
        
        # Check description similarity
        desc1 = self._normalize_description(txn1.description or "")
        desc2 = self._normalize_description(txn2.description or "")
        
        if desc1 and desc2:
            # Simple similarity check - could be enhanced with fuzzy string matching
            return desc1 == desc2
        
        return True


class TransactionMerger:
    """Handles merging transactions from multiple sources for the same account/period"""
    
    def __init__(self, duplicate_detector: Optional[DuplicateDetector] = None):
        self.duplicate_detector = duplicate_detector or DuplicateDetector()
    
    def merge_files_for_account(self, transactions_by_file: Dict[str, List[Transaction]], 
                               account: str, institution: str) -> Tuple[List[Transaction], Dict]:
        """
        Merge transactions from multiple files for the same account
        
        Args:
            transactions_by_file: Dictionary mapping file paths to transaction lists
            account: Account identifier to merge
            institution: Institution name
            
        Returns:
            Tuple of (merged_transactions, merge_statistics)
        """
        # Filter transactions for the specific account
        account_transactions_by_file = {}
        for file_path, transactions in transactions_by_file.items():
            account_txns = [
                txn for txn in transactions 
                if txn.account == account and txn.institution.lower() == institution.lower()
            ]
            if account_txns:
                account_transactions_by_file[file_path] = account_txns
        
        if not account_transactions_by_file:
            return [], {'error': 'No transactions found for specified account'}
        
        if len(account_transactions_by_file) == 1:
            # Only one file, no merging needed
            file_path, transactions = next(iter(account_transactions_by_file.items()))
            return transactions, {
                'files_merged': 1,
                'source_files': [file_path],
                'duplicates_removed': 0,
                'final_count': len(transactions)
            }
        
        # Combine all transactions
        all_transactions = []
        source_files = []
        for file_path, transactions in account_transactions_by_file.items():
            all_transactions.extend(transactions)
            source_files.append(file_path)
        
        # Deduplicate using fuzzy matching for cross-file scenarios
        merged_transactions, dedup_stats = self.duplicate_detector.deduplicate_transactions(all_transactions, use_fuzzy_matching=True)
        
        # Sort by date
        merged_transactions.sort(key=lambda x: x.date)
        
        merge_stats = {
            'files_merged': len(account_transactions_by_file),
            'source_files': source_files,
            'duplicates_removed': dedup_stats.get('total_duplicates_removed', 0),
            'final_count': len(merged_transactions),
            'original_total': len(all_transactions)
        }
        
        return merged_transactions, merge_stats
    
    def identify_mergeable_accounts(self, transactions_by_file: Dict[str, List[Transaction]]) -> Dict[Tuple[str, str], List[str]]:
        """
        Identify accounts that appear in multiple files and can be merged
        
        Args:
            transactions_by_file: Dictionary mapping file paths to transaction lists
            
        Returns:
            Dictionary mapping (account, institution) tuples to list of file paths
        """
        account_files = {}
        
        for file_path, transactions in transactions_by_file.items():
            for txn in transactions:
                key = (txn.account, txn.institution.lower())
                if key not in account_files:
                    account_files[key] = []
                if file_path not in account_files[key]:
                    account_files[key].append(file_path)
        
        # Return only accounts that appear in multiple files
        return {key: files for key, files in account_files.items() if len(files) > 1}