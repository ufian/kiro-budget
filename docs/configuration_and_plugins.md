# Configuration and Plugin System

The Financial Data Parser includes a comprehensive configuration and plugin system that allows for flexible customization and extensibility.

## Configuration Management

### Overview

The configuration system allows you to customize parser behavior through JSON or YAML configuration files. Configuration includes:

- Directory paths for input and output
- Institution-specific parsing rules
- Date and amount formats
- Column mappings for CSV files
- Plugin directories
- Output filename patterns

### Configuration File Locations

The system searches for configuration files in the following order:

1. Explicitly specified path
2. `parser_config.json` or `parser_config.yml` in current directory
3. `config/parser_config.json` or `config/parser_config.yml`
4. `~/.kiro_budget/config.json` or `~/.kiro_budget/config.yml`
5. `/etc/kiro_budget/config.json` or `/etc/kiro_budget/config.yml`

### Configuration Structure

```json
{
  "raw_directory": "raw",
  "data_directory": "data",
  "skip_processed": true,
  "force_reprocess": false,
  "date_formats": [
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%d/%m/%Y"
  ],
  "institution_mappings": {
    "chase": "Chase Bank",
    "bofa": "Bank of America"
  },
  "column_mappings": {
    "chase": {
      "date": ["Date", "Transaction Date"],
      "amount": ["Amount", "Debit", "Credit"],
      "description": ["Description", "Memo"]
    }
  },
  "plugin_directories": [
    "plugins",
    "~/.kiro_budget/plugins"
  ],
  "institutions": {
    "chase": {
      "parser_type": "qfx",
      "column_mappings": {
        "date": "Date",
        "amount": "Amount",
        "description": "Description",
        "account": "Account"
      },
      "date_format": "%m/%d/%Y",
      "amount_format": "decimal",
      "account_extraction_pattern": "statements-(\\d{4})-",
      "custom_rules": {
        "skip_pending": true,
        "merge_transfers": false
      }
    }
  }
}
```

### Configuration Fields

#### Global Settings

- **raw_directory**: Directory containing input files (default: "raw")
- **data_directory**: Directory for output files (default: "data")
- **skip_processed**: Skip files that have already been processed (default: true)
- **force_reprocess**: Force reprocessing of all files (default: false)
- **date_formats**: List of date formats to try when parsing dates
- **institution_mappings**: Map directory names to institution display names
- **column_mappings**: Global column mapping rules for CSV files
- **plugin_directories**: Directories to search for plugins

**Note**: Output filenames now preserve the original filename from the raw folder, changing only the extension to `.csv`.

#### Institution-Specific Settings

Each institution can have its own configuration under the `institutions` key:

- **parser_type**: Type of parser to use ("qfx", "csv", "pdf")
- **column_mappings**: Institution-specific column mappings
- **date_format**: Preferred date format for this institution
- **amount_format**: Amount format specification
- **account_extraction_pattern**: Regex pattern to extract account numbers
- **custom_rules**: Institution-specific custom rules

### Using Configuration

```python
from kiro_budget.utils.config_manager import ConfigManager

# Load configuration
config_manager = ConfigManager(config_path="my_config.json")
config = config_manager.load_config()

# Get institution-specific configuration
chase_config = config_manager.get_institution_config("chase")

# Generate configuration template
config_manager.save_config_template("config_template.json")
```

## Plugin System

### Overview

The plugin system allows you to extend the parser with custom parsers for specific institutions or file formats. Plugins can:

- Override built-in parsers
- Add support for new file formats
- Provide institution-specific parsing logic
- Implement custom data transformation rules

### Creating Plugins

#### Simple Plugin

```python
from kiro_budget.utils.plugin_manager import SimpleParserPlugin
from kiro_budget.parsers.csv_parser import CSVParser

# Create a simple plugin
plugin = SimpleParserPlugin(
    name="my_bank_csv",
    parser_class=CSVParser,
    institutions=["my_bank", "my_credit_union"],
    extensions=[".csv"],
    priority=10
)
```

#### Custom Plugin Class

```python
from typing import List, Type
from kiro_budget.utils.plugin_manager import ParserPlugin
from kiro_budget.parsers.base import FileParser

class MyCustomPlugin(ParserPlugin):
    def get_name(self) -> str:
        return "my_custom_parser"
    
    def get_parser_class(self) -> Type[FileParser]:
        return MyCustomParser
    
    def get_supported_institutions(self) -> List[str]:
        return ["my_bank"]
    
    def get_supported_extensions(self) -> List[str]:
        return [".custom"]
    
    def get_priority(self) -> int:
        return 5
    
    def can_handle_file(self, file_path: str, institution: str = None) -> bool:
        # Custom logic to determine if this plugin can handle the file
        return super().can_handle_file(file_path, institution)
```

### Plugin Discovery

Plugins are automatically discovered in configured plugin directories. The system:

1. Scans all Python files in plugin directories
2. Looks for classes that inherit from `ParserPlugin`
3. Automatically instantiates and registers found plugins
4. Handles plugin priority and conflicts

### Plugin Priority

Plugins with higher priority values take precedence:

- Built-in parsers: -10 (lowest priority)
- Default plugins: 0
- Custom plugins: 1-100 (higher values preferred)

### Using Plugins

```python
from kiro_budget.utils.plugin_manager import PluginManager
from kiro_budget.models.core import ParserConfig

# Initialize plugin manager
config = ParserConfig(plugin_directories=["plugins"])
plugin_manager = PluginManager(config)

# Get parser for a file
parser = plugin_manager.get_parser_for_file("my_file.csv", "my_bank")

# Get plugin information
plugin_info = plugin_manager.get_plugin_info("my_plugin")
```

## Integration with ParserFactory

The `ParserFactory` automatically integrates both configuration and plugin systems:

```python
from kiro_budget.utils.file_scanner import ParserFactory
from kiro_budget.utils.config_manager import ConfigManager

# Load configuration
config_manager = ConfigManager()
config = config_manager.load_config()

# Create parser factory (automatically loads plugins)
factory = ParserFactory(config)

# Get parser for file (uses both config and plugins)
parser = factory.get_parser_for_file("chase_account.qfx", "chase")

# Get plugin information
plugin_info = factory.get_plugin_info()
```

## Examples

### Example Plugin Directory Structure

```
plugins/
├── my_bank_plugin.py
├── credit_union_plugin.py
└── custom_formats/
    ├── __init__.py
    └── proprietary_format.py
```

### Example Plugin File

```python
# plugins/my_bank_plugin.py
from kiro_budget.utils.plugin_manager import ParserPlugin
from kiro_budget.parsers.csv_parser import CSVParser

class MyBankPlugin(ParserPlugin):
    def get_name(self):
        return "my_bank_enhanced"
    
    def get_parser_class(self):
        return CSVParser  # Or your custom parser class
    
    def get_supported_institutions(self):
        return ["my_bank", "my_bank_credit"]
    
    def get_supported_extensions(self):
        return [".csv", ".txt"]
    
    def get_priority(self):
        return 15
    
    def can_handle_file(self, file_path, institution=None):
        # Custom logic for file detection
        if not super().can_handle_file(file_path, institution):
            return False
        
        # Additional checks (e.g., file content patterns)
        return "MY_BANK" in file_path.upper()
```

### Running the Demo

To see the configuration and plugin systems in action:

```bash
cd kiro-budget
python examples/config_plugin_demo.py
```

This will demonstrate:
- Configuration loading and validation
- Plugin registration and discovery
- Parser selection based on file type and institution
- Integration between all components

## Best Practices

### Configuration

1. **Use institution-specific configurations** for banks with unique formats
2. **Test configuration changes** with sample files before production use
3. **Keep backups** of working configurations
4. **Use descriptive institution names** in mappings
5. **Document custom rules** in configuration comments

### Plugins

1. **Use meaningful plugin names** that indicate their purpose
2. **Set appropriate priorities** to avoid conflicts
3. **Implement robust file detection** in `can_handle_file()`
4. **Test plugins thoroughly** with various file formats
5. **Document plugin behavior** and supported institutions
6. **Handle errors gracefully** in custom parser implementations

### Development

1. **Use the configuration template** as a starting point
2. **Test with the demo script** to verify integration
3. **Run the test suite** after making changes
4. **Follow the existing code patterns** for consistency
5. **Add tests for custom plugins** and configurations