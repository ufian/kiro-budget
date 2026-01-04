# Transaction Categorization System Documentation

## Table of Contents

1. [Overview](#overview)
2. [Installation and Setup](#installation-and-setup)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Pattern Matching](#pattern-matching)
6. [AI Integration](#ai-integration)
7. [CLI Commands](#cli-commands)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [API Reference](#api-reference)

## Overview

The Transaction Categorization System is an intelligent financial data processing component that automatically assigns meaningful categories to financial transactions. It uses a multi-layered approach combining:

- **Pattern Matching**: Rule-based categorization using substring, regex, and exact matching
- **AI-Powered Categorization**: OpenAI/Claude integration for unknown merchants
- **Machine Learning**: Local ML models that learn from your transaction patterns
- **User Feedback**: Interactive learning system that improves accuracy over time

### Key Features

- **Automatic Categorization**: Processes transactions with minimal manual intervention
- **High Accuracy**: Multi-method approach ensures reliable categorization
- **Cost Efficient**: Intelligent caching minimizes AI API costs
- **User Learning**: System learns from your corrections and preferences
- **Flexible Configuration**: Human-readable YAML configuration
- **CLI Integration**: Seamless integration with existing kiro-budget workflow

## Installation and Setup

### Prerequisites

- Python 3.8 or higher
- Virtual environment activated (`source venv/bin/activate`)
- kiro-budget package installed (`pip install -e .`)

### Initial Setup

1. **Initialize Categories Configuration**
   ```bash
   # Create default categories.yaml file
   kiro-budget init-categories
   ```

2. **Configure AI Services (Optional)**
   ```bash
   # Set OpenAI API key
   export OPENAI_API_KEY="your_openai_api_key_here"
   
   # Set Claude API key (fallback)
   export ANTHROPIC_API_KEY="your_claude_api_key_here"
   ```

3. **Verify Installation**
   ```bash
   # Test categorization on sample data
   kiro-budget categorize --help
   ```

## Configuration

### Configuration File Structure

The categorization system uses a YAML configuration file (`categories.yaml`) with the following structure:

```yaml
version: "1.0"
default_category: "Uncategorized"
confidence_threshold: 0.7

categories:
  Category_Name:
    patterns:
    - pattern: "MERCHANT_NAME"
      confidence: 0.95
      type: "substring"
      specificity: "high"

ai_config:
  enabled: true
  primary_service: "openai"
  cache_responses: true
  max_cost_per_month: 50.0

ml_config:
  enabled: true
  model_type: "random_forest"
  confidence_threshold: 0.6
```

### Configuration Options

#### Global Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `version` | string | "1.0" | Configuration format version |
| `default_category` | string | "Uncategorized" | Category for unmatched transactions |
| `confidence_threshold` | float | 0.7 | Minimum confidence for automatic categorization |

#### Category Patterns

Each category can have multiple patterns with these properties:

| Property | Type | Options | Description |
|----------|------|---------|-------------|
| `pattern` | string | - | Text pattern to match against transaction descriptions |
| `confidence` | float | 0.0-1.0 | Confidence score for this pattern |
| `type` | string | substring, regex, exact | Pattern matching type |
| `specificity` | string | very_high, high, medium, low | Pattern priority level |

#### AI Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable AI categorization |
| `primary_service` | string | "openai" | Primary AI service (openai, claude) |
| `fallback_service` | string | "claude" | Fallback AI service |
| `cache_responses` | boolean | true | Cache AI responses to reduce costs |
| `max_cost_per_month` | float | 50.0 | Maximum monthly AI API cost (USD) |

#### ML Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | true | Enable/disable ML categorization |
| `model_type` | string | "random_forest" | ML model type |
| `confidence_threshold` | float | 0.6 | Minimum ML confidence threshold |
| `retrain_threshold` | integer | 100 | Transactions before model retraining |

## Usage

### Basic Workflow

1. **Process Raw Financial Files**
   ```bash
   # Convert raw files to CSV format
   python -m kiro_budget.cli process
   ```

2. **Build Consolidated Transaction File**
   ```bash
   # Create unified all_transactions.csv
   python scripts/export/build_total_csv.py
   ```

3. **Categorize Transactions**
   ```bash
   # Add categories to transactions
   kiro-budget categorize --input data/total/all_transactions.csv
   ```

4. **Review and Improve**
   ```bash
   # Review low-confidence categorizations
   kiro-budget review-categories --confidence-threshold 0.7
   ```

### Advanced Usage

#### Batch Processing with Custom Settings

```bash
# Categorize with custom confidence threshold
kiro-budget categorize --input data/total/all_transactions.csv --confidence-threshold 0.8

# Force recategorization of all transactions
kiro-budget categorize --input data/total/all_transactions.csv --force

# Generate detailed categorization report
kiro-budget categorize --input data/total/all_transactions.csv --report categorization_report.json
```

#### Interactive Review Sessions

```bash
# Review only transactions below confidence threshold
kiro-budget review-categories --confidence-threshold 0.7

# Review specific category assignments
kiro-budget review-categories --category "Uncategorized"

# Batch review similar transactions
kiro-budget review-categories --batch-similar
```

## Pattern Matching

### Pattern Types

#### 1. Substring Matching
- **Use Case**: Most common merchant names
- **Example**: `"COSTCO"` matches `"COSTCO WHSE #1029"`
- **Case Sensitivity**: Always case-insensitive

```yaml
- pattern: "STARBUCKS"
  confidence: 0.95
  type: "substring"
  specificity: "high"
```

#### 2. Regular Expression Matching
- **Use Case**: Flexible pattern matching
- **Example**: `".*RESTAURANT.*"` matches any description containing "RESTAURANT"
- **Power**: Full regex support for complex patterns

```yaml
- pattern: ".*GAS.*"
  confidence: 0.85
  type: "regex"
  specificity: "medium"
```

#### 3. Exact Matching
- **Use Case**: Precise merchant identification
- **Example**: `"SHELL #1234"` matches only exactly `"SHELL #1234"`
- **Case Sensitivity**: Case-insensitive

```yaml
- pattern: "APPLE STORE #R123"
  confidence: 0.98
  type: "exact"
  specificity: "very_high"
```

### Specificity Levels

The system uses specificity to resolve conflicts when multiple patterns match:

1. **very_high**: Most specific patterns (e.g., "COSTCO GAS" vs "COSTCO")
2. **high**: Specific merchant names (e.g., "STARBUCKS")
3. **medium**: Common patterns with some specificity (e.g., ".*RESTAURANT.*")
4. **low**: Broad patterns (e.g., ".*STORE.*")

### Pattern Priority Rules

When multiple patterns match a transaction:

1. **Specificity Level**: Higher specificity wins
2. **Confidence Score**: Within same specificity, higher confidence wins
3. **Pattern Length**: Longer, more detailed patterns win
4. **Pattern Order**: First matching pattern wins if all else equal

### Common Pattern Examples

```yaml
# Specific merchant with location override
Groceries:
  patterns:
  - pattern: "COSTCO GAS"        # Very specific - gas station
    confidence: 0.95
    type: "substring"
    specificity: "very_high"
  - pattern: "COSTCO"            # General - grocery store
    confidence: 0.90
    type: "substring"
    specificity: "high"

# Flexible restaurant matching
Restaurants:
  patterns:
  - pattern: ".*RESTAURANT.*"    # Any restaurant
    confidence: 0.85
    type: "regex"
    specificity: "medium"
  - pattern: ".*PIZZA.*"         # Pizza places
    confidence: 0.85
    type: "regex"
    specificity: "medium"
  - pattern: "MCDONALD"          # Specific chain
    confidence: 0.95
    type: "substring"
    specificity: "high"

# Utility bill patterns
Utilities:
  patterns:
  - pattern: "^PG&E"             # Starts with PG&E
    confidence: 0.95
    type: "regex"
    specificity: "high"
  - pattern: ".*ELECTRIC.*"      # Any electric company
    confidence: 0.90
    type: "regex"
    specificity: "medium"
  - pattern: "BILL PAY"          # Generic bill payment
    confidence: 0.70
    type: "substring"
    specificity: "low"
```

## AI Integration

### Supported AI Services

#### OpenAI (Primary)
- **Models**: GPT-3.5-turbo, GPT-4
- **Strengths**: High accuracy, good merchant recognition
- **Cost**: ~$0.002 per transaction (GPT-3.5-turbo)

#### Claude (Fallback)
- **Models**: Claude-3-haiku, Claude-3-sonnet
- **Strengths**: Good reasoning, cost-effective
- **Cost**: ~$0.001 per transaction (Claude-3-haiku)

### AI Categorization Process

1. **Pattern Matching First**: AI only used when patterns fail
2. **Context-Aware Prompts**: Includes transaction amount and available categories
3. **Response Validation**: AI responses validated against known categories
4. **Intelligent Caching**: Similar merchants cached to reduce API calls
5. **Cost Controls**: Monthly spending limits and rate limiting

### AI Configuration Examples

#### Conservative Setup (Low Cost)
```yaml
ai_config:
  enabled: true
  primary_service: "openai"
  fallback_service: "claude"
  cache_responses: true
  max_cost_per_month: 10.0
  rate_limit_per_minute: 10
```

#### Aggressive Setup (High Accuracy)
```yaml
ai_config:
  enabled: true
  primary_service: "openai"
  fallback_service: "claude"
  cache_responses: true
  max_cost_per_month: 100.0
  rate_limit_per_minute: 60
  use_gpt4_for_unclear: true
```

#### Offline-Only Setup
```yaml
ai_config:
  enabled: false
  cache_responses: true
  use_cached_only: true
```

### AI Prompt Engineering

The system uses carefully crafted prompts for optimal results:

```
Categorize this financial transaction:

Description: "WHOLE FOODS MARKET #10234"
Amount: $67.89
Date: 2024-01-15

Available categories:
- Groceries
- Restaurants  
- Gas
- Shopping
- Utilities
- Healthcare
- Entertainment
- Transportation
- Uncategorized

Instructions:
1. Choose the single most appropriate category
2. Consider the merchant name and transaction amount
3. If uncertain, choose "Uncategorized"
4. Respond with only the category name

Category:
```

## CLI Commands

### Core Commands

#### `kiro-budget categorize`
Categorize transactions in a CSV file.

```bash
# Basic usage
kiro-budget categorize --input data/total/all_transactions.csv

# With options
kiro-budget categorize \
  --input data/total/all_transactions.csv \
  --output data/total/categorized_transactions.csv \
  --confidence-threshold 0.8 \
  --force \
  --report categorization_report.json
```

**Options:**
- `--input, -i`: Input CSV file path (required)
- `--output, -o`: Output CSV file path (default: overwrites input)
- `--confidence-threshold, -c`: Minimum confidence threshold (default: 0.7)
- `--force, -f`: Force recategorization of already categorized transactions
- `--report, -r`: Generate detailed report file
- `--dry-run`: Show what would be categorized without making changes

#### `kiro-budget review-categories`
Interactive review of categorization results.

```bash
# Review low-confidence transactions
kiro-budget review-categories --confidence-threshold 0.7

# Review specific category
kiro-budget review-categories --category "Uncategorized"

# Batch review similar transactions
kiro-budget review-categories --batch-similar
```

**Options:**
- `--confidence-threshold, -c`: Review transactions below this confidence
- `--category`: Review specific category assignments
- `--batch-similar`: Group similar transactions for batch editing
- `--limit, -l`: Maximum number of transactions to review

#### `kiro-budget init-categories`
Initialize or reset categories configuration.

```bash
# Create default configuration
kiro-budget init-categories

# Create configuration for specific use case
kiro-budget init-categories --template personal
kiro-budget init-categories --template business
kiro-budget init-categories --template family
```

**Options:**
- `--template, -t`: Use predefined template (personal, business, family)
- `--force, -f`: Overwrite existing configuration
- `--backup, -b`: Create backup of existing configuration

#### `kiro-budget manage-categories`
Manage category definitions and patterns.

```bash
# List all categories
kiro-budget manage-categories list

# Add new category
kiro-budget manage-categories add "My_Category" \
  --pattern "MY_MERCHANT" \
  --confidence 0.90 \
  --type substring

# Remove category
kiro-budget manage-categories remove "Old_Category"

# Export categories to file
kiro-budget manage-categories export categories_backup.yaml

# Import categories from file
kiro-budget manage-categories import categories_backup.yaml
```

### Utility Commands

#### `kiro-budget categorization-stats`
Show categorization statistics and accuracy metrics.

```bash
# Basic statistics
kiro-budget categorization-stats --input data/total/all_transactions.csv

# Detailed analysis
kiro-budget categorization-stats \
  --input data/total/all_transactions.csv \
  --detailed \
  --export stats_report.json
```

#### `kiro-budget validate-config`
Validate categories configuration file.

```bash
# Validate current configuration
kiro-budget validate-config

# Validate specific file
kiro-budget validate-config --config custom_categories.yaml
```

## Best Practices

### Configuration Management

#### 1. Start Simple, Iterate
```yaml
# Begin with high-confidence, specific patterns
Groceries:
  patterns:
  - pattern: "COSTCO"
    confidence: 0.95
    type: "substring"
    specificity: "high"

# Add broader patterns after testing
  - pattern: ".*GROCERY.*"
    confidence: 0.80
    type: "regex"
    specificity: "medium"
```

#### 2. Use Hierarchical Specificity
```yaml
# Most specific first
Gas:
  patterns:
  - pattern: "COSTCO GAS"          # Very specific
    confidence: 0.95
    type: "substring"
    specificity: "very_high"
  - pattern: "SHELL"               # Specific chain
    confidence: 0.90
    type: "substring"
    specificity: "high"
  - pattern: ".*GAS.*"             # General pattern
    confidence: 0.85
    type: "regex"
    specificity: "medium"
```

#### 3. Regular Configuration Backups
```bash
# Automatic backups are created, but manual backups are recommended
cp categories.yaml backups/categories_$(date +%Y%m%d).yaml
```

### Pattern Design Guidelines

#### 1. Confidence Score Guidelines
- **0.95-1.0**: Exact merchant names (e.g., "STARBUCKS #1234")
- **0.85-0.94**: Common merchant chains (e.g., "SHELL", "TARGET")
- **0.70-0.84**: Category patterns (e.g., ".*RESTAURANT.*")
- **0.50-0.69**: Broad patterns (use sparingly)

#### 2. Regex Best Practices
```yaml
# Good: Specific and efficient
- pattern: "^AMAZON"              # Starts with AMAZON
- pattern: "STORE$"               # Ends with STORE
- pattern: ".*COFFEE.*"           # Contains COFFEE

# Avoid: Too broad or inefficient
- pattern: ".*"                   # Matches everything
- pattern: ".*[A-Z].*[0-9].*"     # Complex, slow pattern
```

#### 3. Handle Edge Cases
```yaml
# Account for merchant name variations
Shopping:
  patterns:
  - pattern: "AMAZON"             # Main pattern
  - pattern: "AMZN"               # Abbreviated form
  - pattern: "AMAZON.COM"         # Full domain
  - pattern: "AMAZON MARKETPLACE" # Marketplace transactions
```

### Performance Optimization

#### 1. Pattern Order Matters
```yaml
# Put most specific patterns first
Groceries:
  patterns:
  - pattern: "WHOLE FOODS MARKET" # Most specific
  - pattern: "WHOLE FOODS"        # Less specific
  - pattern: ".*ORGANIC.*"        # Broad pattern last
```

#### 2. AI Cost Management
```yaml
ai_config:
  enabled: true
  cache_responses: true           # Essential for cost control
  max_cost_per_month: 25.0       # Set reasonable limits
  rate_limit_per_minute: 20       # Prevent API overuse
```

#### 3. Batch Processing
```bash
# Process large datasets in batches
kiro-budget categorize --input large_file.csv --batch-size 1000
```

### Quality Assurance

#### 1. Regular Review Sessions
```bash
# Weekly review of low-confidence transactions
kiro-budget review-categories --confidence-threshold 0.8

# Monthly review of "Uncategorized" transactions
kiro-budget review-categories --category "Uncategorized"
```

#### 2. Validation Checks
```bash
# Validate configuration after changes
kiro-budget validate-config

# Check categorization statistics
kiro-budget categorization-stats --input data/total/all_transactions.csv
```

#### 3. A/B Testing New Patterns
```bash
# Test new patterns on subset of data
kiro-budget categorize --input test_data.csv --dry-run
```

## Troubleshooting

### Common Issues and Solutions

#### 1. "No categories configuration found"

**Problem**: Missing or invalid categories.yaml file

**Solutions**:
```bash
# Create default configuration
kiro-budget init-categories

# Validate existing configuration
kiro-budget validate-config

# Check file permissions
ls -la categories.yaml
```

#### 2. "AI API key not found"

**Problem**: Missing or invalid API keys for AI services

**Solutions**:
```bash
# Set OpenAI API key
export OPENAI_API_KEY="your_key_here"

# Verify key is set
echo $OPENAI_API_KEY

# Disable AI if not needed
# Edit categories.yaml: ai_config.enabled: false
```

#### 3. "Low categorization accuracy"

**Problem**: Many transactions categorized as "Uncategorized"

**Solutions**:
1. **Review and add patterns**:
   ```bash
   # Find common uncategorized merchants
   kiro-budget categorization-stats --detailed
   
   # Add patterns for common merchants
   kiro-budget manage-categories add "New_Category" --pattern "COMMON_MERCHANT"
   ```

2. **Lower confidence threshold**:
   ```yaml
   # In categories.yaml
   confidence_threshold: 0.6  # Lower from 0.7
   ```

3. **Enable AI categorization**:
   ```yaml
   ai_config:
     enabled: true
     primary_service: "openai"
   ```

#### 4. "Conflicting category assignments"

**Problem**: Similar transactions getting different categories

**Solutions**:
1. **Check pattern specificity**:
   ```yaml
   # Ensure more specific patterns have higher specificity
   Gas:
     patterns:
     - pattern: "COSTCO GAS"      # Very specific
       specificity: "very_high"
     - pattern: "COSTCO"          # Less specific
       specificity: "high"
   ```

2. **Review pattern conflicts**:
   ```bash
   # Use validation to find conflicts
   kiro-budget validate-config --check-conflicts
   ```

#### 5. "High AI API costs"

**Problem**: Unexpected high costs from AI services

**Solutions**:
1. **Enable aggressive caching**:
   ```yaml
   ai_config:
     cache_responses: true
     cache_duration_days: 90
   ```

2. **Set cost limits**:
   ```yaml
   ai_config:
     max_cost_per_month: 10.0
     rate_limit_per_minute: 10
   ```

3. **Use cheaper AI service**:
   ```yaml
   ai_config:
     primary_service: "claude"  # Generally cheaper than OpenAI
   ```

#### 6. "Slow categorization performance"

**Problem**: Categorization takes too long for large datasets

**Solutions**:
1. **Optimize patterns**:
   ```yaml
   # Use substring instead of regex when possible
   - pattern: "STARBUCKS"        # Fast substring
     type: "substring"
   # Instead of:
   # - pattern: ".*STARBUCKS.*"  # Slower regex
   #   type: "regex"
   ```

2. **Batch processing**:
   ```bash
   # Process in smaller batches
   kiro-budget categorize --batch-size 500
   ```

3. **Disable expensive features temporarily**:
   ```yaml
   ai_config:
     enabled: false
   ml_config:
     enabled: false
   ```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Set debug environment variable
export KIRO_DEBUG=1

# Run categorization with debug output
kiro-budget categorize --input data.csv --verbose

# Check debug logs
tail -f logs/categorization_debug.log
```

### Configuration Validation

Use the built-in validation tools:

```bash
# Comprehensive configuration check
kiro-budget validate-config --detailed

# Check for pattern conflicts
kiro-budget validate-config --check-conflicts

# Validate against sample data
kiro-budget validate-config --test-data sample_transactions.csv
```

### Performance Profiling

Profile categorization performance:

```bash
# Generate performance report
kiro-budget categorize --input data.csv --profile performance_report.json

# Analyze bottlenecks
kiro-budget analyze-performance performance_report.json
```

## API Reference

### Python API Usage

#### Basic Categorization

```python
from kiro_budget.categorizers import CategoryEngine, Transaction
from datetime import datetime

# Initialize engine with configuration
engine = CategoryEngine("categories.yaml")

# Create transaction
transaction = Transaction(
    date=datetime(2024, 1, 15),
    amount=-67.89,
    description="WHOLE FOODS MARKET #10234",
    account="Checking",
    institution="Chase",
    transaction_id="txn_123"
)

# Categorize single transaction
result = engine.categorize_transaction(transaction)
print(f"Category: {result.category}")
print(f"Confidence: {result.confidence}")
print(f"Method: {result.method}")
print(f"Reasoning: {result.reasoning}")
```

#### Batch Categorization

```python
# Categorize multiple transactions
transactions = [transaction1, transaction2, transaction3]
results = engine.batch_categorize(transactions)

for transaction, result in zip(transactions, results):
    print(f"{transaction.description} -> {result.category} ({result.confidence:.2f})")
```

#### Configuration Management

```python
from kiro_budget.categorizers import CategoryStorage, CategoryManager

# Load configuration
storage = CategoryStorage("categories.yaml")
config = storage.load_categories()

# Manage categories
manager = CategoryManager(storage)

# Add new category
manager.add_category("My_Category", [
    {"pattern": "MY_MERCHANT", "confidence": 0.90, "type": "substring"}
])

# Remove category
manager.remove_category("Old_Category")

# List all categories
categories = manager.list_categories()
```

#### Pattern Matching

```python
from kiro_budget.categorizers import PatternMatcher

# Initialize pattern matcher
matcher = PatternMatcher()
matcher.load_patterns_from_config("categories.yaml")

# Test pattern matching
matches = matcher.match_patterns("COSTCO WHSE #1029")
for match in matches:
    print(f"Category: {match.category}, Confidence: {match.confidence}")
```

#### AI Integration

```python
from kiro_budget.categorizers import AICategorizer

# Initialize AI categorizer
ai_categorizer = AICategorizer(
    api_key="your_openai_key",
    service="openai",
    cache_enabled=True
)

# Categorize with AI
result = ai_categorizer.categorize_with_ai(
    description="UNKNOWN MERCHANT #123",
    amount=45.67
)
print(f"AI Category: {result.category}")
```

### Data Models

#### Transaction Model

```python
@dataclass
class Transaction:
    date: datetime
    amount: float
    description: str
    account: str
    institution: str
    transaction_id: str
    category: Optional[str] = None
    confidence: Optional[float] = None
    method: Optional[str] = None
```

#### CategoryResult Model

```python
@dataclass
class CategoryResult:
    category: str
    confidence: float
    method: str  # "pattern", "ai", "ml", "manual"
    reasoning: Optional[str] = None
    pattern_used: Optional[str] = None
    processing_time: Optional[float] = None
```

#### CategoryMatch Model

```python
@dataclass
class CategoryMatch:
    category: str
    pattern: str
    confidence: float
    match_type: str  # "exact", "substring", "regex"
    specificity: str  # "very_high", "high", "medium", "low"
```

### Error Handling

```python
from kiro_budget.categorizers.error_handler import CategorizationError

try:
    result = engine.categorize_transaction(transaction)
except CategorizationError as e:
    print(f"Categorization failed: {e}")
    # Handle error appropriately
```

### Custom Extensions

#### Custom Pattern Matcher

```python
from kiro_budget.categorizers.interfaces import PatternMatcherInterface

class CustomPatternMatcher(PatternMatcherInterface):
    def match_patterns(self, description: str) -> List[CategoryMatch]:
        # Implement custom matching logic
        pass
    
    def add_pattern(self, category: str, pattern: str, confidence: float) -> None:
        # Implement pattern addition
        pass

# Use custom matcher
engine = CategoryEngine("categories.yaml", pattern_matcher=CustomPatternMatcher())
```

#### Custom AI Service

```python
from kiro_budget.categorizers.interfaces import AICategorizerInterface

class CustomAIService(AICategorizerInterface):
    def categorize_with_ai(self, description: str, amount: float) -> Optional[CategoryResult]:
        # Implement custom AI integration
        pass

# Use custom AI service
engine = CategoryEngine("categories.yaml", ai_categorizer=CustomAIService())
```

---

This documentation provides comprehensive coverage of the Transaction Categorization System. For additional help or feature requests, please refer to the project repository or contact the development team.