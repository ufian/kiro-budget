"""File scanning and format detection utilities."""

import os
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from ..models.core import ParserConfig


class FileScanner:
    """Recursively scans directories for supported financial data files"""
    
    def __init__(self, config: ParserConfig):
        self.config = config
        self.supported_extensions = {'.qfx', '.ofx', '.csv', '.pdf'}
    
    def scan_directory(self, directory: str, recursive: bool = True) -> List[str]:
        """
        Scan directory for supported file types
        
        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories recursively
            
        Returns:
            List of file paths that match supported extensions
        """
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not os.path.isdir(directory):
            raise ValueError(f"Path is not a directory: {directory}")
        
        found_files = []
        
        if recursive:
            # Use os.walk for recursive scanning
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self._is_supported_file(file_path):
                        found_files.append(file_path)
        else:
            # Scan only the immediate directory
            try:
                for item in os.listdir(directory):
                    item_path = os.path.join(directory, item)
                    if os.path.isfile(item_path) and self._is_supported_file(item_path):
                        found_files.append(item_path)
            except PermissionError:
                # Log permission error but continue
                pass
        
        return sorted(found_files)  # Sort for consistent ordering
    
    def scan_multiple_directories(self, directories: List[str], recursive: bool = True) -> Dict[str, List[str]]:
        """
        Scan multiple directories and return results organized by directory
        
        Args:
            directories: List of directory paths to scan
            recursive: Whether to scan subdirectories recursively
            
        Returns:
            Dictionary mapping directory paths to lists of found files
        """
        results = {}
        
        for directory in directories:
            try:
                results[directory] = self.scan_directory(directory, recursive)
            except (FileNotFoundError, ValueError) as e:
                # Store error information
                results[directory] = []
        
        return results
    
    def get_files_by_extension(self, directory: str, extension: str, recursive: bool = True) -> List[str]:
        """
        Get all files with a specific extension from directory
        
        Args:
            directory: Directory path to scan
            extension: File extension to filter by (e.g., '.csv')
            recursive: Whether to scan subdirectories recursively
            
        Returns:
            List of file paths with the specified extension
        """
        if not extension.startswith('.'):
            extension = '.' + extension
        
        all_files = self.scan_directory(directory, recursive)
        return [f for f in all_files if f.lower().endswith(extension.lower())]
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Check if file has a supported extension and is accessible"""
        try:
            # Check extension
            _, ext = os.path.splitext(file_path.lower())
            if ext not in self.supported_extensions:
                return False
            
            # Check if file is accessible and not empty
            if not os.path.isfile(file_path):
                return False
            
            # Check file size (skip empty files)
            if os.path.getsize(file_path) == 0:
                return False
            
            return True
        except (OSError, PermissionError):
            return False


class FormatDetector:
    """Detects file format based on extension and content analysis"""
    
    def __init__(self, config: ParserConfig):
        self.config = config
        # Map extensions to format types
        self.extension_map = {
            '.qfx': 'qfx',
            '.ofx': 'qfx',  # OFX and QFX use same parser
            '.csv': 'csv',
            '.pdf': 'pdf'
        }
    
    def detect_format(self, file_path: str) -> Optional[str]:
        """
        Detect file format based on extension and content
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            Format type string ('qfx', 'csv', 'pdf') or None if unsupported
        """
        if not os.path.exists(file_path):
            return None
        
        # Primary detection: file extension
        _, ext = os.path.splitext(file_path.lower())
        format_type = self.extension_map.get(ext)
        
        if format_type:
            # Verify format with content analysis
            if self._verify_format_by_content(file_path, format_type):
                return format_type
        
        # Fallback: content-based detection
        return self._detect_by_content(file_path)
    
    def detect_multiple_files(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """
        Detect formats for multiple files
        
        Args:
            file_paths: List of file paths to analyze
            
        Returns:
            Dictionary mapping file paths to detected formats
        """
        results = {}
        for file_path in file_paths:
            results[file_path] = self.detect_format(file_path)
        return results
    
    def get_files_by_format(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """
        Group files by detected format
        
        Args:
            file_paths: List of file paths to analyze
            
        Returns:
            Dictionary mapping format types to lists of file paths
        """
        format_groups = {}
        
        for file_path in file_paths:
            format_type = self.detect_format(file_path)
            if format_type:
                if format_type not in format_groups:
                    format_groups[format_type] = []
                format_groups[format_type].append(file_path)
        
        return format_groups
    
    def _verify_format_by_content(self, file_path: str, expected_format: str) -> bool:
        """Verify file format by examining content"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read first few lines for analysis
                first_lines = []
                for _ in range(10):  # Read up to 10 lines
                    line = f.readline()
                    if not line:
                        break
                    first_lines.append(line.strip())
                
                content_start = '\n'.join(first_lines).lower()
                
                if expected_format == 'qfx':
                    return self._is_qfx_content(content_start)
                elif expected_format == 'csv':
                    return self._is_csv_content(first_lines)
                elif expected_format == 'pdf':
                    return self._is_pdf_content(file_path)
                
        except (UnicodeDecodeError, PermissionError, OSError):
            pass
        
        return False
    
    def _detect_by_content(self, file_path: str) -> Optional[str]:
        """Detect format by content analysis when extension is unclear"""
        try:
            # Try to detect PDF by binary signature
            if self._is_pdf_content(file_path):
                return 'pdf'
            
            # Try text-based detection
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = []
                for _ in range(10):
                    line = f.readline()
                    if not line:
                        break
                    first_lines.append(line.strip())
                
                content_start = '\n'.join(first_lines).lower()
                
                if self._is_qfx_content(content_start):
                    return 'qfx'
                elif self._is_csv_content(first_lines):
                    return 'csv'
                
        except (UnicodeDecodeError, PermissionError, OSError):
            pass
        
        return None
    
    def _is_qfx_content(self, content: str) -> bool:
        """Check if content appears to be QFX/OFX format"""
        qfx_indicators = [
            'ofxheader',
            '<ofx>',
            '<bankmsgsrsv1>',
            '<stmtrs>',
            '<stmttrnrs>',
            'data:ofx',
            'version:',
            'encoding:'
        ]
        
        return any(indicator in content for indicator in qfx_indicators)
    
    def _is_csv_content(self, lines: List[str]) -> bool:
        """Check if content appears to be CSV format"""
        if not lines:
            return False
        
        # Check first line for CSV-like structure
        first_line = lines[0]
        
        # Look for common CSV indicators
        csv_indicators = [
            ',' in first_line,  # Contains commas
            len(first_line.split(',')) >= 3,  # At least 3 columns
        ]
        
        # Check for common financial CSV headers
        header_keywords = [
            'date', 'amount', 'description', 'transaction', 'balance',
            'debit', 'credit', 'account', 'memo', 'category', 'type'
        ]
        
        first_line_lower = first_line.lower()
        has_financial_headers = any(keyword in first_line_lower for keyword in header_keywords)
        
        return any(csv_indicators) and (has_financial_headers or len(lines) > 1)
    
    def _is_pdf_content(self, file_path: str) -> bool:
        """Check if file is a PDF by examining binary signature"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
                return header.startswith(b'%PDF-')
        except (PermissionError, OSError):
            return False


class ParserFactory:
    """Factory for creating appropriate parser instances based on file format"""
    
    def __init__(self, config: ParserConfig):
        self.config = config
        self.format_detector = FormatDetector(config)
        self._parser_classes = {}
        
        # Initialize plugin manager
        from .plugin_manager import PluginManager
        self.plugin_manager = PluginManager(config)
        
        # Register default parsers (plugins will override if available)
        self._register_default_parsers()
    
    def _register_default_parsers(self):
        """Register default parser classes"""
        # Import parsers dynamically to avoid circular imports
        try:
            from ..parsers.qfx_parser import QFXParser
            self._parser_classes['qfx'] = QFXParser
        except ImportError:
            pass
        
        try:
            from ..parsers.csv_parser import CSVParser
            self._parser_classes['csv'] = CSVParser
        except ImportError:
            pass
        
        try:
            from ..parsers.pdf_parser import PDFParser
            self._parser_classes['pdf'] = PDFParser
        except ImportError:
            pass
    
    def register_parser(self, format_type: str, parser_class):
        """Register a parser class for a specific format"""
        self._parser_classes[format_type] = parser_class
    
    def get_parser_for_file(self, file_path: str, institution: str = None):
        """
        Get appropriate parser instance for a file
        
        Args:
            file_path: Path to the file to parse
            institution: Institution name (if known) for plugin selection
            
        Returns:
            Parser instance or None if no suitable parser found
        """
        # First try plugin manager (supports institution-specific parsers)
        parser = self.plugin_manager.get_parser_for_file(file_path, institution)
        if parser:
            return parser
        
        # Fall back to format detection and default parsers
        format_type = self.format_detector.detect_format(file_path)
        
        if format_type and format_type in self._parser_classes:
            parser_class = self._parser_classes[format_type]
            return parser_class(self.config)
        
        return None
    
    def get_parser_by_format(self, format_type: str):
        """
        Get parser instance by format type
        
        Args:
            format_type: Format type string ('qfx', 'csv', 'pdf')
            
        Returns:
            Parser instance or None if format not supported
        """
        # First try plugin manager
        parser = self.plugin_manager.get_parser_by_type(format_type)
        if parser:
            return parser
        
        # Fall back to default parsers
        if format_type in self._parser_classes:
            parser_class = self._parser_classes[format_type]
            return parser_class(self.config)
        
        return None
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported format types"""
        # Combine plugin manager formats with default formats
        plugin_formats = set(self.plugin_manager.get_available_parsers())
        default_formats = set(self._parser_classes.keys())
        return list(plugin_formats.union(default_formats))
    
    def can_parse_file(self, file_path: str, institution: str = None) -> bool:
        """Check if file can be parsed by available parsers"""
        # Check if plugin manager can handle it
        parser = self.plugin_manager.get_parser_for_file(file_path, institution)
        if parser:
            return True
        
        # Check default format detection
        format_type = self.format_detector.detect_format(file_path)
        return format_type is not None and format_type in self._parser_classes
    
    def get_plugin_info(self) -> Dict[str, Any]:
        """Get information about loaded plugins"""
        return {
            'available_plugins': self.plugin_manager.get_available_plugins(),
            'available_parsers': self.plugin_manager.get_available_parsers(),
            'plugin_details': {
                name: self.plugin_manager.get_plugin_info(name)
                for name in self.plugin_manager.get_available_plugins()
            }
        }
    
    def reload_plugins(self) -> None:
        """Reload all plugins"""
        self.plugin_manager.reload_plugins()