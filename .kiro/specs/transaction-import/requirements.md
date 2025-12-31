# Requirements Document

## Introduction

The Transaction Import module consolidates all processed transaction CSV files from the `data/` directory into a single unified CSV file in `data/total/`. It handles deduplication of transactions that may appear in multiple overlapping source files (e.g., QFX exports and PDF statement extracts for the same account/period).

## Glossary

- **Importer**: The module responsible for reading, deduplicating, and consolidating transaction data
- **Source_File**: A processed CSV file in the `data/{institution}/` directories containing transaction records
- **Consolidated_File**: The single output CSV file containing all deduplicated transactions
- **Duplicate_Transaction**: Two or more transaction records representing the same real-world transaction, potentially from different source files
- **Transaction_Signature**: A hash-based identifier derived from transaction amount, normalized description, and account to detect duplicates
- **Date_Tolerance**: The maximum number of days difference allowed between transaction dates when matching duplicates (accounts for posting vs transaction date differences)

## Requirements

### Requirement 1: Scan and Load Source Files

**User Story:** As a user, I want the importer to automatically find and load all transaction CSV files from the data directory, so that I don't have to specify each file manually.

#### Acceptance Criteria

1. WHEN the import command is executed, THE Importer SHALL scan all subdirectories of `data/` for CSV files matching the transaction format
2. WHEN a CSV file is found, THE Importer SHALL validate that it contains the required columns: date, amount, description, account, account_name, account_type, institution
3. IF a CSV file is missing required columns, THEN THE Importer SHALL fail with a descriptive error message identifying the problematic file
4. THE Importer SHALL exclude the `data/total/` and `data/processed/` directories from scanning
5. WHEN loading transactions, THE Importer SHALL parse dates, amounts, and other fields into appropriate data types

### Requirement 2: Deduplicate Transactions

**User Story:** As a user, I want duplicate transactions from overlapping files to be automatically detected and merged, so that my consolidated file contains each real transaction only once.

#### Acceptance Criteria

1. THE Importer SHALL generate a transaction signature from amount, normalized description, and account identifier
2. WHEN two transactions have the same signature and dates within the Date_Tolerance (3 days), THE Importer SHALL consider them duplicates
3. WHEN merging duplicate transactions, THE Importer SHALL prefer the transaction with a transaction_id (QFX/OFX source) over one without
4. WHEN merging duplicate transactions, THE Importer SHALL preserve the most complete data (category, balance) from all duplicate sources
5. THE Importer SHALL normalize transaction descriptions by removing location codes, reference numbers, and common suffixes before signature generation

### Requirement 3: Generate Consolidated Output

**User Story:** As a user, I want all my transactions consolidated into a single CSV file, so that I can analyze my complete financial picture in one place.

#### Acceptance Criteria

1. THE Importer SHALL write the consolidated transactions to `data/total/all_transactions.csv`
2. THE Importer SHALL create the `data/total/` directory if it does not exist
3. THE Consolidated_File SHALL contain the same columns as the source files: date, amount, description, account, account_name, account_type, institution, transaction_id, category, balance
4. THE Importer SHALL sort transactions by date in ascending order
5. WHEN the import completes successfully, THE Importer SHALL report statistics including: total source files processed, total input transactions, duplicates removed, final transaction count

### Requirement 4: CLI Integration

**User Story:** As a user, I want to run the import through the existing CLI, so that I have a consistent interface for all budget operations.

#### Acceptance Criteria

1. THE CLI SHALL provide an `import` subcommand under the existing `process` command structure
2. WHEN the import command is executed, THE Importer SHALL process all available data files
3. IF the import encounters an unrecoverable error, THEN THE CLI SHALL exit with a non-zero status code and descriptive error message
4. WHEN the import completes, THE CLI SHALL display a summary of the import operation

### Requirement 5: Error Handling

**User Story:** As a user, I want clear error messages when something goes wrong, so that I can fix issues and retry.

#### Acceptance Criteria

1. IF a source file cannot be parsed, THEN THE Importer SHALL fail immediately with the file path and error details
2. IF a transaction contains invalid data (malformed date, non-numeric amount), THEN THE Importer SHALL fail with the file path, line number, and field that caused the error
3. IF the output directory cannot be created or written to, THEN THE Importer SHALL fail with a filesystem error message
4. THE Importer SHALL validate data consistency before writing output
