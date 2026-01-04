#!/bin/bash

# Deep Monthly Report Generator
# Automates the complete 4-step process for generating comprehensive monthly financial reports
# 
# Usage:
#   ./scripts/generate_deep_monthly_report.sh [options]
#
# Options:
#   --force         Force reprocessing of all raw files (ignore processing history)
#   --no-open       Don't automatically open the reports in browser
#   --help          Show this help message
#
# Steps performed:
#   1. Process raw files to CSV (with automatic sign detection)
#   2. Build consolidated transaction file (with duplicate detection)
#   3. Apply transaction categorization (pattern matching, ML, AI)
#   4. Generate interactive HTML reports (basic summary + category breakdown)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
FORCE_REPROCESS=false
OPEN_REPORT=true
SHOW_HELP=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_REPROCESS=true
            shift
            ;;
        --no-open)
            OPEN_REPORT=false
            shift
            ;;
        --help)
            SHOW_HELP=true
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Show help if requested
if [ "$SHOW_HELP" = true ]; then
    echo "Deep Monthly Report Generator"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --force         Force reprocessing of all raw files (ignore processing history)"
    echo "  --no-open       Don't automatically open the report in browser"
    echo "  --help          Show this help message"
    echo ""
    echo "This script automates the complete 4-step process:"
    echo "  1. Process raw files to CSV (with automatic sign detection)"
    echo "  2. Build consolidated transaction file (with duplicate detection)"
    echo "  3. Apply transaction categorization (pattern matching, ML, AI)"
    echo "  4. Generate interactive HTML reports (basic summary + category breakdown)"
    echo ""
    echo "Prerequisites:"
    echo "  - Virtual environment activated (source venv/bin/activate)"
    echo "  - Raw financial files in raw/ directory"
    echo "  - Account configuration at raw/accounts.yaml (optional)"
    echo "  - Category configuration at categories.yaml (for categorization)"
    exit 0
fi

# Function to print step headers
print_step() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to print warning messages
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "src/kiro_budget" ]; then
    # Try to find the correct directory
    if [ -f "../pyproject.toml" ] && [ -d "../src/kiro_budget" ]; then
        cd ..
        print_success "Changed to project root directory"
    elif [ -f "kiro-budget/pyproject.toml" ] && [ -d "kiro-budget/src/kiro_budget" ]; then
        cd kiro-budget
        print_success "Changed to kiro-budget project directory"
    else
        print_error "This script must be run from the kiro-budget project root directory or its parent"
        print_error "Looking for: pyproject.toml and src/kiro_budget directory"
        exit 1
    fi
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "Virtual environment not detected. Attempting to activate..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
        print_success "Virtual environment activated"
    else
        print_error "Virtual environment not found. Please run: python -m venv venv && source venv/bin/activate"
        exit 1
    fi
fi

# Check if raw directory exists
if [ ! -d "raw" ]; then
    print_error "Raw directory not found. Please create 'raw/' directory and add your financial files"
    exit 1
fi

# Check if categories.yaml exists
if [ ! -f "categories.yaml" ]; then
    print_warning "categories.yaml not found. Transaction categorization will use default patterns only"
    print_warning "Consider creating categories.yaml for better categorization results"
fi

# Count raw files
RAW_FILE_COUNT=$(find raw -type f \( -name "*.pdf" -o -name "*.qfx" -o -name "*.csv" \) | wc -l | tr -d ' ')
if [ "$RAW_FILE_COUNT" -eq 0 ]; then
    print_error "No financial files found in raw/ directory"
    print_error "Please add PDF, QFX, or CSV files to the raw/ directory"
    exit 1
fi

print_success "Found $RAW_FILE_COUNT raw financial files to process"

# Record start time
START_TIME=$(date +%s)

# Step 1: Process Raw Files to CSV
print_step "STEP 1: Processing Raw Files to CSV"
echo "Converting all raw financial files to standardized CSV format..."
echo "- Automatic file format detection (PDF, QFX, CSV)"
echo "- Automatic sign detection and correction"
echo "- Account enrichment from accounts.yaml"

if [ "$FORCE_REPROCESS" = true ]; then
    echo "- Force reprocessing enabled (ignoring processing history)"
    python -m kiro_budget.cli process --force
else
    python -m kiro_budget.cli process
fi

if [ $? -eq 0 ]; then
    print_success "Step 1 completed: Raw files processed to CSV"
else
    print_error "Step 1 failed: Raw file processing encountered errors"
    exit 1
fi

# Step 2: Build Consolidated Transaction File
print_step "STEP 2: Building Consolidated Transaction File"
echo "Combining all CSV files with advanced duplicate detection..."
echo "- Exact duplicate removal"
echo "- Fuzzy PDF vs QFX duplicate detection"
echo "- Chronological sorting"

python scripts/export/build_total_csv.py

if [ $? -eq 0 ]; then
    print_success "Step 2 completed: Consolidated transaction file created"
else
    print_error "Step 2 failed: Transaction consolidation encountered errors"
    exit 1
fi

# Check if consolidated file was created
if [ ! -f "data/total/all_transactions.csv" ]; then
    print_error "Consolidated transaction file not found at data/total/all_transactions.csv"
    exit 1
fi

# Step 3: Apply Transaction Categorization
print_step "STEP 3: Applying Transaction Categorization"
echo "Categorizing transactions using pattern matching, ML, and AI..."
echo "- Pattern-based categorization from categories.yaml"
echo "- Machine learning categorization for learned patterns"
echo "- AI-powered categorization for unknown merchants"
echo "- Confidence scoring and method tracking"

python scripts/export/add_categories_to_csv.py

if [ $? -eq 0 ]; then
    print_success "Step 3 completed: Transaction categorization applied"
else
    print_error "Step 3 failed: Transaction categorization encountered errors"
    exit 1
fi

# Step 4a: Generate Basic Monthly Summary Report
print_step "STEP 4a: Generating Basic Monthly Summary Report"
echo "Creating HTML report with transfer pair detection..."
echo "- Credit card payment pair detection"
echo "- Internal transfer pair consolidation"
echo "- High-level income/spending/transfer analysis"
echo "- Interactive drill-down functionality"

python scripts/analysis/monthly_summary_report.py

if [ $? -eq 0 ]; then
    print_success "Step 4a completed: Basic monthly summary report generated"
else
    print_error "Step 4a failed: Basic report generation encountered errors"
    exit 1
fi

# Step 4b: Generate Enhanced Category Report
print_step "STEP 4b: Generating Enhanced Category Report"
echo "Creating detailed category breakdown report..."
echo "- Spending breakdown by category (Groceries, Gas, Restaurants, etc.)"
echo "- Category statistics and trends over time"
echo "- Interactive category drill-down"
echo "- Confidence indicators and method tracking"

python scripts/analysis/monthly_category_report.py

if [ $? -eq 0 ]; then
    print_success "Step 4b completed: Enhanced category report generated"
else
    print_error "Step 4b failed: Category report generation encountered errors"
    exit 1
fi

# Check if reports were created
BASIC_REPORT="data/reports/monthly_summary.html"
CATEGORY_REPORT="data/reports/monthly_category_report.html"

if [ ! -f "$BASIC_REPORT" ]; then
    print_error "Basic report file not found at $BASIC_REPORT"
    exit 1
fi

if [ ! -f "$CATEGORY_REPORT" ]; then
    print_error "Category report file not found at $CATEGORY_REPORT"
    exit 1
fi

# Calculate total execution time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Final success message
print_step "DEEP MONTHLY REPORT COMPLETE!"
print_success "All 4 steps completed successfully in ${DURATION} seconds"
echo ""
echo -e "${GREEN}📊 Basic Report:${NC} $BASIC_REPORT"
echo -e "${GREEN}📈 Category Report:${NC} $CATEGORY_REPORT"
echo -e "${GREEN}📋 Consolidated Data:${NC} data/total/all_transactions.csv"
echo -e "${GREEN}📊 Statistics:${NC} data/total/total_stats.json"
echo -e "${GREEN}🔍 Uncategorized:${NC} data/reports/uncategorized_transactions.csv"

# Show file sizes
if command -v du >/dev/null 2>&1; then
    BASIC_SIZE=$(du -h "$BASIC_REPORT" | cut -f1)
    CATEGORY_SIZE=$(du -h "$CATEGORY_REPORT" | cut -f1)
    DATA_SIZE=$(du -h "data/total/all_transactions.csv" | cut -f1)
    echo -e "${BLUE}📁 Basic Report Size:${NC} $BASIC_SIZE"
    echo -e "${BLUE}📁 Category Report Size:${NC} $CATEGORY_SIZE"
    echo -e "${BLUE}📁 Data Size:${NC} $DATA_SIZE"
fi

# Open reports in browser if requested
if [ "$OPEN_REPORT" = true ]; then
    echo ""
    echo "Opening reports in default browser..."
    
    # Cross-platform browser opening
    if command -v open >/dev/null 2>&1; then
        # macOS
        open "$BASIC_REPORT"
        sleep 1  # Small delay between opening files
        open "$CATEGORY_REPORT"
    elif command -v xdg-open >/dev/null 2>&1; then
        # Linux
        xdg-open "$BASIC_REPORT"
        sleep 1
        xdg-open "$CATEGORY_REPORT"
    elif command -v start >/dev/null 2>&1; then
        # Windows (Git Bash/WSL)
        start "$BASIC_REPORT"
        sleep 1
        start "$CATEGORY_REPORT"
    else
        print_warning "Could not automatically open browser. Please open:"
        echo "  • Basic Report: $BASIC_REPORT"
        echo "  • Category Report: $CATEGORY_REPORT"
    fi
fi

echo ""
print_success "Deep monthly report generation complete!"
echo -e "${BLUE}Next steps:${NC}"
echo "  • Review the basic HTML report for high-level monthly summaries"
echo "  • Review the category report for detailed spending breakdown"
echo "  • Click on any cell to drill down into underlying transactions"
echo "  • Check transfer pair consolidation to avoid double-counting"
echo "  • Review uncategorized transactions for pattern improvements"
echo "  • Use the consolidated CSV for further analysis if needed"
echo ""
echo -e "${BLUE}Report Types:${NC}"
echo "  • Basic Report: High-level income/spending/transfer analysis"
echo "  • Category Report: Detailed breakdown by spending categories"
echo "  • Both reports include interactive drill-down functionality"