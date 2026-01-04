# Transaction Categorization Examples

This directory contains example configuration files for different use cases of the transaction categorization system. These examples demonstrate best practices and provide starting points for your own categorization setup.

## Available Examples

### 1. Personal Budget (`personal_budget.yaml`)
**Use Case**: Individual or couple managing personal finances

**Features**:
- Essential living expenses (groceries, housing, utilities)
- Transportation costs (gas, car maintenance, rideshare)
- Personal care and healthcare
- Entertainment and dining
- Savings and insurance categories
- Conservative AI cost limits ($25/month)

**Best For**:
- Single individuals
- Couples without children
- Simple personal finance tracking
- Users new to categorization

### 2. Business Budget (`business_budget.yaml`)
**Use Case**: Small business owners and freelancers tracking business expenses

**Features**:
- Tax-deductible business categories
- Office supplies and equipment
- Professional services (legal, accounting)
- Marketing and advertising expenses
- Business travel and meals
- Software subscriptions and licenses
- Higher AI cost limits ($100/month)
- Higher confidence thresholds for accuracy

**Best For**:
- Small business owners
- Freelancers and consultants
- Tax preparation and deduction tracking
- Professional expense management

### 3. Family Budget (`family_budget.yaml`)
**Use Case**: Families with children managing household finances

**Features**:
- Child-specific categories (childcare, education, activities)
- Family entertainment and activities
- Children's clothing and toys
- Healthcare including pediatric care
- Family-friendly restaurants and venues
- Education savings (529 plans)
- Moderate AI cost limits ($40/month)

**Best For**:
- Families with children
- Households with multiple dependents
- Parents tracking child-related expenses
- Family budget planning

### 4. Common Merchants (`common_merchants.yaml`)
**Use Case**: Comprehensive reference of major retailer patterns

**Features**:
- Extensive list of major grocery chains
- Gas station and fuel provider patterns
- Fast food and restaurant chains
- Department stores and retailers
- Pharmacy and healthcare providers
- Utility companies and service providers
- Entertainment and streaming services

**Best For**:
- Reference when adding new patterns
- Understanding pattern specificity levels
- Comprehensive merchant coverage
- Building custom configurations

## How to Use These Examples

### 1. Choose Your Starting Point

Select the example that best matches your use case:

```bash
# Copy personal budget example
cp examples/categorization/personal_budget.yaml categories.yaml

# Copy business budget example
cp examples/categorization/business_budget.yaml categories.yaml

# Copy family budget example
cp examples/categorization/family_budget.yaml categories.yaml
```

### 2. Customize for Your Needs

Edit the copied file to match your specific requirements:

1. **Add Your Merchants**: Look at your transaction history and add patterns for merchants you frequent
2. **Adjust Categories**: Add, remove, or rename categories to match your budgeting style
3. **Tune Confidence Levels**: Adjust confidence scores based on your accuracy preferences
4. **Configure AI Settings**: Set API keys and cost limits appropriate for your usage

### 3. Test and Refine

```bash
# Test categorization on your data
kiro-budget categorize --input data/total/all_transactions.csv --dry-run

# Review results and adjust patterns
kiro-budget review-categories --confidence-threshold 0.7

# Validate your configuration
kiro-budget validate-config
```

## Configuration Tips

### Pattern Specificity Guidelines

Use the examples to understand specificity levels:

- **very_high**: Most specific patterns (e.g., "COSTCO GAS" vs "COSTCO")
- **high**: Specific merchant names (e.g., "STARBUCKS")
- **medium**: Category patterns (e.g., ".*RESTAURANT.*")
- **low**: Broad patterns (e.g., ".*STORE.*")

### Confidence Score Guidelines

Follow the patterns in the examples:

- **0.95-1.0**: Very specific merchant names
- **0.85-0.94**: Common merchant chains
- **0.70-0.84**: Category patterns
- **0.50-0.69**: Broad patterns (use sparingly)

### AI Cost Management

The examples show different AI cost strategies:

- **Personal**: $25/month (conservative)
- **Business**: $100/month (accuracy-focused)
- **Family**: $40/month (moderate usage)

Adjust based on your transaction volume and accuracy needs.

## Combining Examples

You can combine patterns from multiple examples:

```bash
# Start with personal budget
cp examples/categorization/personal_budget.yaml categories.yaml

# Add business patterns for side income
# (manually copy relevant business categories)

# Reference common merchants for additional patterns
# (use common_merchants.yaml as a lookup reference)
```

## Pattern Maintenance

### Regular Updates

1. **Monthly Review**: Check "Uncategorized" transactions and add new patterns
2. **Quarterly Cleanup**: Remove unused categories and consolidate similar patterns
3. **Annual Overhaul**: Review all patterns and update based on spending changes

### Best Practices

1. **Start Simple**: Begin with high-confidence patterns and add complexity gradually
2. **Test Changes**: Use `--dry-run` to test pattern changes before applying
3. **Monitor Accuracy**: Use `categorization-stats` to track accuracy over time
4. **Backup Regularly**: The system creates automatic backups, but manual backups are recommended

### Common Customizations

Based on the examples, here are common customizations:

#### Adding New Categories

```yaml
My_Custom_Category:
  patterns:
  - pattern: "MY_MERCHANT"
    confidence: 0.90
    type: "substring"
    specificity: "high"
```

#### Handling Merchant Variations

```yaml
Coffee_Shops:
  patterns:
  - pattern: "STARBUCKS"           # Main pattern
  - pattern: "SBUX"                # Abbreviated form
  - pattern: "STARBUCKS STORE"     # Full name variation
```

#### Geographic Patterns

```yaml
Regional_Grocery:
  patterns:
  - pattern: "H-E-B"               # Texas
  - pattern: "WEGMANS"             # Northeast
  - pattern: "PUBLIX"              # Southeast
```

## Troubleshooting

### Common Issues

1. **Low Accuracy**: Start with a more comprehensive example (common_merchants.yaml)
2. **High AI Costs**: Reduce `max_cost_per_month` and enable aggressive caching
3. **Conflicting Patterns**: Use the specificity system shown in examples
4. **Missing Categories**: Add categories specific to your spending patterns

### Getting Help

1. **Validation**: Use `kiro-budget validate-config` to check for errors
2. **Statistics**: Use `kiro-budget categorization-stats` to analyze performance
3. **Documentation**: Refer to the main documentation at `docs/transaction_categorization.md`

## Contributing

If you create useful patterns or configurations, consider contributing them back:

1. Test your configuration thoroughly
2. Document any special use cases or requirements
3. Follow the naming and structure conventions shown in these examples
4. Submit as a pull request with clear documentation

---

These examples provide a solid foundation for most categorization needs. Start with the closest match to your situation, then customize based on your specific requirements and spending patterns.