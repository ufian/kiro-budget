#!/usr/bin/env python3
"""Generate monthly transaction summary HTML report.

This script reads the consolidated transactions file and produces an HTML
report with monthly summaries showing:
- Total income (external deposits/transfers in)
- Internal transfers (between own accounts)
- External transfers (transfers out to external accounts)
- Total spending (purchases, bills, etc.)

IMPORTANT: Internal transfers may have up to 3 business days of processing lag,
which means transfer pairs might appear in different months. Monthly totals
for internal transfers may not balance perfectly within a single month.

Sign convention:
- Negative numbers = spending (money going out)
- Positive numbers = income, refunds, credits (money coming in)

Each cell is clickable to show the underlying transactions.

Usage:
    python scripts/analysis/monthly_summary_report.py [input_csv] [output_html]
    
    Defaults:
        input_csv: data/total/all_transactions.csv
        output_html: data/reports/monthly_summary.html
"""

import csv
import html
import json
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


# Patterns to identify transaction types
INTERNAL_TRANSFER_PATTERNS = [
    'transfer to ',
    'transfer from ',
    'to pocket',
    'from pocket',
    'deposit transfer from',
    'withdrawal transfer to',
]

# Credit card payment patterns - these are internal transfers
# (money moving from bank account to credit card)
CREDIT_CARD_PAYMENT_PATTERNS = [
    'payment thank you',      # Chase CC payment received
    'payment received',
    'payment transaction',    # Gemini CC payment received
    'cardpymt',               # Withdrawal to pay credit card (e.g., "Gemini CardPymt")
    'applecard gsbank payment',  # Apple Card payment from bank
    'gsbank payment',         # Goldman Sachs (Apple Card) payment
]

# Salary/income patterns - must be specific employer deposits
INCOME_PATTERNS = [
    'deposit moodys analytics',
    'deposit moodys investor',
    'deposit risk management',
    'deposit microsoft',
    'deposit payroll',
    'deposit real property',  # Rental income
    'dividend',
    'deposit paid leave',     # Paid leave benefits
]

EXTERNAL_TRANSFER_PATTERNS = [
    'olb external transfer',
    'external transfer',
]

# Refund patterns - positive amounts that are refunds, not income
REFUND_PATTERNS = [
    'refund',
    'credit',
    'return',
    'reversal',
    'cashback',
    'cash back',
]


def classify_transaction(description: str, amount: Decimal, account_type: str = 'debit', institution: str = '') -> str:
    """Classify a transaction into a category.
    
    Returns one of: 'income', 'internal_transfer', 'external_transfer', 'spending', 'refund'
    
    Note: All transactions now follow banking convention after automatic sign detection:
    - Negative amounts = spending (money going out)
    - Positive amounts = income, refunds, payments (money coming in)
    """
    desc_lower = description.lower()
    
    # Check for internal transfers first (between own accounts)
    for pattern in INTERNAL_TRANSFER_PATTERNS:
        if pattern in desc_lower:
            return 'internal_transfer'
    
    # Credit card payments are internal transfers
    for pattern in CREDIT_CARD_PAYMENT_PATTERNS:
        if pattern in desc_lower:
            return 'internal_transfer'
    
    # Check for external transfers
    for pattern in EXTERNAL_TRANSFER_PATTERNS:
        if pattern in desc_lower:
            return 'external_transfer'
    
    # Check for salary/income patterns (specific employers)
    for pattern in INCOME_PATTERNS:
        if pattern in desc_lower:
            return 'income'
    
    # Check for refunds - these are spending adjustments, not income
    for pattern in REFUND_PATTERNS:
        if pattern in desc_lower:
            return 'refund'
    
    # For credit card accounts, handle different sign conventions by institution
    if account_type == 'credit':
        return _classify_credit_card_transaction(description, amount, institution)
    
    # For debit/checking accounts:
    # - Negative amounts are spending
    # - Positive amounts are treated as refunds/misc (not income)
    if amount < 0:
        return 'spending'
    else:
        return 'refund'


def _classify_credit_card_transaction(description: str, amount: Decimal, institution: str) -> str:
    """Classify credit card transactions using banking convention.
    
    NOTE: All transactions now follow banking convention after sign detection:
    - Negative amounts = spending (money going out)
    - Positive amounts = income/refunds/payments (money coming in)
    """
    
    # Check for transfer patterns first (regardless of institution)
    desc_lower = description.lower()
    if any(pattern in desc_lower for pattern in ['payment transaction', 'deposit internet transfer', 'transfer']):
        return 'internal_transfer'
    
    # All credit card transactions now follow banking convention
    # regardless of original institution format
    if amount < 0:
        # Negative amounts are spending
        return 'spending'
    else:
        # Positive amounts are payments/refunds/credits
        # Use amount threshold and description to distinguish
        if abs(amount) > 100 and any(pattern in desc_lower for pattern in CREDIT_CARD_PAYMENT_PATTERNS):
            return 'internal_transfer'
        else:
            return 'refund'


def load_transactions(csv_path: str) -> list:
    """Load transactions from CSV file."""
    transactions = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date = datetime.strptime(row['date'], '%Y-%m-%d')
                amount = Decimal(row['amount'])
                transactions.append({
                    'date': date,
                    'amount': amount,
                    'description': row['description'],
                    'account': row['account'],
                    'account_name': row['account_name'],
                    'account_type': row.get('account_type', 'debit'),
                    'institution': row['institution'],
                })
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping invalid row: {e}", file=sys.stderr)
    
    return transactions


def aggregate_by_month(transactions: list) -> tuple:
    """Aggregate transactions by month and category.
    
    Sign convention:
    - Negative = money going out (spending)
    - Positive = money coming in (income, refunds, credit card payments)
    
    Returns:
        (monthly_totals, monthly_transactions) where monthly_transactions
        contains the actual transaction lists for each cell.
    """
    monthly = defaultdict(lambda: {
        'income': Decimal('0'),
        'internal_transfer': Decimal('0'),
        'external_transfer': Decimal('0'),
        'credits': Decimal('0'),  # Positive amounts: refunds, misc credits
        'spending': Decimal('0'),  # Negative amounts: purchases, bills
    })
    
    # Store transactions for each cell
    monthly_txns = defaultdict(lambda: {
        'income': [],
        'internal_transfer': [],
        'external_transfer': [],
        'credits': [],
        'spending': [],
    })
    
    for txn in transactions:
        month_key = txn['date'].strftime('%Y-%m')
        account_type = txn.get('account_type', 'debit')
        category = classify_transaction(txn['description'], txn['amount'], account_type, txn.get('institution', ''))
        amount = txn['amount']
        
        # Credit card amounts already follow standard sign convention:
        # - Negative = spending, Positive = credits/payments
        # No normalization needed for credit cards
        amount = txn['amount']
        
        # Store transaction for drill-down
        txn_data = {
            'date': txn['date'].strftime('%Y-%m-%d'),
            'amount': float(amount),
            'description': txn['description'],
            'account_name': txn['account_name'],
            'institution': txn['institution'],
        }
        
        if category == 'income':
            monthly[month_key]['income'] += amount  # Positive: salary, dividends
            monthly_txns[month_key]['income'].append(txn_data)
        elif category == 'internal_transfer':
            monthly[month_key]['internal_transfer'] += amount  # Can be +/-
            monthly_txns[month_key]['internal_transfer'].append(txn_data)
        elif category == 'external_transfer':
            monthly[month_key]['external_transfer'] += amount  # Usually negative
            monthly_txns[month_key]['external_transfer'].append(txn_data)
        elif category == 'refund':
            # Credits: refunds, cashback, misc positive amounts
            monthly[month_key]['credits'] += amount  # Positive
            monthly_txns[month_key]['credits'].append(txn_data)
        else:  # spending
            # Spending: purchases, bills, subscriptions
            monthly[month_key]['spending'] += amount  # Negative
            monthly_txns[month_key]['spending'].append(txn_data)
    
    return monthly, monthly_txns


def generate_html(monthly_data: dict, monthly_txns: dict, output_path: str):
    """Generate HTML report with clickable cells.
    
    Sign convention displayed:
    - Negative numbers (red) = spending (money going out)
    - Positive numbers (green) = income, refunds, credits (money coming in)
    """
    
    # Sort months chronologically
    sorted_months = sorted(monthly_data.keys())
    
    # Calculate totals
    totals = {
        'income': Decimal('0'),
        'internal_transfer': Decimal('0'),
        'external_transfer': Decimal('0'),
        'credits': Decimal('0'),
        'spending': Decimal('0'),
    }
    
    for month_data in monthly_data.values():
        for key in totals:
            totals[key] += month_data[key]
    
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
    <title>Monthly Transaction Summary</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .legend {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .legend-title {{
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
            font-size: 0.9em;
        }}
        .legend-positive {{ color: #2e7d32; }}
        .legend-negative {{ color: #c62828; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-top: 20px;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: right;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #4CAF50;
            color: white;
            font-weight: 600;
        }}
        th:first-child, td:first-child {{
            text-align: left;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        tr.totals {{
            font-weight: bold;
            background: #e8f5e9;
        }}
        tr.year-subtotal {{
            font-weight: bold;
            background: #fff3e0;
            border-top: 2px solid #ff9800;
        }}
        tr.year-header {{
            background: #e3f2fd;
        }}
        tr.year-header td {{
            font-weight: bold;
            font-size: 1.1em;
            color: #1565c0;
            padding: 15px;
        }}
        .positive {{ color: #2e7d32; }}
        .negative {{ color: #c62828; }}
        .transfer {{ color: #1565c0; }}
        .clickable {{
            cursor: pointer;
            text-decoration: underline;
            text-decoration-style: dotted;
        }}
        .clickable:hover {{
            background: #fff9c4;
        }}
        .generated {{
            margin-top: 20px;
            color: #666;
            font-size: 0.9em;
        }}
        
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
            max-width: 900px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}
        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .modal-header h2 {{
            margin: 0;
            color: #333;
        }}
        .close {{
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            color: #666;
        }}
        .close:hover {{
            color: #000;
        }}
        .txn-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        .txn-table th, .txn-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #eee;
            text-align: left;
        }}
        .txn-table th {{
            background: #f5f5f5;
            color: #333;
        }}
        .txn-table td.amount {{
            text-align: right;
            font-family: monospace;
        }}
        .txn-table td.amount.positive {{ color: #2e7d32; }}
        .txn-table td.amount.negative {{ color: #c62828; }}
        .txn-table tr:hover {{
            background: #f9f9f9;
        }}
        .txn-count {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <h1>Monthly Transaction Summary</h1>
    <div class="legend">
        <div class="legend-title">Sign Convention:</div>
        <span class="legend-item legend-negative">Negative (-) = Spending (money out)</span>
        <span class="legend-item legend-positive">Positive (+) = Income, Refunds, Credits (money in)</span>
    </div>
    <div class="legend" style="background: #fff3e0; border-left: 4px solid #ff9800;">
        <div class="legend-title" style="color: #e65100;">⚠️ Internal Transfer Timing:</div>
        <p style="margin: 5px 0; color: #bf360c; font-size: 0.9em;">
            Internal transfers may have up to 3 business days of processing lag. 
            Transfer pairs might appear in different months, causing monthly internal transfer totals to not balance perfectly.
        </p>
    </div>
    <p style="color: #666;">Click on any value to see the underlying transactions.</p>
    <table>
        <thead>
            <tr>
                <th>Month</th>
                <th>Income</th>
                <th>Internal Transfers</th>
                <th>External Transfers</th>
                <th>Credits/Refunds</th>
                <th>Spending</th>
            </tr>
        </thead>
        <tbody>
'''
    
    # Group months by year
    months_by_year = {}
    for month in sorted_months:
        year = month[:4]
        if year not in months_by_year:
            months_by_year[year] = []
        months_by_year[year].append(month)
    
    # Format amounts with sign and color class
    def fmt_with_class(val):
        if val >= 0:
            return (f"+${val:,.2f}", "positive")
        else:
            return (f"-${abs(val):,.2f}", "negative")
    
    # Generate rows grouped by year
    for year in sorted(months_by_year.keys()):
        # Year header row
        html_content += f'''            <tr class="year-header">
                <td colspan="6">📅 {year}</td>
            </tr>
'''
        
        # Year subtotals
        year_totals = {
            'income': Decimal('0'),
            'internal_transfer': Decimal('0'),
            'external_transfer': Decimal('0'),
            'credits': Decimal('0'),
            'spending': Decimal('0'),
        }
        
        for month in months_by_year[year]:
            data = monthly_data[month]
            
            # Accumulate year totals
            for key in year_totals:
                year_totals[key] += data[key]
            
            # Format month for display (just month name, year is in header)
            month_display = datetime.strptime(month, '%Y-%m').strftime('%B')
            month_full = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
            
            income_fmt, income_cls = fmt_with_class(data['income'])
            transfer_fmt, transfer_cls = fmt_with_class(data['internal_transfer'])
            external_fmt, external_cls = fmt_with_class(data['external_transfer'])
            credits_fmt, credits_cls = fmt_with_class(data['credits'])
            spending_fmt, spending_cls = fmt_with_class(data['spending'])
            
            html_content += f'''            <tr>
                <td>{month_display}</td>
                <td class="{income_cls} clickable" onclick="showTransactions('{month}', 'income', '{month_full}')">{income_fmt}</td>
                <td class="transfer clickable" onclick="showTransactions('{month}', 'internal_transfer', '{month_full}')">{transfer_fmt}</td>
                <td class="{external_cls} clickable" onclick="showTransactions('{month}', 'external_transfer', '{month_full}')">{external_fmt}</td>
                <td class="{credits_cls} clickable" onclick="showTransactions('{month}', 'credits', '{month_full}')">{credits_fmt}</td>
                <td class="{spending_cls} clickable" onclick="showTransactions('{month}', 'spending', '{month_full}')">{spending_fmt}</td>
            </tr>
'''
        
        # Year subtotal row
        income_fmt, income_cls = fmt_with_class(year_totals['income'])
        transfer_fmt, transfer_cls = fmt_with_class(year_totals['internal_transfer'])
        external_fmt, external_cls = fmt_with_class(year_totals['external_transfer'])
        credits_fmt, credits_cls = fmt_with_class(year_totals['credits'])
        spending_fmt, spending_cls = fmt_with_class(year_totals['spending'])
        
        html_content += f'''            <tr class="year-subtotal">
                <td>{year} Subtotal</td>
                <td class="{income_cls}">{income_fmt}</td>
                <td class="transfer">{transfer_fmt}</td>
                <td class="{external_cls}">{external_fmt}</td>
                <td class="{credits_cls}">{credits_fmt}</td>
                <td class="{spending_cls}">{spending_fmt}</td>
            </tr>
'''
    
    # Add grand totals row
    income_fmt, income_cls = fmt_with_class(totals['income'])
    transfer_fmt, transfer_cls = fmt_with_class(totals['internal_transfer'])
    external_fmt, external_cls = fmt_with_class(totals['external_transfer'])
    credits_fmt, credits_cls = fmt_with_class(totals['credits'])
    spending_fmt, spending_cls = fmt_with_class(totals['spending'])
    
    html_content += f'''            <tr class="totals">
                <td><strong>GRAND TOTAL</strong></td>
                <td class="{income_cls}">{income_fmt}</td>
                <td class="transfer">{transfer_fmt}</td>
                <td class="{external_cls}">{external_fmt}</td>
                <td class="{credits_cls}">{credits_fmt}</td>
                <td class="{spending_cls}">{spending_fmt}</td>
            </tr>
'''
    
    html_content += f'''        </tbody>
    </table>
    <p class="generated">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <!-- Modal for transaction details -->
    <div id="txnModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modalTitle">Transactions</h2>
                <span class="close" onclick="closeModal()">&times;</span>
            </div>
            <div class="txn-count" id="txnCount"></div>
            <table class="txn-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Account</th>
                        <th>Institution</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody id="txnBody">
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        const transactionData = {txns_json};
        
        const categoryNames = {{
            'income': 'Income',
            'internal_transfer': 'Internal Transfers',
            'external_transfer': 'External Transfers',
            'credits': 'Credits/Refunds',
            'spending': 'Spending'
        }};
        
        function showTransactions(month, category, monthDisplay) {{
            const txns = transactionData[month]?.[category] || [];
            const modal = document.getElementById('txnModal');
            const title = document.getElementById('modalTitle');
            const count = document.getElementById('txnCount');
            const tbody = document.getElementById('txnBody');
            
            title.textContent = `${{monthDisplay}} - ${{categoryNames[category]}}`;
            
            const total = txns.reduce((sum, t) => sum + t.amount, 0);
            const totalFormatted = total >= 0 
                ? `+${{total.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`
                : `-${{Math.abs(total).toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
            count.textContent = `${{txns.length}} transactions, Total: ${{totalFormatted}}`; 
            
            // Sort by date, then by amount
            txns.sort((a, b) => {{
                if (a.date !== b.date) return a.date.localeCompare(b.date);
                return Math.abs(b.amount) - Math.abs(a.amount);
            }});
            
            tbody.innerHTML = txns.map(t => {{
                const amtClass = t.amount >= 0 ? 'positive' : 'negative';
                const amtStr = t.amount >= 0 
                    ? `+${{t.amount.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`
                    : `-${{Math.abs(t.amount).toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
                return `
                    <tr>
                        <td>${{t.date}}</td>
                        <td>${{escapeHtml(t.description)}}</td>
                        <td>${{escapeHtml(t.account_name)}}</td>
                        <td>${{escapeHtml(t.institution)}}</td>
                        <td class="amount ${{amtClass}}">${{amtStr}}</td>
                    </tr>
                `;
            }}).join('');
            
            modal.style.display = 'block';
        }}
        
        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        }}
        
        function closeModal() {{
            document.getElementById('txnModal').style.display = 'none';
        }}
        
        // Close modal when clicking outside
        window.onclick = function(event) {{
            const modal = document.getElementById('txnModal');
            if (event.target === modal) {{
                modal.style.display = 'none';
            }}
        }}
        
        // Close modal with Escape key
        document.addEventListener('keydown', function(event) {{
            if (event.key === 'Escape') {{
                closeModal();
            }}
        }});
    </script>
</body>
</html>
'''
    
    # Write output
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Report generated: {output_path}")


def main():
    # Default paths
    input_csv = 'data/total/all_transactions.csv'
    output_html = 'data/reports/monthly_summary.html'
    
    # Override with command line args if provided
    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
    if len(sys.argv) > 2:
        output_html = sys.argv[2]
    
    # Check input file exists
    if not Path(input_csv).exists():
        print(f"Error: Input file not found: {input_csv}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Loading transactions from: {input_csv}")
    transactions = load_transactions(input_csv)
    print(f"Loaded {len(transactions)} transactions")
    
    print("Aggregating by month...")
    monthly_data, monthly_txns = aggregate_by_month(transactions)
    print(f"Found {len(monthly_data)} months of data")
    
    print(f"Generating HTML report...")
    generate_html(monthly_data, monthly_txns, output_html)


if __name__ == '__main__':
    main()
