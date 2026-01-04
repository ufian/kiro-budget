#!/usr/bin/env python3
"""
Add category information to consolidated transaction CSV file.

This script reads the consolidated all_transactions.csv file, applies categorization
to each transaction, and saves the result with category information included.
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from typing import Optional

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from kiro_budget.categorizers.category_engine import CategoryEngine
from kiro_budget.categorizers.models import Transaction


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def load_transactions_csv(csv_file: str, logger) -> pd.DataFrame:
    """Load transactions from CSV file."""
    logger.info(f"Loading transactions from {csv_file}")
    
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"Transaction file not found: {csv_file}")
    
    df = pd.read_csv(csv_file)
    logger.info(f"Loaded {len(df)} transactions")
    
    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    return df


def categorize_transactions(df: pd.DataFrame, category_engine: CategoryEngine, logger) -> pd.DataFrame:
    """Apply categorization to all transactions in the DataFrame."""
    logger.info("Categorizing transactions...")
    
    # Add category columns
    df['category'] = 'Uncategorized'
    df['category_confidence'] = 0.0
    df['category_method'] = 'none'
    
    categorization_stats = {
        'total': len(df),
        'categorized': 0,
        'uncategorized': 0,
        'by_method': {},
        'by_category': {}
    }
    
    # Process transactions in batches for better performance
    batch_size = 1000
    for i in range(0, len(df), batch_size):
        batch_end = min(i + batch_size, len(df))
        logger.info(f"Processing batch {i//batch_size + 1}: transactions {i+1}-{batch_end}")
        
        for idx in range(i, batch_end):
            row = df.iloc[idx]
            
            # Create Transaction object
            transaction = Transaction(
                date=row['date'],
                amount=float(row['amount']),
                description=str(row['description']),
                account=str(row.get('account', '')),
                institution=str(row.get('institution', '')),
                transaction_id=f"csv_{idx}"
            )
            
            # Categorize transaction
            result = category_engine.categorize_transaction(transaction)
            
            # Update DataFrame
            df.at[idx, 'category'] = result.category
            df.at[idx, 'category_confidence'] = result.confidence
            df.at[idx, 'category_method'] = result.method
            
            # Update statistics
            if result.category != 'Uncategorized':
                categorization_stats['categorized'] += 1
            else:
                categorization_stats['uncategorized'] += 1
            
            # Track by method
            method = result.method
            if method not in categorization_stats['by_method']:
                categorization_stats['by_method'][method] = 0
            categorization_stats['by_method'][method] += 1
            
            # Track by category
            category = result.category
            if category not in categorization_stats['by_category']:
                categorization_stats['by_category'][category] = 0
            categorization_stats['by_category'][category] += 1
    
    # Log statistics
    logger.info("Categorization completed!")
    logger.info(f"  Total transactions: {categorization_stats['total']:,}")
    logger.info(f"  Categorized: {categorization_stats['categorized']:,} ({categorization_stats['categorized']/categorization_stats['total']*100:.1f}%)")
    logger.info(f"  Uncategorized: {categorization_stats['uncategorized']:,} ({categorization_stats['uncategorized']/categorization_stats['total']*100:.1f}%)")
    
    logger.info("Categorization by method:")
    for method, count in sorted(categorization_stats['by_method'].items()):
        logger.info(f"  {method}: {count:,} ({count/categorization_stats['total']*100:.1f}%)")
    
    logger.info("Top 10 categories:")
    top_categories = sorted(categorization_stats['by_category'].items(), key=lambda x: x[1], reverse=True)[:10]
    for category, count in top_categories:
        logger.info(f"  {category}: {count:,} ({count/categorization_stats['total']*100:.1f}%)")
    
    return df


def save_categorized_csv(df: pd.DataFrame, output_file: str, logger):
    """Save the categorized DataFrame to a CSV file."""
    logger.info(f"Saving categorized data to {output_file}")
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Reorder columns to put category information after core transaction data
    core_columns = ['date', 'amount', 'description', 'account', 'institution']
    category_columns = ['category', 'category_confidence', 'category_method']
    
    # Get remaining columns
    remaining_columns = [col for col in df.columns if col not in core_columns + category_columns]
    
    # Reorder
    ordered_columns = core_columns + category_columns + remaining_columns
    df = df[ordered_columns]
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    logger.info(f"Successfully saved {len(df)} categorized transactions to {output_file}")


def main():
    """Main function to add categories to CSV file."""
    logger = setup_logging()
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # Default input file
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        input_file = project_root / "data" / "total" / "all_transactions.csv"
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        # Default output file (overwrite input)
        output_file = input_file
    
    # Category configuration file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    categories_file = project_root / "categories.yaml"
    
    try:
        logger.info("Adding categories to transaction CSV file...")
        logger.info(f"Input file: {input_file}")
        logger.info(f"Output file: {output_file}")
        logger.info(f"Categories file: {categories_file}")
        
        # Initialize category engine
        logger.info("Initializing category engine...")
        category_engine = CategoryEngine(str(categories_file), enable_persistence=False)
        
        # Load transactions
        df = load_transactions_csv(str(input_file), logger)
        
        # Apply categorization
        categorized_df = categorize_transactions(df, category_engine, logger)
        
        # Save categorized data
        save_categorized_csv(categorized_df, str(output_file), logger)
        
        logger.info("Category addition completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Error adding categories to CSV: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())