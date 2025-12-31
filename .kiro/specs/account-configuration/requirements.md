# Requirements Document

## Introduction

This feature adds account configuration support to the kiro-budget parser. Users can define human-readable account names and account types (debit/credit) in a centralized `accounts.yaml` file located in the `raw/` folder. During CSV export, transactions are enriched with the configured account name and type, enabling better identification and analysis of financial data across multiple institutions.

## Glossary

- **Account_Configuration_System**: The system responsible for loading, validating, and applying account configurations during transaction processing
- **Account_ID**: The unique identifier extracted from source files (e.g., last 4 digits of account number like "0547")
- **Account_Name**: A human-readable label for an account (e.g., "Main Checking", "Travel Credit Card")
- **Account_Type**: Classification of account as either "debit" (checking/savings) or "credit" (credit cards)
- **Institution**: The financial institution that owns the account (e.g., "firsttech", "chase")
- **Accounts_Config_File**: The YAML configuration file located at `raw/accounts.yaml`

## Requirements

### Requirement 1: Account Configuration File

**User Story:** As a user, I want to define account configurations in a YAML file, so that I can assign human-readable names and types to my accounts.

#### Acceptance Criteria

1. THE Account_Configuration_System SHALL read configuration from `raw/accounts.yaml`
2. WHEN the accounts.yaml file does not exist, THE Account_Configuration_System SHALL continue processing without account enrichment
3. WHEN the accounts.yaml file contains invalid YAML syntax, THE Account_Configuration_System SHALL log an error and continue processing without account enrichment
4. THE Account_Configuration_System SHALL support configuration for multiple institutions in a single file

### Requirement 2: Account Configuration Schema

**User Story:** As a user, I want a clear configuration schema, so that I can easily define my accounts with names and types.

#### Acceptance Criteria

1. THE Accounts_Config_File SHALL support a hierarchical structure: institution → account_id → properties
2. THE Account_Configuration_System SHALL require an `account_name` property for each configured account
3. THE Account_Configuration_System SHALL require an `account_type` property with values "debit" or "credit"
4. WHEN an account_type value is not "debit" or "credit", THE Account_Configuration_System SHALL log a warning and treat it as "debit"
5. THE Account_Configuration_System SHALL support an optional `description` property for additional account notes

### Requirement 3: Transaction Enrichment

**User Story:** As a user, I want my transactions enriched with account information during CSV export, so that I can identify which account each transaction belongs to.

#### Acceptance Criteria

1. WHEN a transaction's account_id matches a configured account, THE Account_Configuration_System SHALL add the account_name to the transaction
2. WHEN a transaction's account_id matches a configured account, THE Account_Configuration_System SHALL add the account_type to the transaction
3. WHEN a transaction's account_id does not match any configured account, THE Account_Configuration_System SHALL use the raw account_id as account_name and "debit" as default account_type
4. THE Account_Configuration_System SHALL match accounts using both institution name and account_id

### Requirement 4: CSV Output Enhancement

**User Story:** As a user, I want the exported CSV to include account name and type columns, so that I can analyze transactions by account.

#### Acceptance Criteria

1. THE Account_Configuration_System SHALL add an `account_name` column to the CSV output
2. THE Account_Configuration_System SHALL add an `account_type` column to the CSV output
3. THE Account_Configuration_System SHALL preserve all existing CSV columns and their order
4. THE Account_Configuration_System SHALL place new columns after the existing `account` column

### Requirement 5: Configuration Documentation

**User Story:** As a user, I want clear documentation on how to set up the accounts configuration, so that I can configure my accounts correctly.

#### Acceptance Criteria

1. THE Account_Configuration_System SHALL generate a sample accounts.yaml template when requested via CLI
2. THE sample template SHALL include examples for multiple institutions
3. THE sample template SHALL include comments explaining each configuration option
4. THE documentation SHALL be included in the project's docs folder
