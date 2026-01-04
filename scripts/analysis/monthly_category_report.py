#!/usr/bin/env python3
"""
Generate monthly transaction summary HTML report with category grouping.
Layout: Months as rows, categories as columns, grouped by year.

This script reads the categorized transactions file and produces an HTML
report with monthly summaries showing spending breakdown by category.

Usage:
    python scripts/analysis/monthly_category_report_by_year.py [input_csv] [output_html]
    
    Defaults:
        input_csv: data/total/all_transactions.csv
        output_html: data/reports/monthly_category_report.html
"""

import csv
import html
import json
import sys
import yaml
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


def load_categorized_transactions(csv_path: str) -> list:
    """Load categorized transactions from CSV file."""
    transactions = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date = datetime.strptime(row['date'], '%Y-%m-%d')
                amount = Decimal(row['amount'])
                category = row.get('category', 'Uncategorized')
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'description': row['description'],
                    'account': row['account'],
                    'account_name': row.get('account_name', ''),
                    'account_type': row.get('account_type', 'debit'),
                    'institution': row['institution'],
                    'category': category,
                    'category_confidence': float(row.get('category_confidence', 0.0)),
                    'category_method': row.get('category_method', 'unknown'),
                })
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping invalid row: {e}", file=sys.stderr)
    
    print(f"Loaded {len(transactions)} transactions")
    return transactions


def load_category_priorities(categories_yaml_path: str) -> dict:
    """Load category priorities from categories.yaml file."""
    category_priorities = {}
    
    try:
        with open(categories_yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        categories = config.get('categories', {})
        for category_name, category_config in categories.items():
            # Use priority from config, default to 9999 if not specified
            priority = category_config.get('priority', 9999)
            category_priorities[category_name] = priority
            
        # Print some debug info about loaded priorities
        if category_priorities:
            print("Category priorities loaded:")
            sorted_categories = sorted(category_priorities.items(), key=lambda x: (x[1], x[0]))
            for category, priority in sorted_categories[:10]:  # Show first 10
                print(f"  {category}: {priority}")
            if len(sorted_categories) > 10:
                print(f"  ... and {len(sorted_categories) - 10} more categories")
            
    except Exception as e:
        print(f"Warning: Could not load category priorities from {categories_yaml_path}: {e}")
        print("Using default alphabetical ordering")
    
    return category_priorities


def aggregate_by_month_and_category(transactions: list) -> tuple:
    """Aggregate transactions by month and category.
    
    Returns:
        (monthly_category_data, monthly_transactions, category_stats)
    """
    # Monthly data: {month: {category: amount}}
    monthly_categories = defaultdict(lambda: defaultdict(Decimal))
    
    # Store transactions for drill-down: {month: {category: [transactions]}}
    monthly_txns = defaultdict(lambda: defaultdict(list))
    
    # Overall category statistics
    category_stats = defaultdict(lambda: {
        'total_amount': Decimal('0'),
        'transaction_count': 0,
        'avg_amount': Decimal('0'),
        'months_active': set(),
    })
    
    # Process transactions
    for txn in transactions:
        month_key = txn['date'].strftime('%Y-%m')
        category = txn['category']
        amount = txn['amount']
        
        # Aggregate by month and category
        monthly_categories[month_key][category] += amount
        
        # Store transaction for drill-down
        txn_data = {
            'date': txn['date'].strftime('%Y-%m-%d'),
            'amount': float(amount),
            'description': txn['description'],
            'account_name': txn['account_name'],
            'institution': txn['institution'],
            'category_confidence': txn['category_confidence'],
            'category_method': txn['category_method'],
        }
        monthly_txns[month_key][category].append(txn_data)
        
        # Update category statistics
        category_stats[category]['total_amount'] += amount
        category_stats[category]['transaction_count'] += 1
        category_stats[category]['months_active'].add(month_key)
    
    # Calculate average amounts
    for category, stats in category_stats.items():
        if stats['transaction_count'] > 0:
            stats['avg_amount'] = stats['total_amount'] / stats['transaction_count']
        stats['months_active'] = len(stats['months_active'])  # Convert set to count
    
    return monthly_categories, monthly_txns, category_stats


def generate_category_html(monthly_data: dict, monthly_txns: dict, category_stats: dict, category_priorities: dict, output_path: str):
    """Generate HTML report with months as rows, categories as columns, grouped by year."""
    
    # Sort months chronologically
    sorted_months = sorted(monthly_data.keys())
    
    # Group months by year
    months_by_year = {}
    for month in sorted_months:
        year = month[:4]  # Extract year from YYYY-MM format
        if year not in months_by_year:
            months_by_year[year] = []
        months_by_year[year].append(month)
    
    # Get all categories and sort them by priority
    all_categories = set()
    for month_data in monthly_data.values():
        all_categories.update(month_data.keys())
    
    # Sort categories by priority (lower priority first), then alphabetically
    def get_category_sort_key(category):
        priority = category_priorities.get(category, 9999)
        return (priority, category)
    
    ordered_categories = sorted(all_categories, key=get_category_sort_key)
    
    # Separate categories by type for header styling (but keep priority order)
    spending_categories = []
    income_categories = []
    transfer_categories = []
    other_categories = []
    
    for category in ordered_categories:
        if category in ['Income', 'Dividend'] or 'Income' in category:
            income_categories.append(category)
        elif category in ['Transfers', 'Banking']:
            transfer_categories.append(category)
        elif category == 'Uncategorized':
            other_categories.append(category)
        else:
            spending_categories.append(category)
    
    # Calculate yearly totals by category
    yearly_totals = {}
    for year in months_by_year.keys():
        yearly_totals[year] = {}
        for category in ordered_categories:
            yearly_totals[year][category] = sum(
                monthly_data[month].get(category, 0) 
                for month in months_by_year[year]
            )
    
    # Calculate grand totals by category
    grand_totals = {}
    for category in ordered_categories:
        grand_totals[category] = sum(
            stats['total_amount'] for cat, stats in category_stats.items() 
            if cat == category
        )
    
    # Convert transactions to JSON for JavaScript
    txns_json = json.dumps({
        month: {
            cat: txns 
            for cat, txns in cats.items()
        }
        for month, cats in monthly_txns.items()
    })
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monthly Category Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }}
        .year-section {{
            margin-bottom: 40px;
        }}
        .year-header {{
            background-color: #2c3e50;
            color: white;
            padding: 15px;
            margin: 20px 0 10px 0;
            border-radius: 6px;
            font-size: 1.2em;
            font-weight: bold;
            text-align: center;
        }}
        .positive {{ color: #28a745; }}
        .negative {{ color: #dc3545; }}
        .neutral {{ color: #6c757d; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            font-size: 12px;
        }}
        th, td {{
            padding: 6px 8px;
            text-align: right;
            border: 1px solid #ddd;
            white-space: nowrap;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        .month-header {{
            text-align: left;
            font-weight: 600;
            background-color: #e9ecef;
        }}
        .year-total-row {{
            background-color: #d1ecf1;
            font-weight: bold;
            border-top: 2px solid #17a2b8;
        }}
        .grand-total-row {{
            background-color: #f8f9fa;
            font-weight: bold;
            border-top: 3px solid #333;
        }}
        .clickable {{
            cursor: pointer;
            transition: background-color 0.2s;
        }}
        .clickable:hover {{
            background-color: #e3f2fd;
        }}
        
        /* Category type headers */
        .category-type-header {{
            background-color: #6c757d !important;
            color: white;
            text-align: center;
            font-weight: bold;
        }}
        .spending-header {{ background-color: #dc3545 !important; }}
        .income-header {{ background-color: #28a745 !important; }}
        .transfer-header {{ background-color: #17a2b8 !important; }}
        .other-header {{ background-color: #6c757d !important; }}
        
        /* Modal styles */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }}
        .modal-content {{
            background-color: white;
            margin: 5% auto;
            padding: 20px;
            border-radius: 8px;
            width: 90%;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
        }}
        .close {{
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }}
        .close:hover {{
            color: black;
        }}
        .transaction-list {{
            margin-top: 15px;
        }}
        .transaction-item {{
            padding: 10px;
            border-bottom: 1px solid #eee;
            display: grid;
            grid-template-columns: 100px 100px 1fr 150px;
            gap: 10px;
            align-items: center;
        }}
        .transaction-item:last-child {{
            border-bottom: none;
        }}
        .confidence-badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.8em;
            color: white;
        }}
        .confidence-high {{ background-color: #28a745; }}
        .confidence-medium {{ background-color: #ffc107; color: #000; }}
        .confidence-low {{ background-color: #dc3545; }}
        
        @media (max-width: 768px) {{
            .container {{ margin: 10px; padding: 15px; }}
            table {{ font-size: 10px; }}
            th, td {{ padding: 4px 6px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Monthly Category Report</h1>'''
    
    # Generate tables grouped by year
    for year in sorted(months_by_year.keys()):
        year_months = months_by_year[year]
        
        html_content += f'''
        <div class="year-section">
            <div class="year-header">{year}</div>
            <table>
                <thead>
                    <tr>
                        <th class="month-header">Month</th>'''
        
        # Add category headers with type grouping
        for category in ordered_categories:
            # Determine category type for header styling
            if category in spending_categories:
                cat_type = "spending"
            elif category in income_categories:
                cat_type = "income"
            elif category in transfer_categories:
                cat_type = "transfer"
            else:
                cat_type = "other"
            
            html_content += f'<th class="{cat_type}-header">{category}</th>'
        
        html_content += '</tr></thead><tbody>'
        
        # Add month rows for this year
        for month in year_months:
            month_name = datetime.strptime(month, '%Y-%m').strftime('%B')
            html_content += f'<tr><td class="month-header">{month_name}</td>'
            
            for category in ordered_categories:
                amount = monthly_data[month].get(category, 0)
                css_class = 'negative' if amount < 0 else 'positive' if amount > 0 else 'neutral'
                cell_class = f'clickable {css_class}'
                html_content += f'<td class="{cell_class}" onclick="showTransactions(\'{month}\', \'{category}\')">${amount:,.0f}</td>'
            
            html_content += '</tr>'
        
        # Add year total row
        html_content += '<tr class="year-total-row"><td><strong>Year Total</strong></td>'
        for category in ordered_categories:
            total = yearly_totals[year].get(category, 0)
            css_class = 'negative' if total < 0 else 'positive' if total > 0 else 'neutral'
            html_content += f'<td class="{css_class}"><strong>${total:,.0f}</strong></td>'
        html_content += '</tr>'
        
        html_content += '</tbody></table></div>'
    
    # Add grand total row
    html_content += '''
        <div class="year-section">
            <div class="year-header">Grand Totals</div>
            <table>
                <thead>
                    <tr>
                        <th class="month-header">All Years</th>'''
    
    for category in ordered_categories:
        if category in spending_categories:
            cat_type = "spending"
        elif category in income_categories:
            cat_type = "income"
        elif category in transfer_categories:
            cat_type = "transfer"
        else:
            cat_type = "other"
        
        html_content += f'<th class="{cat_type}-header">{category}</th>'
    
    html_content += '''</tr>
                </thead>
                <tbody>
                    <tr class="grand-total-row">
                        <td><strong>Grand Total</strong></td>'''
    
    for category in ordered_categories:
        total = grand_totals.get(category, 0)
        css_class = 'negative' if total < 0 else 'positive' if total > 0 else 'neutral'
        html_content += f'<td class="{css_class}"><strong>${total:,.0f}</strong></td>'
    
    html_content += '''</tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- Modal for transaction details -->
    <div id="transactionModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <h2 id="modalTitle">Transactions</h2>
            <div id="modalBody"></div>
        </div>
    </div>
    
    <script>
        // Transaction data
        const transactions = ''' + txns_json + ''';
        
        // Modal functionality
        const modal = document.getElementById('transactionModal');
        const span = document.getElementsByClassName('close')[0];
        
        span.onclick = function() {
            modal.style.display = 'none';
        }
        
        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
        
        function showTransactions(month, category) {
            const monthData = transactions[month];
            if (!monthData || !monthData[category]) {
                alert('No transactions found for this category and month.');
                return;
            }
            
            const txns = monthData[category];
            const modalTitle = document.getElementById('modalTitle');
            const modalBody = document.getElementById('modalBody');
            
            modalTitle.textContent = `${category} - ${month} (${txns.length} transactions)`;
            
            let html = '<div class="transaction-list">';
            let total = 0;
            
            // Sort transactions by date (newest first)
            txns.sort((a, b) => new Date(b.date) - new Date(a.date));
            
            txns.forEach(txn => {
                total += txn.amount;
                const amountClass = txn.amount < 0 ? 'negative' : 'positive';
                const confidenceClass = txn.category_confidence >= 0.8 ? 'confidence-high' : 
                                       txn.category_confidence >= 0.6 ? 'confidence-medium' : 'confidence-low';
                
                html += `
                    <div class="transaction-item">
                        <div>${txn.date}</div>
                        <div class="${amountClass}">$${txn.amount.toFixed(2)}</div>
                        <div>${txn.description}</div>
                        <div>
                            ${txn.institution} - ${txn.account_name}
                            <br>
                            <span class="confidence-badge ${confidenceClass}">
                                ${(txn.category_confidence * 100).toFixed(0)}% (${txn.category_method})
                            </span>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            html += `<div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid #333; font-weight: bold;">
                        Total: <span class="${total < 0 ? 'negative' : 'positive'}">$${total.toFixed(2)}</span>
                     </div>`;
            
            modalBody.innerHTML = html;
            modal.style.display = 'block';
        }
    </script>
</body>
</html>'''
    
    # Write HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Generated category report: {output_path}")


def main():
    """Main function to generate monthly category report."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        input_file = project_root / "data" / "total" / "all_transactions.csv"
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        output_file = project_root / "data" / "reports" / "monthly_category_report.html"
    
    # Categories YAML file path
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    categories_file = project_root / "categories.yaml"
    
    try:
        print("Generating monthly category report...")
        print(f"Input file: {input_file}")
        print(f"Output file: {output_file}")
        print(f"Categories file: {categories_file}")
        
        # Load category priorities
        category_priorities = load_category_priorities(str(categories_file))
        print(f"Loaded priorities for {len(category_priorities)} categories")
        
        # Load categorized transactions
        transactions = load_categorized_transactions(str(input_file))
        
        # Aggregate by month and category
        monthly_data, monthly_txns, category_stats = aggregate_by_month_and_category(transactions)
        
        # Generate HTML report
        output_file.parent.mkdir(parents=True, exist_ok=True)
        generate_category_html(monthly_data, monthly_txns, category_stats, category_priorities, str(output_file))
        
        print("Monthly category report generated successfully!")
        return 0
        
    except Exception as e:
        print(f"Error generating category report: {e}")
        import traceback
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())