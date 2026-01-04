#!/usr/bin/env python3
"""
Interactive categorization tool for uncategorized transactions.

This script groups uncategorized transactions by merchant patterns and presents
them to the user for manual categorization decisions.
"""

import os
import sys
import pandas as pd
from pathlib import Path
from collections import defaultdict, Counter
import re
from datetime import datetime
import yaml


def load_transactions(csv_file: str) -> pd.DataFrame:
    """Load transactions from CSV file."""
    print(f"Loading transactions from {csv_file}")
    
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"Transaction file not found: {csv_file}")
    
    df = pd.read_csv(csv_file)
    df['date'] = pd.to_datetime(df['date'])
    
    return df


def load_existing_categories(categories_file: str) -> dict:
    """Load existing categories from YAML file."""
    if not os.path.exists(categories_file):
        return {}
    
    with open(categories_file, 'r') as f:
        config = yaml.safe_load(f)
    
    return list(config.get('categories', {}).keys()) if config else []


def extract_merchant_name(description: str) -> str:
    """Extract a clean merchant name from transaction description."""
    if pd.isna(description):
        return "UNKNOWN"
    
    desc = str(description).upper().strip()
    
    # Remove common prefixes/suffixes
    desc = re.sub(r'^(DEBIT|CREDIT|ACH|ONLINE|MOBILE|ATM|POS)\s+', '', desc)
    desc = re.sub(r'\s+(DEBIT|CREDIT|PURCHASE|PAYMENT|TRANSFER)$', '', desc)
    
    # Remove transaction IDs and reference numbers
    desc = re.sub(r'\s+\d{10,}.*$', '', desc)  # Remove long numbers at end
    desc = re.sub(r'\s+[A-Z0-9]{8,}.*$', '', desc)  # Remove reference codes
    
    # Extract first few meaningful words
    words = desc.split()
    if len(words) >= 1:
        # Take first 1-3 words as merchant name
        merchant = ' '.join(words[:min(3, len(words))])
        return merchant
    
    return desc


def group_transactions_by_merchant(uncategorized: pd.DataFrame) -> dict:
    """Group uncategorized transactions by merchant patterns."""
    merchant_groups = defaultdict(list)
    
    for idx, row in uncategorized.iterrows():
        merchant = extract_merchant_name(row['description'])
        merchant_groups[merchant].append({
            'date': row['date'],
            'amount': row['amount'],
            'description': row['description'],
            'institution': row['institution'],
            'account': row['account']
        })
    
    # Sort groups by transaction count (most frequent first)
    sorted_groups = dict(sorted(merchant_groups.items(), 
                               key=lambda x: len(x[1]), 
                               reverse=True))
    
    return sorted_groups


def display_merchant_group(merchant: str, transactions: list, group_num: int, total_groups: int):
    """Display a merchant group for categorization."""
    print(f"\n{'='*80}")
    print(f"GROUP {group_num}/{total_groups}: {merchant}")
    print(f"{'='*80}")
    print(f"Number of transactions: {len(transactions)}")
    
    # Calculate total amount
    total_amount = sum(t['amount'] for t in transactions)
    print(f"Total amount: ${total_amount:,.2f}")
    
    # Show date range
    dates = [t['date'] for t in transactions]
    print(f"Date range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}")
    
    # Show institutions
    institutions = Counter(t['institution'] for t in transactions)
    print(f"Institutions: {', '.join(f'{inst}({count})' for inst, count in institutions.items())}")
    
    print(f"\nSample transactions:")
    print(f"{'Date':<12} {'Amount':<12} {'Description':<50}")
    print("-" * 80)
    
    # Show up to 5 sample transactions
    for i, transaction in enumerate(transactions[:5]):
        date_str = transaction['date'].strftime('%Y-%m-%d')
        amount_str = f"${transaction['amount']:,.2f}"
        desc = transaction['description'][:47] + "..." if len(transaction['description']) > 50 else transaction['description']
        print(f"{date_str:<12} {amount_str:<12} {desc:<50}")
    
    if len(transactions) > 5:
        print(f"... and {len(transactions) - 5} more transactions")


def get_user_categorization(merchant: str, existing_categories: list) -> tuple:
    """Get categorization decision from user."""
    print(f"\nHow would you like to categorize '{merchant}'?")
    print(f"\nExisting categories:")
    
    # Display existing categories in columns
    categories = sorted(existing_categories)
    for i, category in enumerate(categories, 1):
        print(f"{i:2d}. {category}")
    
    print(f"\nOptions:")
    print(f"  - Enter a number (1-{len(categories)}) to use an existing category")
    print(f"  - Type a new category name to create a new category")
    print(f"  - Type 'skip' to skip this merchant for now")
    print(f"  - Type 'quit' to exit the categorization process")
    
    while True:
        choice = input(f"\nYour choice: ").strip()
        
        if choice.lower() == 'quit':
            return 'quit', None
        
        if choice.lower() == 'skip':
            return 'skip', None
        
        # Check if it's a number (existing category)
        try:
            num = int(choice)
            if 1 <= num <= len(categories):
                return 'existing', categories[num - 1]
            else:
                print(f"Please enter a number between 1 and {len(categories)}")
                continue
        except ValueError:
            pass
        
        # Check if it's a new category name
        if choice and choice not in categories:
            confirm = input(f"Create new category '{choice}'? (y/n): ").strip().lower()
            if confirm in ['y', 'yes']:
                return 'new', choice
            else:
                continue
        
        # Check if it matches an existing category name
        if choice in categories:
            return 'existing', choice
        
        print("Invalid choice. Please try again.")


def suggest_pattern_for_merchant(merchant: str, transactions: list) -> dict:
    """Suggest a pattern configuration for the merchant."""
    # Analyze the merchant name to suggest pattern type and confidence
    merchant_clean = merchant.strip()
    
    # Determine pattern type and specificity
    if len(merchant_clean.split()) == 1 and merchant_clean.isalpha():
        # Single word, likely exact match
        pattern_type = "substring"
        specificity = "high"
        confidence = 0.90
    elif any(char in merchant_clean for char in ['*', '.', '#']):
        # Contains special characters, might need regex
        pattern_type = "substring"  # Start with substring, user can change to regex
        specificity = "medium"
        confidence = 0.85
    else:
        # Multi-word or complex, use substring
        pattern_type = "substring"
        specificity = "high" if len(transactions) > 10 else "medium"
        confidence = 0.90 if len(transactions) > 10 else 0.85
    
    return {
        'pattern': merchant_clean,
        'confidence': confidence,
        'type': pattern_type,
        'specificity': specificity
    }


def save_categorization_updates(categories_file: str, new_patterns: dict):
    """Save new categorization patterns to the YAML file."""
    # Load existing configuration
    if os.path.exists(categories_file):
        with open(categories_file, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {
            'version': '1.0',
            'default_category': 'Uncategorized',
            'confidence_threshold': 0.7,
            'categories': {}
        }
    
    # Add new patterns
    for category, patterns in new_patterns.items():
        if category not in config['categories']:
            config['categories'][category] = {'patterns': []}
        
        # Add new patterns to existing category
        existing_patterns = [p['pattern'] for p in config['categories'][category]['patterns']]
        for pattern_config in patterns:
            if pattern_config['pattern'] not in existing_patterns:
                config['categories'][category]['patterns'].append(pattern_config)
    
    # Create backup
    backup_file = f"{categories_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if os.path.exists(categories_file):
        import shutil
        shutil.copy2(categories_file, backup_file)
        print(f"Created backup: {backup_file}")
    
    # Save updated configuration
    with open(categories_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
    
    print(f"Updated categories configuration: {categories_file}")


def main():
    """Main interactive categorization function."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        input_file = project_root / "data" / "total" / "all_transactions.csv"
    
    # Categories file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    categories_file = project_root / "categories.yaml"
    
    try:
        print("Interactive Transaction Categorization Tool")
        print("=" * 50)
        
        # Load data
        df = load_transactions(str(input_file))
        existing_categories = load_existing_categories(str(categories_file))
        
        # Filter uncategorized transactions
        uncategorized = df[df['category'] == 'Uncategorized'].copy()
        print(f"Found {len(uncategorized):,} uncategorized transactions")
        
        if len(uncategorized) == 0:
            print("No uncategorized transactions found!")
            return 0
        
        # Group by merchant
        merchant_groups = group_transactions_by_merchant(uncategorized)
        print(f"Grouped into {len(merchant_groups)} merchant patterns")
        
        # Interactive categorization
        new_patterns = defaultdict(list)
        processed_count = 0
        
        for merchant, transactions in merchant_groups.items():
            # Skip very small groups (less than 3 transactions) initially
            if len(transactions) < 3:
                continue
            
            processed_count += 1
            display_merchant_group(merchant, transactions, processed_count, len(merchant_groups))
            
            action, category = get_user_categorization(merchant, existing_categories)
            
            if action == 'quit':
                break
            elif action == 'skip':
                continue
            elif action in ['existing', 'new']:
                # Generate pattern suggestion
                pattern_config = suggest_pattern_for_merchant(merchant, transactions)
                
                print(f"\nSuggested pattern configuration:")
                print(f"  Pattern: {pattern_config['pattern']}")
                print(f"  Type: {pattern_config['type']}")
                print(f"  Confidence: {pattern_config['confidence']}")
                print(f"  Specificity: {pattern_config['specificity']}")
                
                confirm = input(f"Add this pattern to category '{category}'? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    new_patterns[category].append(pattern_config)
                    
                    # Add to existing categories list if it's new
                    if category not in existing_categories:
                        existing_categories.append(category)
                    
                    print(f"✓ Added pattern for '{merchant}' to category '{category}'")
        
        # Save new patterns
        if new_patterns:
            print(f"\nSaving {len(new_patterns)} new categorization patterns...")
            save_categorization_updates(str(categories_file), dict(new_patterns))
            
            print(f"\nSummary of new patterns added:")
            for category, patterns in new_patterns.items():
                print(f"  {category}: {len(patterns)} patterns")
            
            print(f"\nTo apply these new patterns, run:")
            print(f"  python scripts/export/add_categories_to_csv.py")
        else:
            print(f"\nNo new patterns were added.")
        
        return 0
        
    except Exception as e:
        print(f"Error in interactive categorization: {e}")
        import traceback
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())