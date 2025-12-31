#!/usr/bin/env python3
"""
Build a consolidated CSV file from all processed transaction data.

This script combines all processed CSV files from the data/ directory into a single
total.csv file, removing duplicates and sorting by date.
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from kiro_budget.utils.duplicate_detector import DuplicateDetector


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def find_all_csv_files(data_dir: str) -> list:
    """Find all CSV files in the data directory."""
    csv_files = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")
    
    # Recursively find all CSV files
    for csv_file in data_path.rglob("*.csv"):
        # Skip the total CSV files if they already exist
        if csv_file.name not in ["total.csv", "all_transactions.csv"]:
            csv_files.append(str(csv_file))
    
    return sorted(csv_files)


def load_and_combine_csv_files(csv_files: list, logger) -> pd.DataFrame:
    """Load and combine all CSV files into a single DataFrame."""
    all_transactions = []
    
    for csv_file in csv_files:
        try:
            logger.info(f"Loading {csv_file}")
            df = pd.read_csv(csv_file)
            
            # Add source file information
            df['source_file'] = os.path.basename(csv_file)
            
            all_transactions.append(df)
            logger.info(f"  Loaded {len(df)} transactions")
            
        except Exception as e:
            logger.error(f"Error loading {csv_file}: {e}")
            continue
    
    if not all_transactions:
        raise ValueError("No valid CSV files found to combine")
    
    # Combine all DataFrames
    combined_df = pd.concat(all_transactions, ignore_index=True)
    logger.info(f"Combined {len(combined_df)} total transactions from {len(csv_files)} files")
    
    return combined_df


def clean_and_deduplicate(df: pd.DataFrame, logger) -> pd.DataFrame:
    """Clean the data and remove duplicates."""
    logger.info("Cleaning and deduplicating data...")
    
    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Convert amount to numeric
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    # Remove rows with invalid amounts
    initial_count = len(df)
    df = df.dropna(subset=['amount'])
    if len(df) < initial_count:
        logger.info(f"  Removed {initial_count - len(df)} transactions with invalid amounts")
    
    # Sort by date, then by amount, then by description for consistent ordering
    df = df.sort_values(['date', 'amount', 'description'], ascending=[True, True, True])
    
    # Remove duplicates based on key fields
    # We consider transactions duplicates if they have the same date, amount, description, and account
    duplicate_cols = ['date', 'amount', 'description', 'account', 'institution']
    initial_count = len(df)
    df = df.drop_duplicates(subset=duplicate_cols, keep='first')
    
    duplicates_removed = initial_count - len(df)
    if duplicates_removed > 0:
        logger.info(f"  Removed {duplicates_removed} duplicate transactions")
    
    # Reset index
    df = df.reset_index(drop=True)
    
    return df


def add_summary_statistics(df: pd.DataFrame, logger) -> dict:
    """Calculate and log summary statistics."""
    stats = {
        'total_transactions': len(df),
        'date_range': {
            'start': df['date'].min().strftime('%Y-%m-%d'),
            'end': df['date'].max().strftime('%Y-%m-%d')
        },
        'institutions': df['institution'].value_counts().to_dict(),
        'account_types': df['account_type'].value_counts().to_dict() if 'account_type' in df.columns else {},
        'total_spending': float(df[df['amount'] < 0]['amount'].sum()),
        'total_income': float(df[df['amount'] > 0]['amount'].sum()),
        'net_amount': float(df['amount'].sum())
    }
    
    logger.info("Summary Statistics:")
    logger.info(f"  Total transactions: {stats['total_transactions']:,}")
    logger.info(f"  Date range: {stats['date_range']['start']} to {stats['date_range']['end']}")
    logger.info(f"  Total spending: ${abs(stats['total_spending']):,.2f}")
    logger.info(f"  Total income: ${stats['total_income']:,.2f}")
    logger.info(f"  Net amount: ${stats['net_amount']:,.2f}")
    
    logger.info("Transactions by institution:")
    for institution, count in stats['institutions'].items():
        logger.info(f"  {institution}: {count:,} transactions")
    
    return stats


def save_total_csv(df: pd.DataFrame, output_file: str, logger):
    """Save the combined DataFrame to a CSV file."""
    logger.info(f"Saving combined data to {output_file}")
    
    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    logger.info(f"Successfully saved {len(df)} transactions to {output_file}")


def main():
    """Main function to build the total CSV file."""
    logger = setup_logging()
    
    # Set up paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    data_dir = project_root / "data"
    output_file = data_dir / "total" / "all_transactions.csv"
    
    try:
        logger.info("Building total CSV file from all processed transactions...")
        
        # Find all CSV files
        csv_files = find_all_csv_files(str(data_dir))
        logger.info(f"Found {len(csv_files)} CSV files to combine")
        
        if not csv_files:
            logger.error("No CSV files found in data directory")
            return 1
        
        # Load and combine all CSV files
        combined_df = load_and_combine_csv_files(csv_files, logger)
        
        # Clean and deduplicate
        cleaned_df = clean_and_deduplicate(combined_df, logger)
        
        # Calculate statistics
        stats = add_summary_statistics(cleaned_df, logger)
        
        # Save the combined file
        save_total_csv(cleaned_df, str(output_file), logger)
        
        # Save statistics as well
        stats_file = output_file.parent / "total_stats.json"
        import json
        with open(stats_file, 'w') as f:
            # Convert datetime objects to strings for JSON serialization
            json_stats = stats.copy()
            json.dump(json_stats, f, indent=2, default=str)
        logger.info(f"Saved statistics to {stats_file}")
        
        logger.info("Total CSV build completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Error building total CSV: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())