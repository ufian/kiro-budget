# Account Configuration

The Account Configuration system allows you to define human-readable names and types for your financial accounts. This enriches transaction data during CSV export, making it easier to identify and analyze transactions across multiple institutions.

## Overview

When processing financial data files, the parser can enrich transactions with:

- **account_name**: A friendly name for the account (e.g., "Main Checking", "Travel Credit Card")
- **account_type**: Classification as either "debit" (checking/savings) or "credit" (credit cards)

This information is added to the CSV output, enabling better filtering and analysis in spreadsheet applications or financial tools.

## Configuration File

### Location

The account configuration file should be placed at:

```
raw/accounts.yaml
```

This location is relative to your project's raw data directory.

### Generating a Template

Use the CLI command to generate a sample configuration template:

```bash
python -m kiro_budget.cli generate-accounts-template
```

This creates `raw/accounts.yaml.example` with documented examples. Copy and customize it:

```bash
cp raw/accounts.yaml.example raw/accounts.yaml
```

### Command Options

```bash
python -m kiro_budget.cli generate-accounts-template --help

Options:
  -o, --output TEXT  Output path for template file (default: raw/accounts.yaml.example)
  -f, --force        Overwrite existing file without confirmation
```

## Configuration Format

### Basic Structure

```yaml
<institution>:
  "<account_id>":
    account_name: "<human readable name>"
    account_type: "<debit|credit>"
    description: "<optional notes>"
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `institution` | Yes | Institution name (must match folder name in `raw/`) |
| `account_id` | Yes | Account identifier (typically last 4 digits) |
| `account_name` | Yes | Human-readable account name |
| `account_type` | Yes | Either "debit" or "credit" |
| `description` | No | Optional notes about the account |

### Example Configuration

```yaml
# First Tech Federal Credit Union
firsttech:
  "0125":
    account_name: "Primary Savings"
    account_type: debit
    description: "Emergency fund"
  
  "0547":
    account_name: "Main Checking"
    account_type: debit
  
  "0854":
    account_name: "Joint Savings"
    account_type: debit

# Chase Bank
chase:
  "4521":
    account_name: "Sapphire Preferred"
    account_type: credit
    description: "Travel rewards card"
  
  "8147":
    account_name: "Freedom Unlimited"
    account_type: credit

# Gemini Exchange
gemini:
  "main":
    account_name: "Crypto Trading"
    account_type: debit
```

## Important Notes

### Account ID Quoting

Always quote account IDs to preserve leading zeros:

```yaml
# Correct - preserves leading zero
"0547":
  account_name: "Main Checking"

# Incorrect - YAML may interpret as octal number
0547:
  account_name: "Main Checking"
```

### Institution Name Matching

Institution names in the configuration must match the folder names in your `raw/` directory:

```
raw/
├── chase/          # Use "chase" in config
├── firsttech/      # Use "firsttech" in config
└── gemini/         # Use "gemini" in config
```

### Account Type Values

Only two values are valid for `account_type`:

- `debit` - For checking accounts, savings accounts, and debit cards
- `credit` - For credit cards and lines of credit

## Default Behavior

### Unconfigured Accounts

If a transaction's account is not found in the configuration:

- `account_name` defaults to the raw account ID
- `account_type` defaults to "debit"

### Missing Configuration File

If `raw/accounts.yaml` does not exist:

- Processing continues normally
- Transactions use default values (account ID as name, "debit" as type)
- An informational message is logged

### Invalid Configuration

| Condition | Behavior |
|-----------|----------|
| Invalid YAML syntax | Error logged, processing continues with defaults |
| Missing `account_name` | Warning logged, account entry skipped |
| Invalid `account_type` | Warning logged, defaults to "debit" |
| Missing institution section | Treated as no accounts for that institution |

## CSV Output

When account configuration is applied, the CSV output includes two additional columns:

| Column | Description |
|--------|-------------|
| `account_name` | Human-readable account name from configuration |
| `account_type` | Account type ("debit" or "credit") |

These columns appear after the existing `account` column, preserving the original column order.

### Example Output

```csv
date,amount,description,account,account_name,account_type,institution,transaction_id
2024-01-15,-45.67,GROCERY STORE,0547,Main Checking,debit,firsttech,TXN123
2024-01-16,-125.00,AMAZON.COM,4521,Sapphire Preferred,credit,chase,TXN456
```

## Common Scenarios

### Multiple Accounts at Same Institution

```yaml
chase:
  "4521":
    account_name: "Personal Credit"
    account_type: credit
  "8147":
    account_name: "Business Credit"
    account_type: credit
  "2234":
    account_name: "Business Checking"
    account_type: debit
```

### Same Account ID at Different Institutions

The system correctly distinguishes accounts by both institution and account ID:

```yaml
firsttech:
  "1234":
    account_name: "First Tech Checking"
    account_type: debit

chase:
  "1234":
    account_name: "Chase Checking"
    account_type: debit
```

### Adding a New Institution

1. Create a folder in `raw/` for the institution's files
2. Add a section to `accounts.yaml` with the same name
3. Configure each account with its ID, name, and type

```yaml
# New institution
bankofamerica:
  "5678":
    account_name: "BoA Checking"
    account_type: debit
  "9012":
    account_name: "BoA Cash Rewards"
    account_type: credit
```

## Troubleshooting

### Account Name Not Appearing

1. Verify the institution name matches the folder name exactly (case-sensitive)
2. Check that the account ID matches what appears in your source files
3. Ensure the account ID is quoted in the YAML file

### Invalid YAML Errors

Common YAML syntax issues:

```yaml
# Wrong - missing quotes around ID with leading zero
0547:
  account_name: "Checking"

# Correct
"0547":
  account_name: "Checking"

# Wrong - inconsistent indentation
chase:
"4521":
    account_name: "Card"

# Correct
chase:
  "4521":
    account_name: "Card"
```

### Finding Account IDs

Account IDs are typically extracted from:

- QFX/OFX files: Look for `<ACCTID>` tags
- PDF statements: Usually the last 4 digits shown on the statement
- CSV exports: Check the account column in the file

You can also check the processed CSV files to see what account IDs are being extracted.

## Integration with Processing

The account enrichment happens automatically during the `process` command:

```bash
python -m kiro_budget.cli process
```

No additional flags are needed. The system:

1. Loads `raw/accounts.yaml` at startup
2. Enriches each transaction with account metadata
3. Writes enriched data to the output CSV

To verify your configuration is being applied, check the `account_name` and `account_type` columns in the output CSV files.
