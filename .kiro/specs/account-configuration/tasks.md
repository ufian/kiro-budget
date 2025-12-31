# Implementation Plan: Account Configuration

## Overview

This implementation adds account configuration support to enrich transactions with human-readable account names and types. The work is organized into data models, configuration loading, transaction enrichment, CSV output updates, and CLI tooling.

## Tasks

- [x] 1. Create data models for account configuration
  - [x] 1.1 Add AccountConfig dataclass to models/core.py
    - Fields: account_id, institution, account_name, account_type, description
    - _Requirements: 2.1, 2.2, 2.3, 2.5_
  - [x] 1.2 Add EnrichedTransaction dataclass to models/core.py
    - Extend Transaction with account_name and account_type fields
    - _Requirements: 3.1, 3.2_
  - [ ]* 1.3 Write property test for AccountConfig validation
    - **Property 2: Config Validation Completeness**
    - **Validates: Requirements 2.2, 2.3, 2.4**

- [x] 2. Implement AccountConfigLoader
  - [x] 2.1 Create utils/account_config.py with AccountConfigLoader class
    - Load YAML from raw/accounts.yaml
    - Parse hierarchical structure (institution → account_id → properties)
    - Store configs in dict keyed by (institution, account_id) tuple
    - _Requirements: 1.1, 1.4, 2.1_
  - [x] 2.2 Implement validation logic in AccountConfigLoader
    - Validate required fields (account_name, account_type)
    - Validate account_type enum values
    - Log warnings for invalid entries
    - _Requirements: 2.2, 2.3, 2.4_
  - [x] 2.3 Implement error handling for missing/invalid config file
    - Handle FileNotFoundError gracefully
    - Handle YAML parsing errors gracefully
    - _Requirements: 1.2, 1.3_
  - [ ]* 2.4 Write property test for configuration round-trip
    - **Property 1: Configuration Round-Trip**
    - **Validates: Requirements 1.1, 2.1**
  - [ ]* 2.5 Write property test for multi-institution isolation
    - **Property 6: Multi-Institution Isolation**
    - **Validates: Requirements 1.4, 3.4**

- [x] 3. Checkpoint - Ensure config loading tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement AccountEnricher
  - [x] 4.1 Create utils/account_enricher.py with AccountEnricher class
    - Accept AccountConfigLoader in constructor
    - Implement enrich() method for single transaction
    - Implement enrich_batch() method for multiple transactions
    - _Requirements: 3.1, 3.2, 3.4_
  - [x] 4.2 Implement default handling for unconfigured accounts
    - Use raw account_id as account_name when not configured
    - Default account_type to "debit" when not configured
    - _Requirements: 3.3_
  - [ ]* 4.3 Write property test for transaction enrichment
    - **Property 3: Transaction Enrichment Correctness**
    - **Validates: Requirements 3.1, 3.2, 3.4**
  - [ ]* 4.4 Write property test for unconfigured account defaults
    - **Property 4: Unconfigured Account Defaults**
    - **Validates: Requirements 3.3**

- [x] 5. Update CSV output
  - [x] 5.1 Modify CSVWriter to include account_name and account_type columns
    - Add new columns after existing account column
    - Preserve all existing columns and their order
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [x] 5.2 Integrate AccountEnricher into processing pipeline
    - Load account config at startup
    - Enrich transactions before CSV export
    - _Requirements: 3.1, 3.2_
  - [ ]* 5.3 Write property test for CSV column preservation
    - **Property 5: CSV Column Preservation**
    - **Validates: Requirements 4.3, 4.4**

- [x] 6. Checkpoint - Ensure enrichment and CSV tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Add CLI tooling and documentation
  - [x] 7.1 Add CLI command to generate sample accounts.yaml template
    - Create command: `python -m kiro_budget.cli generate-accounts-template`
    - Output to raw/accounts.yaml.example
    - Include comments explaining each option
    - _Requirements: 5.1, 5.2, 5.3_
  - [x] 7.2 Create documentation in docs/accounts_configuration.md
    - Explain configuration file format
    - Provide examples for common scenarios
    - Document error handling behavior
    - _Requirements: 5.4_
  - [ ]* 7.3 Write unit tests for CLI template generation
    - Verify template file is created
    - Verify template contains multiple institutions
    - Verify template contains explanatory comments
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
