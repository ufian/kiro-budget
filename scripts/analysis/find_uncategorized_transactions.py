#!/usr/bin/env python3
"""
Find and analyze uncategorized transactions.

This script reads the categorized transaction CSV file and extracts all transactions
that are marked as "Uncategorized" to help identify patterns for new categorization rules.
"""

import os
import sys
import pandas as pd
from pathlib import Path
from collections import Counter
import re
from datetime import datetime


def load_transactions(csv_file: str) -> pd.DataFrame:
    """Load transactions from CSV file."""
    print(f"Loading transactions from {csv_file}")
    
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"Transaction file not found: {csv_file}")
    
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} total transactions")
    
    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    return df


def analyze_uncategorized_transactions(df: pd.DataFrame):
    """Analyze uncategorized transactions to identify patterns."""
    # Filter uncategorized transactions
    uncategorized = df[df['category'] == 'Uncategorized'].copy()
    
    print(f"\nUncategorized Transactions Analysis")
    print("=" * 50)
    print(f"Total uncategorized: {len(uncategorized):,} ({len(uncategorized)/len(df)*100:.1f}%)")
    
    if len(uncategorized) == 0:
        print("No uncategorized transactions found!")
        return uncategorized
    
    # Amount analysis
    print(f"\nAmount Statistics:")
    print(f"  Total amount: ${uncategorized['amount'].sum():,.2f}")
    print(f"  Average amount: ${uncategorized['amount'].mean():.2f}")
    print(f"  Median amount: ${uncategorized['amount'].median():.2f}")
    print(f"  Min amount: ${uncategorized['amount'].min():.2f}")
    print(f"  Max amount: ${uncategorized['amount'].max():.2f}")
    
    # Date range analysis
    print(f"\nDate Range:")
    print(f"  Earliest: {uncategorized['date'].min().strftime('%Y-%m-%d')}")
    print(f"  Latest: {uncategorized['date'].max().strftime('%Y-%m-%d')}")
    
    # Institution analysis
    print(f"\nBy Institution:")
    institution_counts = uncategorized['institution'].value_counts()
    for institution, count in institution_counts.head(10).items():
        print(f"  {institution}: {count:,} ({count/len(uncategorized)*100:.1f}%)")
    
    # Account analysis
    print(f"\nBy Account:")
    account_counts = uncategorized['account'].value_counts()
    for account, count in account_counts.head(10).items():
        print(f"  {account}: {count:,} ({count/len(uncategorized)*100:.1f}%)")
    
    return uncategorized


def extract_merchant_patterns(uncategorized: pd.DataFrame):
    """Extract and analyze merchant patterns from descriptions."""
    print(f"\nMerchant Pattern Analysis")
    print("=" * 50)
    
    # Clean and extract potential merchant names
    merchants = []
    for desc in uncategorized['description']:
        if pd.isna(desc):
            continue
        
        desc = str(desc).upper().strip()
        
        # Remove common prefixes/suffixes
        desc = re.sub(r'^(DEBIT|CREDIT|ACH|ONLINE|MOBILE|ATM|POS)\s+', '', desc)
        desc = re.sub(r'\s+(DEBIT|CREDIT|PURCHASE|PAYMENT|TRANSFER)$', '', desc)
        
        # Extract first few words (likely merchant name)
        words = desc.split()
        if len(words) >= 1:
            # Take first 1-3 words as potential merchant
            merchant = ' '.join(words[:min(3, len(words))])
            merchants.append(merchant)
    
    # Count merchant occurrences
    merchant_counts = Counter(merchants)
    
    print(f"Top 50 Uncategorized Merchants:")
    print("-" * 80)
    print(f"{'Merchant':<50} {'Count':<8} {'%':<6}")
    print("-" * 80)
    
    for merchant, count in merchant_counts.most_common(50):
        percentage = count / len(uncategorized) * 100
        print(f"{merchant:<50} {count:<8} {percentage:<6.1f}")
    
    return merchant_counts


def suggest_categorization_patterns(uncategorized: pd.DataFrame, merchant_counts: Counter):
    """Suggest potential categorization patterns based on merchant analysis."""
    print(f"\nSuggested Categorization Patterns")
    print("=" * 50)
    
    # Common patterns to look for
    patterns = {
        'Restaurants': [
            r'.*RESTAURANT.*', r'.*CAFE.*', r'.*COFFEE.*', r'.*PIZZA.*',
            r'.*BURGER.*', r'.*TACO.*', r'.*SUSHI.*', r'.*DINER.*',
            r'.*GRILL.*', r'.*BISTRO.*', r'.*BAR.*', r'.*PUB.*'
        ],
        'Groceries': [
            r'.*GROCERY.*', r'.*MARKET.*', r'.*SUPERMARKET.*', r'.*FOOD.*',
            r'.*PRODUCE.*', r'.*DELI.*'
        ],
        'Gas': [
            r'.*GAS.*', r'.*FUEL.*', r'.*PETRO.*', r'.*STATION.*'
        ],
        'Shopping': [
            r'.*STORE.*', r'.*SHOP.*', r'.*RETAIL.*', r'.*MALL.*',
            r'.*OUTLET.*', r'.*BOUTIQUE.*'
        ],
        'Healthcare': [
            r'.*MEDICAL.*', r'.*HOSPITAL.*', r'.*CLINIC.*', r'.*DOCTOR.*',
            r'.*DENTAL.*', r'.*PHARMACY.*', r'.*HEALTH.*'
        ],
        'Transportation': [
            r'.*UBER.*', r'.*LYFT.*', r'.*TAXI.*', r'.*TRANSIT.*',
            r'.*PARKING.*', r'.*TOLL.*', r'.*METRO.*'
        ],
        'Utilities': [
            r'.*ELECTRIC.*', r'.*POWER.*', r'.*WATER.*', r'.*SEWER.*',
            r'.*INTERNET.*', r'.*CABLE.*', r'.*PHONE.*'
        ],
        'Entertainment': [
            r'.*THEATER.*', r'.*CINEMA.*', r'.*MOVIE.*', r'.*NETFLIX.*',
            r'.*SPOTIFY.*', r'.*GAMING.*', r'.*ENTERTAINMENT.*'
        ]
    }
    
    suggestions = {}
    
    for category, category_patterns in patterns.items():
        matches = []
        for merchant, count in merchant_counts.most_common(100):  # Check top 100
            for pattern in category_patterns:
                if re.search(pattern, merchant):
                    matches.append((merchant, count))
                    break
        
        if matches:
            suggestions[category] = matches
    
    # Print suggestions
    for category, matches in suggestions.items():
        if matches:
            print(f"\n{category}:")
            for merchant, count in matches[:10]:  # Show top 10 matches
                print(f"  {merchant} ({count} transactions)")
    
    return suggestions


def save_uncategorized_report(uncategorized: pd.DataFrame, output_file: str):
    """Save uncategorized transactions to a CSV file for manual review."""
    print(f"\nSaving uncategorized transactions to {output_file}")
    
    # Sort by amount (largest first) and then by date
    uncategorized_sorted = uncategorized.sort_values(['amount', 'date'], ascending=[False, False])
    
    # Select relevant columns for review
    columns_to_save = [
        'date', 'amount', 'description', 'institution', 'account',
        'category', 'category_confidence', 'category_method'
    ]
    
    # Ensure all columns exist
    available_columns = [col for col in columns_to_save if col in uncategorized_sorted.columns]
    
    uncategorized_sorted[available_columns].to_csv(output_file, index=False)
    print(f"Saved {len(uncategorized_sorted)} uncategorized transactions")


def main():
    """Main function to analyze uncategorized transactions."""
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
        # Default output file
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        output_file = project_root / "data" / "reports" / "uncategorized_transactions.csv"
    
    try:
        print("Analyzing uncategorized transactions...")
        print(f"Input file: {input_file}")
        print(f"Output file: {output_file}")
        
        # Load transactions
        df = load_transactions(str(input_file))
        
        # Analyze uncategorized transactions
        uncategorized = analyze_uncategorized_transactions(df)
        
        if len(uncategorized) > 0:
            # Extract merchant patterns
            merchant_counts = extract_merchant_patterns(uncategorized)
            
            # Suggest categorization patterns
            suggest_categorization_patterns(uncategorized, merchant_counts)
            
            # Save uncategorized transactions for manual review
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            save_uncategorized_report(uncategorized, str(output_file))
        
        print("\nUncategorized transaction analysis completed!")
        return 0
        
    except Exception as e:
        print(f"Error analyzing uncategorized transactions: {e}")
        import traceback
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())