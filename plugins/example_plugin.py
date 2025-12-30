"""Example plugin demonstrating the plugin architecture."""

from typing import List, Type
from kiro_budget.utils.plugin_manager import ParserPlugin
from kiro_budget.parsers.base import FileParser
from kiro_budget.parsers.csv_parser import CSVParser


class ExampleChasePlugin(ParserPlugin):
    """Example plugin for Chase-specific CSV parsing"""
    
    def get_name(self) -> str:
        return "chase_csv_enhanced"
    
    def get_parser_class(self) -> Type[FileParser]:
        # For this example, we'll use the existing CSVParser
        # In a real plugin, you'd create a custom parser class
        return CSVParser
    
    def get_supported_institutions(self) -> List[str]:
        return ["chase", "chase_bank", "jpmorgan_chase"]
    
    def get_supported_extensions(self) -> List[str]:
        return [".csv"]
    
    def get_priority(self) -> int:
        # Higher priority than built-in parsers
        return 10
    
    def can_handle_file(self, file_path: str, institution: str = None) -> bool:
        """Enhanced file handling logic for Chase files"""
        # Call parent implementation first
        if not super().can_handle_file(file_path, institution):
            return False
        
        # Additional logic: check if filename contains chase-specific patterns
        filename = file_path.lower()
        chase_patterns = ['chase', 'jpmorgan', 'activity']
        
        return any(pattern in filename for pattern in chase_patterns)


# Plugin classes are automatically discovered by the plugin manager
# No need for explicit registration