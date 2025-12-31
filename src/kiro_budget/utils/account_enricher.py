"""Account enricher for adding account metadata to transactions."""

import logging
from typing import List

from ..models.core import AccountConfig, EnrichedTransaction, Transaction
from .account_config import AccountConfigLoader


logger = logging.getLogger(__name__)


class AccountEnricher:
    """Enriches transactions with account configuration data.
    
    Uses AccountConfigLoader to look up account metadata and applies it
    to transactions, creating EnrichedTransaction objects with account_name
    and account_type fields populated.
    
    Example:
        loader = AccountConfigLoader("raw/accounts.yaml")
        loader.load()
        enricher = AccountEnricher(loader)
        
        enriched = enricher.enrich(transaction)
        enriched_batch = enricher.enrich_batch(transactions)
    """
    
    DEFAULT_ACCOUNT_TYPE = "debit"
    
    def __init__(self, config_loader: AccountConfigLoader):
        """Initialize the account enricher.
        
        Args:
            config_loader: AccountConfigLoader instance for looking up
                          account configurations.
        """
        self.config_loader = config_loader
    
    def enrich(self, transaction: Transaction) -> EnrichedTransaction:
        """Add account_name and account_type to a transaction.
        
        Looks up the account configuration using the transaction's institution
        and account fields. If a matching configuration is found, uses the
        configured account_name and account_type. Otherwise, applies defaults.
        
        Args:
            transaction: The transaction to enrich.
            
        Returns:
            EnrichedTransaction with account_name and account_type populated.
            
        Requirements: 3.1, 3.2, 3.4
        """
        # Look up account config using (institution, account_id) pair
        config = self.config_loader.get_account(
            institution=transaction.institution,
            account_id=transaction.account
        )
        
        if config is not None:
            # Use configured values (Requirements 3.1, 3.2)
            account_name = config.account_name
            account_type = config.account_type
            logger.debug(
                f"Enriched transaction with config: "
                f"{transaction.institution}/{transaction.account} -> "
                f"{account_name} ({account_type})"
            )
        else:
            # Apply defaults for unconfigured accounts (Requirement 3.3)
            account_name = transaction.account
            account_type = self.DEFAULT_ACCOUNT_TYPE
            logger.debug(
                f"No config found for {transaction.institution}/{transaction.account}, "
                f"using defaults: {account_name} ({account_type})"
            )
        
        return EnrichedTransaction(
            date=transaction.date,
            amount=transaction.amount,
            description=transaction.description,
            account=transaction.account,
            institution=transaction.institution,
            transaction_id=transaction.transaction_id,
            category=transaction.category,
            balance=transaction.balance,
            account_name=account_name,
            account_type=account_type
        )
    
    def enrich_batch(
        self, 
        transactions: List[Transaction]
    ) -> List[EnrichedTransaction]:
        """Enrich multiple transactions.
        
        Applies account enrichment to each transaction in the list.
        
        Args:
            transactions: List of transactions to enrich.
            
        Returns:
            List of EnrichedTransaction objects with account metadata applied.
            
        Requirements: 3.1, 3.2, 3.4
        """
        return [self.enrich(txn) for txn in transactions]
