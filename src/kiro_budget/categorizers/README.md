# Transaction Categorization System

A comprehensive system for automatically categorizing financial transactions using pattern matching, AI-powered categorization, and machine learning techniques.

## Overview

The transaction categorization system provides intelligent categorization of financial transactions through multiple methods:

- **Pattern Matching**: Rule-based categorization using substring, regex, and exact matching
- **AI Categorization**: OpenAI/Claude integration for unknown merchants
- **User Learning**: Interactive feedback system that learns from user corrections
- **Category Management**: Hierarchical category organization with validation
- **CLI Integration**: Command-line tools for batch processing and configuration

## Architecture

### Core Components

1. **CategoryEngine** (`category_engine.py`): Main orchestrator that coordinates all categorization methods
2. **PatternMatcher** (`pattern_matcher.py`): Pattern-based categorization with specificity scoring
3. **AICategorizer** (`ai_categorizer.py`): AI-powered categorization with caching and cost control
4. **UserInteraction** (`user_interaction.py`): Interactive learning and feedback system
5. **CategoryManager** (`category_manager.py`): Category lifecycle management with hierarchy support
6. **CategoryStorage** (`storage.py`): YAML-based configuration storage with validation

### Data Models

- **Transaction**: Core transaction data structure
- **CategoryResult**: Categorization result with confidence and method tracking
- **CategoryMatch**: Pattern matching result with specificity scoring
- **CategoryDefinition**: Category configuration with patterns and metadata

## Features

### Pattern-Based Categorization

- **Multiple Pattern Types**: Substring, regex, and exact matching
- **Specificity Scoring**: Handles conflicts like "COSTCO GAS" vs "COSTCO" correctly
- **Case-Insensitive Matching**: Robust merchant name matching
- **Confidence Scoring**: 0.0-1.0 confidence scores for all matches

### AI-Powered Categorization

- **OpenAI Integration**: GPT-based categorization for unknown merchants
- **Response Caching**: Minimizes API costs through intelligent caching
- **Rate Limiting**: Configurable rate limits and cost controls
- **Fallback Support**: Multiple AI service support with automatic fallback

### User Learning System

- **Interactive Review**: CLI-based review of low-confidence transactions
- **Pattern Learning**: Automatically creates patterns from user feedback
- **Batch Processing**: Efficient review of multiple similar transactions
- **Inconsistency Detection**: Identifies and suggests fixes for conflicting categorizations

### Category Management

- **Hierarchical Categories**: Support for parent-child category relationships
- **Validation**: Name validation, circular reference detection, and integrity checks
- **CRUD Operations**: Add, remove, modify categories with transaction reassignment
- **Backup System**: Automatic configuration backups before changes

## Usage

### CLI Commands

```bash
# Initialize categories configuration
kiro-budget init-categories

# Categorize transactions in CSV file
kiro-budget categorize --input data/total/all_transactions.csv

# Interactive review of low-confidence categorizations
kiro-budget review-categories --confidence-threshold 0.7

# Show help for any command
kiro-budget categorize --help
```

### Python API

```python
from kiro_budget.categorizers import CategoryEngine, Transaction
from datetime import datetime

# Initialize category engine
engine = CategoryEngine("categories.yaml")

# Categorize a transaction
transaction = Transaction(
    date=datetime.now(),
    amount=-50.0,
    description="COSTCO WHSE #1029",
    account="Checking",
    institution="Chase"
)

result = engine.categorize_transaction(transaction)
print(f"Category: {result.category}")
print(f"Confidence: {result.confidence}")
print(f"Method: {result.method}")
```

### Configuration

Categories are configured in YAML format with human-readable structure:

```yaml
version: "1.0"
default_category: "Uncategorized"
confidence_threshold: 0.7

categories:
  Groceries:
    patterns:
      - pattern: "COSTCO"
        confidence: 0.95
        type: "substring"
        specificity: "high"
      - pattern: "COSTCO GAS"
        confidence: 0.95
        type: "substring"
        specificity: "very_high"  # Higher specificity wins
    
  Gas:
    patterns:
      - pattern: ".*GAS.*"
        confidence: 0.85
        type: "regex"
        specificity: "medium"

ai_config:
  enabled: true
  primary_service: "openai"
  cache_responses: true
  max_cost_per_month: 50.0
```

## Integration

### CSV Workflow Integration

The system integrates seamlessly with the existing CSV processing workflow:

1. **Raw File Processing**: `kiro-budget process` converts files to CSV
2. **Consolidation**: `python scripts/export/build_total_csv.py` creates unified CSV
3. **Categorization**: `kiro-budget categorize` adds category columns
4. **Review**: `kiro-budget review-categories` for interactive improvement

### Monthly Reports

Categorized transactions can be included in monthly summary reports with category-based spending analysis.

## Performance

- **Batch Processing**: Efficient processing of large transaction sets
- **Caching**: AI response caching reduces API costs and improves speed
- **Memory Efficient**: Streaming processing for large datasets
- **Concurrent Safe**: Thread-safe operations for parallel processing

## Testing

Comprehensive test suite with:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing  
- **Property Tests**: Universal correctness validation using Hypothesis
- **Mock Testing**: AI service mocking for reliable testing

Run tests with:
```bash
pytest tests/categorizers/ -v
```

## Configuration Files

### categories.yaml
Main configuration file with categories, patterns, and AI settings.

### Cache Files
- `.ai_cache.json`: AI response cache (auto-generated)
- `backups/`: Configuration backups (auto-generated)

## Error Handling

- **Graceful Degradation**: Falls back to simpler methods when advanced features fail
- **Validation**: Comprehensive input validation with helpful error messages
- **Logging**: Detailed logging for debugging and monitoring
- **Recovery**: Automatic recovery from temporary failures

## Future Enhancements

- **Machine Learning**: Scikit-learn integration for advanced categorization
- **Web Interface**: Browser-based category management and review
- **Import/Export**: Category rule sharing between users
- **Analytics**: Advanced categorization accuracy analytics

## Requirements Satisfied

This implementation satisfies all requirements from the transaction categorization specification:

- ✅ Single category assignment with confidence scores
- ✅ Pattern-based categorization with multiple types
- ✅ AI-powered categorization for unknown merchants  
- ✅ User interaction and learning capabilities
- ✅ Category management with hierarchical support
- ✅ YAML-based human-readable configuration
- ✅ CLI integration with existing workflow
- ✅ Comprehensive error handling and validation
- ✅ Performance optimization for large datasets
- ✅ Extensive testing and documentation