"""Command-line interface for the financial data parser."""

import os
import sys
import click
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from .utils.config_manager import ConfigManager
from .utils.file_scanner import FileScanner, FormatDetector, ParserFactory
from .utils.processing_tracker import ProcessingTracker
from .utils.error_handler import ErrorHandler
from .utils.csv_writer import CSVWriter
from .utils.validation import ValidationEngine
from .models.core import ParserConfig, Transaction


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FinancialDataParserCLI:
    """Main CLI class for the financial data parser"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize CLI with configuration"""
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()
        self.error_handler = ErrorHandler()
        self.processing_tracker = ProcessingTracker(error_handler=self.error_handler)
        
        # Initialize components
        self.file_scanner = FileScanner(self.config)
        self.format_detector = FormatDetector(self.config)
        self.parser_factory = ParserFactory(self.config)
        self.csv_writer = CSVWriter(self.config)
        self.validation_engine = ValidationEngine()
    
    def process_files(self, 
                     file_paths: Optional[List[str]] = None,
                     directories: Optional[List[str]] = None,
                     force_reprocess: bool = False,
                     recursive: bool = True) -> Dict[str, Any]:
        """Process specified files or directories"""
        
        # Ensure output directory structure exists
        self._ensure_directory_structure()
        
        # Start batch processing
        self.processing_tracker.start_batch_processing()
        
        # Collect files to process
        files_to_process = []
        
        if file_paths:
            # Process specific files
            for file_path in file_paths:
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    files_to_process.append(file_path)
                else:
                    self.error_handler.log_warning(
                        f"File not found or not accessible: {file_path}",
                        "FILE_NOT_FOUND",
                        file_path=file_path
                    )
        
        if directories:
            # Process directories
            for directory in directories:
                if os.path.exists(directory) and os.path.isdir(directory):
                    found_files = self.file_scanner.scan_directory(directory, recursive)
                    files_to_process.extend(found_files)
                else:
                    self.error_handler.log_warning(
                        f"Directory not found or not accessible: {directory}",
                        "DIRECTORY_NOT_FOUND",
                        file_path=directory
                    )
        
        if not file_paths and not directories:
            # Default: process raw directory
            raw_dir = self.config.raw_directory
            if os.path.exists(raw_dir):
                files_to_process = self.file_scanner.scan_directory(raw_dir, recursive)
            else:
                self.error_handler.log_error(
                    f"Raw directory not found: {raw_dir}",
                    "DIRECTORY_NOT_FOUND",
                    file_path=raw_dir
                )
                return {'success': False, 'error': f'Raw directory not found: {raw_dir}'}
        
        if not files_to_process:
            self.error_handler.log_info("No files found to process")
            return {'success': True, 'message': 'No files found to process', 'files_processed': 0}
        
        # Filter files based on processing history
        skipped_count = 0
        if not force_reprocess:
            original_count = len(files_to_process)
            files_to_process = [
                f for f in files_to_process 
                if self.processing_tracker.should_process_file(f, force_reprocess)
            ]
            skipped_count = original_count - len(files_to_process)
            if skipped_count > 0:
                self.error_handler.log_info(f"Skipping {skipped_count} previously processed files")
        
        # Check if we should use batch processing with duplicate detection
        if len(files_to_process) > 1:
            # Process each file individually (no merging)
            processed_count = 0
            successful_count = 0
            total_files = len(files_to_process)
            
            for i, file_path in enumerate(files_to_process, 1):
                try:
                    # Progress reporting
                    self._report_progress(i, total_files, file_path)
                    
                    result = self._process_single_file(file_path)
                    self.processing_tracker.record_processing_result(result)
                    
                    processed_count += 1
                    if result.success:
                        successful_count += 1
                        
                except Exception as e:
                    self.error_handler.log_error(
                        f"Unexpected error processing {file_path}: {str(e)}",
                        "PROCESSING_ERROR",
                        file_path=file_path,
                        exception=e
                    )
        else:
            # Process single file with original logic
            processed_count = 0
            successful_count = 0
            total_files = len(files_to_process)
            
            for i, file_path in enumerate(files_to_process, 1):
                try:
                    # Progress reporting
                    self._report_progress(i, total_files, file_path)
                    
                    result = self._process_single_file(file_path)
                    self.processing_tracker.record_processing_result(result)
                    
                    processed_count += 1
                    if result.success:
                        successful_count += 1
                        
                except Exception as e:
                    self.error_handler.log_error(
                        f"Unexpected error processing {file_path}: {str(e)}",
                        "PROCESSING_ERROR",
                        file_path=file_path,
                        exception=e
                    )
        
        # Generate summary
        summary = self.processing_tracker.generate_batch_summary()
        summary.skipped_files = skipped_count
        
        return {
            'success': True,
            'files_processed': processed_count,
            'files_successful': successful_count,
            'files_failed': processed_count - successful_count,
            'files_skipped': skipped_count,
            'summary': summary
        }
    
    def _process_single_file(self, file_path: str):
        """Process a single file and return ProcessingResult"""
        from .models.core import ProcessingResult
        import time
        
        start_time = time.time()
        errors = []
        warnings = []
        transactions = []
        output_file = ""
        
        try:
            # Detect format and get parser
            parser = self.parser_factory.get_parser_for_file(file_path)
            if not parser:
                error_msg = f"No suitable parser found for file: {file_path}"
                errors.append(error_msg)
                self.error_handler.log_error(
                    error_msg,
                    "PARSER_NOT_FOUND",
                    file_path=file_path
                )
                return ProcessingResult(
                    file_path=file_path,
                    institution=self._extract_institution_from_path(file_path),
                    transactions_count=0,
                    output_file="",
                    processing_time=time.time() - start_time,
                    errors=errors,
                    warnings=warnings,
                    success=False
                )
            
            # Parse the file
            try:
                transactions = parser.parse(file_path)
                self.error_handler.log_info(f"Parsed {len(transactions)} transactions from {file_path}")
            except Exception as e:
                error_msg = f"Failed to parse file {file_path}: {str(e)}"
                errors.append(error_msg)
                self.error_handler.log_error(
                    error_msg,
                    "PARSING_ERROR",
                    file_path=file_path,
                    exception=e
                )
                return ProcessingResult(
                    file_path=file_path,
                    institution=self._extract_institution_from_path(file_path),
                    transactions_count=0,
                    output_file="",
                    processing_time=time.time() - start_time,
                    errors=errors,
                    warnings=warnings,
                    success=False
                )
            
            # Validate transactions
            validated_transactions = []
            for transaction in transactions:
                validation_errors = self.validation_engine.validate_transaction(transaction)
                if validation_errors:
                    warnings.extend(validation_errors)
                else:
                    validated_transactions.append(transaction)
            
            # Deduplicate transactions
            if validated_transactions:
                deduplicated_transactions = self.validation_engine.deduplicate_transactions(validated_transactions)
                duplicate_count = len(validated_transactions) - len(deduplicated_transactions)
                if duplicate_count > 0:
                    warnings.append(f"Removed {duplicate_count} duplicate transactions")
                    self.error_handler.log_info(f"Removed {duplicate_count} duplicates from {file_path}")
                transactions = deduplicated_transactions
            else:
                transactions = []
            
            # Write output CSV
            if transactions:
                try:
                    output_file = self.csv_writer.generate_output_path(
                        transactions, 
                        file_path
                    )
                    # Ensure output directory exists
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    
                    success = self.csv_writer.write_transactions(transactions, output_file)
                    if success:
                        self.error_handler.log_info(f"Wrote {len(transactions)} transactions to {output_file}")
                    else:
                        error_msg = f"Failed to write output file for {file_path}"
                        errors.append(error_msg)
                        self.error_handler.log_error(
                            error_msg,
                            "OUTPUT_WRITE_ERROR",
                            file_path=file_path
                        )
                    
                    # Validate output file
                    if success:
                        csv_validation_errors = self.validation_engine.validate_csv_output(output_file)
                        if csv_validation_errors:
                            warnings.extend(csv_validation_errors)
                        
                except Exception as e:
                    error_msg = f"Failed to write output file for {file_path}: {str(e)}"
                    errors.append(error_msg)
                    self.error_handler.log_error(
                        error_msg,
                        "OUTPUT_WRITE_ERROR",
                        file_path=file_path,
                        exception=e
                    )
            
            processing_time = time.time() - start_time
            success = len(errors) == 0 and len(transactions) > 0
            
            return ProcessingResult(
                file_path=file_path,
                institution=self._extract_institution_from_path(file_path),
                transactions_count=len(transactions),
                output_file=output_file,
                processing_time=processing_time,
                errors=errors,
                warnings=warnings,
                success=success
            )
            
        except Exception as e:
            error_msg = f"Unexpected error processing {file_path}: {str(e)}"
            errors.append(error_msg)
            self.error_handler.log_error(
                error_msg,
                "PROCESSING_ERROR",
                file_path=file_path,
                exception=e
            )
            
            return ProcessingResult(
                file_path=file_path,
                institution=self._extract_institution_from_path(file_path),
                transactions_count=0,
                output_file="",
                processing_time=time.time() - start_time,
                errors=errors,
                warnings=warnings,
                success=False
            )
    
    def _process_files_with_merging(self, file_paths: List[str]) -> Dict[str, 'ProcessingResult']:
        """
        Process multiple files with duplicate detection and merging
        
        Args:
            file_paths: List of file paths to process
            
        Returns:
            Dictionary mapping file paths to ProcessingResult objects
        """
        from .models.core import ProcessingResult
        import time
        
        # Parse all files first
        transactions_by_file = {}
        parse_results = {}
        
        total_files = len(file_paths)
        
        for i, file_path in enumerate(file_paths, 1):
            self._report_progress(i, total_files, file_path)
            
            start_time = time.time()
            errors = []
            warnings = []
            transactions = []
            
            try:
                # Detect format and get parser
                parser = self.parser_factory.get_parser_for_file(file_path)
                if not parser:
                    error_msg = f"No suitable parser found for file: {file_path}"
                    errors.append(error_msg)
                    self.error_handler.log_error(
                        error_msg,
                        "PARSER_NOT_FOUND",
                        file_path=file_path
                    )
                else:
                    # Parse the file
                    try:
                        transactions = parser.parse(file_path)
                        self.error_handler.log_info(f"Parsed {len(transactions)} transactions from {file_path}")
                        
                        # Validate transactions
                        validated_transactions = []
                        for transaction in transactions:
                            validation_errors = self.validation_engine.validate_transaction(transaction)
                            if validation_errors:
                                warnings.extend(validation_errors)
                            else:
                                validated_transactions.append(transaction)
                        
                        transactions = validated_transactions
                        
                    except Exception as e:
                        error_msg = f"Failed to parse file {file_path}: {str(e)}"
                        errors.append(error_msg)
                        self.error_handler.log_error(
                            error_msg,
                            "PARSING_ERROR",
                            file_path=file_path,
                            exception=e
                        )
                
                # Store results
                transactions_by_file[file_path] = transactions
                parse_results[file_path] = {
                    'errors': errors,
                    'warnings': warnings,
                    'parsing_time': time.time() - start_time,
                    'transaction_count': len(transactions)
                }
                
            except Exception as e:
                error_msg = f"Unexpected error processing {file_path}: {str(e)}"
                errors.append(error_msg)
                self.error_handler.log_error(
                    error_msg,
                    "PROCESSING_ERROR",
                    file_path=file_path,
                    exception=e
                )
                
                transactions_by_file[file_path] = []
                parse_results[file_path] = {
                    'errors': errors,
                    'warnings': warnings,
                    'parsing_time': time.time() - start_time,
                    'transaction_count': 0
                }
        
        # Now write with duplicate detection and merging
        write_results = self.csv_writer.write_multiple_files(transactions_by_file)
        
        # Combine parse and write results
        final_results = {}
        for file_path in file_paths:
            parse_result = parse_results[file_path]
            write_result = write_results.get(file_path)
            
            if write_result:
                # Merge results
                all_errors = parse_result['errors'] + write_result.errors
                all_warnings = parse_result['warnings'] + write_result.warnings
                total_time = parse_result['parsing_time'] + write_result.processing_time
                
                final_results[file_path] = ProcessingResult(
                    file_path=file_path,
                    institution=write_result.institution,
                    transactions_count=write_result.transactions_count,
                    output_file=write_result.output_file,
                    processing_time=total_time,
                    errors=all_errors,
                    warnings=all_warnings,
                    success=write_result.success and len(all_errors) == 0
                )
            else:
                # Only parse results available
                final_results[file_path] = ProcessingResult(
                    file_path=file_path,
                    institution=self._extract_institution_from_path(file_path),
                    transactions_count=parse_result['transaction_count'],
                    output_file="",
                    processing_time=parse_result['parsing_time'],
                    errors=parse_result['errors'],
                    warnings=parse_result['warnings'],
                    success=len(parse_result['errors']) == 0 and parse_result['transaction_count'] > 0
                )
        
        return final_results
    
    def _extract_institution_from_path(self, file_path: str) -> str:
        """Extract institution name from file path"""
        path_parts = Path(file_path).parts
        
        # Look for institution name in path (typically in raw/institution_name/)
        for i, part in enumerate(path_parts):
            if part == 'raw' and i + 1 < len(path_parts):
                return path_parts[i + 1].lower().replace('_', ' ').title()
        
        # Fallback to filename-based extraction
        filename = Path(file_path).stem.lower()
        
        # Common institution patterns
        if 'chase' in filename:
            return 'Chase'
        elif 'bofa' in filename or 'bankofamerica' in filename:
            return 'Bank of America'
        elif 'wells' in filename:
            return 'Wells Fargo'
        elif 'citi' in filename:
            return 'Citibank'
        elif 'amex' in filename:
            return 'American Express'
        elif 'firsttech' in filename:
            return 'First Tech'
        elif 'gemini' in filename:
            return 'Gemini'
        
        return 'Unknown'
    
    def _ensure_directory_structure(self):
        """Ensure required directory structure exists"""
        directories_to_create = [
            self.config.data_directory,
            os.path.join(self.config.data_directory, 'processed'),
            os.path.join(self.config.data_directory, 'reports'),
            self.processing_tracker.state_directory
        ]
        
        # Create institution-specific directories based on raw directory structure
        if os.path.exists(self.config.raw_directory):
            for item in os.listdir(self.config.raw_directory):
                item_path = os.path.join(self.config.raw_directory, item)
                if os.path.isdir(item_path):
                    # Create corresponding data directory for this institution
                    institution_data_dir = os.path.join(self.config.data_directory, item)
                    directories_to_create.append(institution_data_dir)
        
        for directory in directories_to_create:
            try:
                os.makedirs(directory, exist_ok=True)
                self.error_handler.log_debug(f"Ensured directory exists: {directory}")
            except Exception as e:
                self.error_handler.log_error(
                    f"Failed to create directory {directory}: {str(e)}",
                    "DIRECTORY_CREATION_ERROR",
                    file_path=directory,
                    exception=e
                )
                raise
    
    def _report_progress(self, current: int, total: int, current_file: str):
        """Report processing progress"""
        percentage = (current / total) * 100
        filename = os.path.basename(current_file)
        
        # Log progress for verbose mode
        self.error_handler.log_info(
            f"Processing file {current}/{total} ({percentage:.1f}%): {filename}",
            context={
                'current_file': current,
                'total_files': total,
                'percentage': percentage,
                'file_path': current_file
            }
        )
    
    def create_directory_structure(self, base_path: Optional[str] = None) -> Dict[str, Any]:
        """Create complete directory structure for the parser"""
        if base_path:
            # Update config to use custom base path
            self.config.raw_directory = os.path.join(base_path, 'raw')
            self.config.data_directory = os.path.join(base_path, 'data')
        
        directories_created = []
        directories_failed = []
        
        # Standard directory structure
        standard_dirs = [
            self.config.raw_directory,
            self.config.data_directory,
            os.path.join(self.config.data_directory, 'processed'),
            os.path.join(self.config.data_directory, 'reports'),
            os.path.join(self.config.raw_directory, 'chase'),
            os.path.join(self.config.raw_directory, 'firsttech'),
            os.path.join(self.config.raw_directory, 'gemini'),
            os.path.join(self.config.raw_directory, 'other'),
            self.processing_tracker.state_directory,
            'config',
            'plugins',
            'logs'
        ]
        
        for directory in standard_dirs:
            try:
                os.makedirs(directory, exist_ok=True)
                directories_created.append(directory)
                self.error_handler.log_info(f"Created directory: {directory}")
            except Exception as e:
                directories_failed.append({
                    'directory': directory,
                    'error': str(e)
                })
                self.error_handler.log_error(
                    f"Failed to create directory {directory}: {str(e)}",
                    "DIRECTORY_CREATION_ERROR",
                    file_path=directory,
                    exception=e
                )
        
        # Create README files for guidance
        readme_files = {
            os.path.join(self.config.raw_directory, 'README.md'): self._get_raw_directory_readme(),
            os.path.join(self.config.data_directory, 'README.md'): self._get_data_directory_readme(),
            os.path.join('config', 'README.md'): self._get_config_directory_readme(),
            os.path.join('plugins', 'README.md'): self._get_plugins_directory_readme()
        }
        
        for readme_path, content in readme_files.items():
            try:
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                directories_created.append(readme_path)
                self.error_handler.log_info(f"Created README: {readme_path}")
            except Exception as e:
                directories_failed.append({
                    'directory': readme_path,
                    'error': str(e)
                })
                self.error_handler.log_error(
                    f"Failed to create README {readme_path}: {str(e)}",
                    "FILE_CREATION_ERROR",
                    file_path=readme_path,
                    exception=e
                )
        
        return {
            'success': len(directories_failed) == 0,
            'directories_created': directories_created,
            'directories_failed': directories_failed,
            'total_created': len(directories_created),
            'total_failed': len(directories_failed)
        }
    
    def _get_raw_directory_readme(self) -> str:
        """Get README content for raw directory"""
        return """# Raw Data Directory

This directory contains the original financial data files downloaded from your institutions.

## Organization

Organize your files by institution in subdirectories:

- `chase/` - Chase Bank files (QFX, PDF statements)
- `firsttech/` - First Tech Credit Union files
- `gemini/` - Gemini cryptocurrency exchange files (CSV)
- `other/` - Files from other institutions

## Supported File Types

- **QFX/OFX files** - Quicken/Open Financial Exchange format
- **CSV files** - Comma-separated values from online banking
- **PDF files** - Bank statements (table extraction)

## File Naming

Use descriptive names that include:
- Institution name
- Account identifier (last 4 digits)
- Date range
- File type

Example: `chase_8147_20241001_20241031.qfx`

## Processing

Run `kiro-budget process` to convert all files in this directory to the unified CSV format in the `data/` directory.
"""
    
    def _get_data_directory_readme(self) -> str:
        """Get README content for data directory"""
        return """# Data Directory

This directory contains processed financial data in unified CSV format.

## Organization

- `processed/` - Final processed CSV files organized by institution
- `reports/` - Processing reports and summaries

## CSV Format

All output files use this standardized format:

| Column | Description |
|--------|-------------|
| date | Transaction date (YYYY-MM-DD) |
| amount | Transaction amount (decimal, negative for debits) |
| description | Transaction description |
| account | Account identifier |
| institution | Financial institution name |
| transaction_id | Unique transaction ID (when available) |
| category | Transaction category (optional) |
| balance | Account balance after transaction (when available) |

## File Naming

Output files follow this pattern:
`{institution}_{account}_{start_date}_{end_date}.csv`

Example: `chase_8147_2024-10-01_2024-10-31.csv`
"""
    
    def _get_config_directory_readme(self) -> str:
        """Get README content for config directory"""
        return """# Configuration Directory

This directory contains configuration files for the financial data parser.

## Files

- `parser_config.json` - Main parser configuration
- `parser_config.yml` - Alternative YAML format configuration
- Institution-specific configuration files

## Generate Template

Run `kiro-budget init-config` to generate a configuration template with examples.

## Configuration Options

- **raw_directory** - Path to raw data files
- **data_directory** - Path for processed output files
- **skip_processed** - Skip files that have been processed before
- **date_formats** - Supported date formats for parsing
- **institution_mappings** - Map directory names to institution names
- **column_mappings** - Map CSV column names to standard format
- **plugin_directories** - Directories to search for custom parsers

## Institution-Specific Rules

Configure custom parsing rules for each institution:

```json
{
  "institutions": {
    "chase": {
      "parser_type": "qfx",
      "date_format": "%m/%d/%Y",
      "column_mappings": {...}
    }
  }
}
```
"""
    
    def _get_plugins_directory_readme(self) -> str:
        """Get README content for plugins directory"""
        return """# Plugins Directory

This directory contains custom parser plugins for extending the financial data parser.

## Plugin Structure

Each plugin should be a Python file that defines:

1. A parser class inheriting from `FileParser`
2. A plugin class inheriting from `ParserPlugin`
3. Registration of the plugin

## Example Plugin

```python
from kiro_budget.parsers.base import FileParser
from kiro_budget.utils.plugin_manager import ParserPlugin

class CustomBankParser(FileParser):
    def parse(self, file_path: str):
        # Custom parsing logic
        pass
    
    def get_supported_extensions(self):
        return ['.custom']
    
    def validate_file(self, file_path: str):
        return True

class CustomBankPlugin(ParserPlugin):
    def get_name(self):
        return "custom_bank"
    
    def get_parser_class(self):
        return CustomBankParser
    
    def get_supported_institutions(self):
        return ["Custom Bank"]
```

## Loading Plugins

Plugins are automatically loaded from:
- This directory (`plugins/`)
- `~/.kiro_budget/plugins/`
- Directories specified in configuration

## Testing Plugins

Test your plugins with:
```bash
kiro-budget status  # Shows loaded plugins
kiro-budget process --files path/to/test/file
```
"""
    
    def generate_config_template(self, output_path: str) -> bool:
        """Generate configuration template file"""
        try:
            self.config_manager.save_config_template(output_path)
            return True
        except Exception as e:
            self.error_handler.log_error(
                f"Failed to generate config template: {str(e)}",
                "CONFIG_TEMPLATE_ERROR",
                file_path=output_path,
                exception=e
            )
            return False
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status and statistics"""
        return {
            'institution_stats': self.processing_tracker.get_institution_statistics(),
            'supported_formats': self.parser_factory.get_supported_formats(),
            'plugin_info': self.parser_factory.get_plugin_info(),
            'config_summary': {
                'raw_directory': self.config.raw_directory,
                'data_directory': self.config.data_directory,
                'skip_processed': self.config.skip_processed,
                'force_reprocess': self.config.force_reprocess
            }
        }


# CLI Commands using Click
@click.group()
@click.option('--config', '-c', help='Path to configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config, verbose):
    """Financial Data Parser - Convert financial data files to unified CSV format"""
    
    # Set up logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize CLI instance
    ctx.ensure_object(dict)
    ctx.obj['cli'] = FinancialDataParserCLI(config)


@cli.command()
@click.option('--files', '-f', multiple=True, help='Specific files to process')
@click.option('--directories', '-d', multiple=True, help='Directories to process')
@click.option('--force', is_flag=True, help='Force reprocessing of previously processed files')
@click.option('--no-recursive', is_flag=True, help='Disable recursive directory scanning')
@click.option('--report', '-r', help='Save processing report to specified file')
@click.pass_context
def process(ctx, files, directories, force, no_recursive, report):
    """Process financial data files"""
    
    cli_instance = ctx.obj['cli']
    
    # Convert tuples to lists
    file_list = list(files) if files else None
    dir_list = list(directories) if directories else None
    
    # Process files
    click.echo("Starting file processing...")
    
    try:
        result = cli_instance.process_files(
            file_paths=file_list,
            directories=dir_list,
            force_reprocess=force,
            recursive=not no_recursive
        )
        
        if result['success']:
            click.echo(f"✓ Processing completed successfully")
            click.echo(f"  Files processed: {result['files_processed']}")
            click.echo(f"  Files successful: {result['files_successful']}")
            click.echo(f"  Files failed: {result['files_failed']}")
            if result.get('files_skipped', 0) > 0:
                click.echo(f"  Files skipped: {result['files_skipped']}")
            
            # Show summary statistics
            summary = result['summary']
            click.echo(f"  Total transactions: {summary.total_transactions}")
            click.echo(f"  Processing time: {summary.total_duration:.2f}s")
            click.echo(f"  Success rate: {summary.success_rate:.1f}%")
            
            # Save report if requested
            if report:
                report_file = cli_instance.processing_tracker.save_batch_report(summary, report)
                click.echo(f"  Report saved: {report_file}")
        else:
            click.echo(f"✗ Processing failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"✗ Error during processing: {str(e)}")
        sys.exit(1)


@cli.command()
@click.argument('output_path', default='parser_config.json')
@click.option('--format', type=click.Choice(['json', 'yaml']), default='json', help='Configuration file format')
@click.pass_context
def init_config(ctx, output_path, format):
    """Generate configuration template file"""
    
    cli_instance = ctx.obj['cli']
    
    # Adjust extension based on format
    if format == 'yaml' and not output_path.endswith(('.yml', '.yaml')):
        output_path = output_path.replace('.json', '.yml')
    elif format == 'json' and not output_path.endswith('.json'):
        output_path = output_path.replace('.yml', '.json').replace('.yaml', '.json')
    
    try:
        success = cli_instance.generate_config_template(output_path)
        if success:
            click.echo(f"✓ Configuration template generated: {output_path}")
            click.echo("  Edit the file to customize parsing rules for your institutions")
        else:
            click.echo("✗ Failed to generate configuration template")
            sys.exit(1)
    except Exception as e:
        click.echo(f"✗ Error generating config template: {str(e)}")
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """Show processing status and statistics"""
    
    cli_instance = ctx.obj['cli']
    
    try:
        status_info = cli_instance.get_processing_status()
        
        click.echo("Financial Data Parser Status")
        click.echo("=" * 40)
        
        # Configuration summary
        config = status_info['config_summary']
        click.echo(f"Raw directory: {config['raw_directory']}")
        click.echo(f"Data directory: {config['data_directory']}")
        click.echo(f"Skip processed: {config['skip_processed']}")
        click.echo()
        
        # Supported formats
        formats = status_info['supported_formats']
        click.echo(f"Supported formats: {', '.join(formats)}")
        click.echo()
        
        # Institution statistics
        inst_stats = status_info['institution_stats']
        if inst_stats:
            click.echo("Institution Statistics:")
            for institution, stats in inst_stats.items():
                click.echo(f"  {institution}:")
                click.echo(f"    Files processed: {stats['total_files']}")
                click.echo(f"    Successful: {stats['successful_files']}")
                click.echo(f"    Failed: {stats['failed_files']}")
                click.echo(f"    Total transactions: {stats['total_transactions']}")
                if stats['last_processed']:
                    click.echo(f"    Last processed: {stats['last_processed']}")
        else:
            click.echo("No processing history found")
        
        # Plugin information
        plugin_info = status_info['plugin_info']
        if plugin_info['available_plugins']:
            click.echo()
            click.echo("Loaded Plugins:")
            for plugin in plugin_info['available_plugins']:
                click.echo(f"  - {plugin}")
        
    except Exception as e:
        click.echo(f"✗ Error getting status: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--institution', help='Filter by institution')
@click.option('--days', default=30, help='Number of days to look back')
@click.pass_context
def history(ctx, institution, days):
    """Show processing history"""
    
    cli_instance = ctx.obj['cli']
    
    try:
        history_data = cli_instance.processing_tracker.get_processing_history(
            institution=institution,
            days_back=days
        )
        
        if not history_data:
            click.echo("No processing history found")
            return
        
        click.echo(f"Processing History (last {days} days)")
        if institution:
            click.echo(f"Filtered by institution: {institution}")
        click.echo("=" * 60)
        
        for entry in history_data:
            status = "✓" if entry.success else "✗"
            click.echo(f"{status} {entry.file_path}")
            click.echo(f"    Processed: {entry.last_processed}")
            click.echo(f"    Transactions: {entry.transaction_count}")
            click.echo(f"    Processing time: {entry.processing_time:.2f}s")
            if entry.output_file:
                click.echo(f"    Output: {entry.output_file}")
            click.echo()
            
    except Exception as e:
        click.echo(f"✗ Error getting history: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--days', default=90, help='Keep state for this many days')
@click.pass_context
def cleanup(ctx, days):
    """Clean up old processing state"""
    
    cli_instance = ctx.obj['cli']
    
    try:
        cli_instance.processing_tracker.cleanup_old_state(days_to_keep=days)
        click.echo(f"✓ Cleaned up processing state older than {days} days")
    except Exception as e:
        click.echo(f"✗ Error during cleanup: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--path', help='Base path for directory structure (default: current directory)')
@click.option('--dry-run', is_flag=True, help='Show what would be created without actually creating')
@click.pass_context
def setup(ctx, path, dry_run):
    """Set up complete directory structure for the parser"""
    
    cli_instance = ctx.obj['cli']
    
    if dry_run:
        click.echo("Directory structure that would be created:")
        click.echo("=" * 50)
        
        base = path or os.getcwd()
        directories = [
            os.path.join(base, 'raw'),
            os.path.join(base, 'raw', 'chase'),
            os.path.join(base, 'raw', 'firsttech'),
            os.path.join(base, 'raw', 'gemini'),
            os.path.join(base, 'raw', 'other'),
            os.path.join(base, 'data'),
            os.path.join(base, 'data', 'processed'),
            os.path.join(base, 'data', 'reports'),
            os.path.join(base, 'config'),
            os.path.join(base, 'plugins'),
            os.path.join(base, 'logs'),
            os.path.join(base, '.kiro_parser_state')
        ]
        
        for directory in directories:
            click.echo(f"  📁 {directory}")
        
        readme_files = [
            os.path.join(base, 'raw', 'README.md'),
            os.path.join(base, 'data', 'README.md'),
            os.path.join(base, 'config', 'README.md'),
            os.path.join(base, 'plugins', 'README.md')
        ]
        
        click.echo("\nREADME files that would be created:")
        for readme in readme_files:
            click.echo(f"  📄 {readme}")
        
        return
    
    try:
        result = cli_instance.create_directory_structure(path)
        
        if result['success']:
            click.echo("✓ Directory structure created successfully")
            click.echo(f"  Directories created: {result['total_created']}")
            
            if result['directories_created']:
                click.echo("\nCreated:")
                for directory in result['directories_created']:
                    click.echo(f"  📁 {directory}")
        else:
            click.echo("⚠ Directory structure created with some errors")
            click.echo(f"  Directories created: {result['total_created']}")
            click.echo(f"  Directories failed: {result['total_failed']}")
            
            if result['directories_failed']:
                click.echo("\nFailed:")
                for failed in result['directories_failed']:
                    click.echo(f"  ✗ {failed['directory']}: {failed['error']}")
            
            if result['total_failed'] > 0:
                sys.exit(1)
                
    except Exception as e:
        click.echo(f"✗ Error setting up directory structure: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option('--show-progress', is_flag=True, help='Show detailed progress during processing')
@click.option('--batch-size', default=10, help='Number of files to process in each batch')
@click.pass_context
def batch_process(ctx, show_progress, batch_size):
    """Process all files in raw directory with batch processing and progress reporting"""
    
    cli_instance = ctx.obj['cli']
    
    try:
        # Ensure directory structure exists
        cli_instance._ensure_directory_structure()
        
        # Get all files to process
        raw_dir = cli_instance.config.raw_directory
        if not os.path.exists(raw_dir):
            click.echo(f"✗ Raw directory not found: {raw_dir}")
            click.echo("Run 'kiro-budget setup' to create the directory structure")
            sys.exit(1)
        
        all_files = cli_instance.file_scanner.scan_directory(raw_dir, recursive=True)
        
        if not all_files:
            click.echo("No files found to process")
            return
        
        # Filter files that need processing
        files_to_process = [
            f for f in all_files 
            if cli_instance.processing_tracker.should_process_file(f, False)
        ]
        
        total_files = len(all_files)
        new_files = len(files_to_process)
        skipped_files = total_files - new_files
        
        click.echo(f"Found {total_files} files, {new_files} need processing, {skipped_files} already processed")
        
        if new_files == 0:
            click.echo("All files are up to date")
            return
        
        # Process in batches
        processed_count = 0
        successful_count = 0
        failed_count = 0
        
        cli_instance.processing_tracker.start_batch_processing()
        
        for i in range(0, len(files_to_process), batch_size):
            batch = files_to_process[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(files_to_process) + batch_size - 1) // batch_size
            
            if show_progress:
                click.echo(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} files)")
            
            for j, file_path in enumerate(batch, 1):
                if show_progress:
                    filename = os.path.basename(file_path)
                    click.echo(f"  [{j}/{len(batch)}] {filename}...", nl=False)
                
                try:
                    result = cli_instance._process_single_file(file_path)
                    cli_instance.processing_tracker.record_processing_result(result)
                    
                    processed_count += 1
                    if result.success:
                        successful_count += 1
                        if show_progress:
                            click.echo(f" ✓ ({result.transactions_count} transactions)")
                    else:
                        failed_count += 1
                        if show_progress:
                            click.echo(f" ✗ ({len(result.errors)} errors)")
                        
                except Exception as e:
                    failed_count += 1
                    if show_progress:
                        click.echo(f" ✗ (exception: {str(e)})")
                    
                    cli_instance.error_handler.log_error(
                        f"Unexpected error processing {file_path}: {str(e)}",
                        "PROCESSING_ERROR",
                        file_path=file_path,
                        exception=e
                    )
        
        # Generate final summary
        summary = cli_instance.processing_tracker.generate_batch_summary()
        summary.skipped_files = skipped_files
        
        click.echo(f"\n✓ Batch processing completed")
        click.echo(f"  Files processed: {processed_count}")
        click.echo(f"  Files successful: {successful_count}")
        click.echo(f"  Files failed: {failed_count}")
        click.echo(f"  Files skipped: {skipped_files}")
        click.echo(f"  Total transactions: {summary.total_transactions}")
        click.echo(f"  Processing time: {summary.total_duration:.2f}s")
        click.echo(f"  Success rate: {summary.success_rate:.1f}%")
        
        # Save batch report
        report_file = cli_instance.processing_tracker.save_batch_report(summary)
        click.echo(f"  Report saved: {report_file}")
        
        if failed_count > 0:
            click.echo(f"\n⚠ {failed_count} files failed processing. Check logs for details.")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"✗ Error during batch processing: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    cli()