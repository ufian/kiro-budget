# Implementation Plan: Transaction Import

## Overview

Implement the transaction import module that consolidates all processed CSV files from `data/` subdirectories into a single deduplicated file at `data/total/all_transactions.csv`. The implementation extends the existing CLI with an `import` subcommand.

## Current State Analysis

- **ImportError/ImportResult**: Not implemented - need to create `src/kiro_budget/utils/importer.py`
- **TransactionImporter class**: Not implemented
- **CLI import command**: Not implemented
- **DuplicateDetector**: Already exists in `utils/duplicate_detector.py` with fuzzy matching support (3-day tolerance)
- **CSV Writer**: Already exists with proper column format including account_name, account_type
- **Transaction/EnrichedTransaction models**: Already exist in `models/core.py`

## Tasks

- [x] 1. Create ImportError exception and ImportResult data class
  - Create `src/kiro_budget/utils/importer.py` with ImportError exception class
  - ImportError should include optional file_path, line_number, and field context
  - Add ImportResult dataclass with success, source_files_count, total_input_transactions, duplicates_removed, final_transaction_count, output_file, errors, warnings fields
  - _Requirements: 5.1, 5.2, 5.3, 3.5_

- [x] 2. Implement file scanning functionality
  - [x] 2.1 Implement TransactionImporter class with scan_source_files method
    - Create TransactionImporter class with data_directory and output_directory parameters
    - Recursively find all CSV files in data/ subdirectories
    - Exclude data/total/ and data/processed/ directories
    - Return list of Path objects
    - _Requirements: 1.1, 1.4_

  - [ ]* 2.2 Write property test for file scanner completeness
    - **Property 1: File Scanner Completeness**
    - **Validates: Requirements 1.1, 1.4**

- [x] 3. Implement CSV validation and loading
  - [x] 3.1 Implement validate_csv_structure method
    - Check for required columns: date, amount, description, account, account_name, account_type, institution
    - Raise ImportError with file path if validation fails
    - _Requirements: 1.2, 1.3_

  - [ ]* 3.2 Write property test for column validation
    - **Property 2: Column Validation Correctness**
    - **Validates: Requirements 1.2, 1.3**

  - [x] 3.3 Implement load_transactions method
    - Parse CSV rows into EnrichedTransaction objects (to preserve account_name, account_type)
    - Convert date strings to datetime, amounts to Decimal
    - Raise ImportError with file, line, field on parse failure
    - _Requirements: 1.5, 5.2_

  - [ ]* 3.4 Write property test for transaction round-trip
    - **Property 3: Transaction Round-Trip Consistency**
    - **Validates: Requirements 1.5**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement deduplication integration
  - [x] 5.1 Integrate with existing DuplicateDetector
    - Reuse DuplicateDetector from utils/duplicate_detector.py
    - Use fuzzy matching mode (ignore_transaction_ids=True)
    - Use existing 3-day date tolerance configuration
    - _Requirements: 2.1, 2.2, 2.5_

  - [ ]* 5.2 Write property test for signature determinism
    - **Property 4: Signature Determinism**
    - **Validates: Requirements 2.1, 2.5**

  - [ ]* 5.3 Write property test for duplicate detection accuracy
    - **Property 5: Duplicate Detection Accuracy**
    - **Validates: Requirements 2.2**

  - [x] 5.4 Verify merge priority logic works correctly
    - Existing DuplicateDetector already prefers transactions with transaction_id
    - Existing merge logic preserves category and balance from any source
    - Add any necessary wrapper methods if needed
    - _Requirements: 2.3, 2.4_

  - [ ]* 5.5 Write property test for merge data preservation
    - **Property 6: Merge Data Preservation**
    - **Validates: Requirements 2.3, 2.4**

- [x] 6. Implement output generation
  - [x] 6.1 Implement write_consolidated_output method
    - Create data/total/ directory if needed
    - Write transactions to all_transactions.csv using existing CSVWriter
    - Sort by date ascending before writing
    - Include all required columns (date, amount, description, account, account_name, account_type, institution, transaction_id, category, balance)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 6.2 Write property test for output format correctness
    - **Property 7: Output Format Correctness**
    - **Validates: Requirements 3.3, 3.4**

  - [x] 6.3 Implement statistics calculation
    - Track source files count, input transactions, duplicates removed, final count
    - Return ImportResult with all statistics
    - Ensure: final_transaction_count = total_input_transactions - duplicates_removed
    - _Requirements: 3.5_

  - [ ]* 6.4 Write property test for statistics arithmetic
    - **Property 8: Statistics Arithmetic Consistency**
    - **Validates: Requirements 3.5**

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement main import_all orchestration
  - [x] 8.1 Implement import_all method
    - Orchestrate scan → load → deduplicate → write pipeline
    - Collect and return ImportResult
    - Handle errors with proper context (file path, line number, field)
    - Fail immediately on first error with descriptive message
    - _Requirements: 1.1, 2.2, 3.1, 5.1_

- [x] 9. CLI integration
  - [x] 9.1 Add import subcommand to CLI
    - Add `import` command to existing Click CLI in cli.py
    - Instantiate TransactionImporter and call import_all()
    - Display summary on completion (files processed, transactions, duplicates removed)
    - Exit with non-zero code on ImportError
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 9.2 Write unit tests for CLI import command
    - Test successful import displays summary
    - Test error returns non-zero exit code
    - _Requirements: 4.1, 4.3_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation reuses existing DuplicateDetector from utils/duplicate_detector.py
- The implementation reuses existing CSVWriter from utils/csv_writer.py
- Use EnrichedTransaction model to preserve account_name and account_type through the pipeline
