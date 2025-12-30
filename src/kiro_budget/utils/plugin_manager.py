"""Plugin architecture for extensible parser loading."""

import importlib
import importlib.util
import inspect
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
import logging

from ..models.core import ParserConfig
from ..parsers.base import FileParser


logger = logging.getLogger(__name__)


class ParserPlugin(ABC):
    """Base class for parser plugins"""
    
    @abstractmethod
    def get_name(self) -> str:
        """Return plugin name"""
        pass
    
    @abstractmethod
    def get_parser_class(self) -> Type[FileParser]:
        """Return the parser class this plugin provides"""
        pass
    
    @abstractmethod
    def get_supported_institutions(self) -> List[str]:
        """Return list of institutions this plugin supports"""
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Return list of file extensions this plugin supports"""
        pass
    
    def get_priority(self) -> int:
        """Return plugin priority (higher numbers = higher priority)
        
        Returns:
            Priority value (default: 0)
        """
        return 0
    
    def can_handle_file(self, file_path: str, institution: str = None) -> bool:
        """Check if this plugin can handle a specific file
        
        Args:
            file_path: Path to the file
            institution: Institution name (if known)
            
        Returns:
            True if plugin can handle the file
        """
        # Default implementation checks extension and institution
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in self.get_supported_extensions():
            return False
            
        if institution:
            supported_institutions = [inst.lower() for inst in self.get_supported_institutions()]
            if institution.lower() not in supported_institutions:
                return False
                
        return True


class PluginManager:
    """Manages loading and registration of parser plugins"""
    
    def __init__(self, config: ParserConfig):
        """Initialize plugin manager
        
        Args:
            config: Parser configuration containing plugin directories
        """
        self.config = config
        self.registered_parsers: Dict[str, Type[FileParser]] = {}
        self.registered_plugins: Dict[str, ParserPlugin] = {}
        self._plugin_priorities: Dict[str, int] = {}
        
        # Register built-in parsers first
        self._register_builtin_parsers()
        
        # Load plugins from configured directories
        self.load_plugins()
    
    def _register_builtin_parsers(self) -> None:
        """Register built-in parser classes"""
        try:
            # Import built-in parsers
            from ..parsers.qfx_parser import QFXParser
            from ..parsers.csv_parser import CSVParser
            from ..parsers.pdf_parser import PDFParser
            
            # Register with low priority so plugins can override
            self.register_parser('qfx', QFXParser, priority=-10)
            self.register_parser('csv', CSVParser, priority=-10)
            self.register_parser('pdf', PDFParser, priority=-10)
            
            logger.debug("Built-in parsers registered")
            
        except ImportError as e:
            logger.warning(f"Could not import built-in parsers: {e}")
    
    def load_plugins(self) -> None:
        """Load plugins from configured directories"""
        if not self.config.plugin_directories:
            logger.debug("No plugin directories configured")
            return
            
        for plugin_dir in self.config.plugin_directories:
            self._load_plugins_from_directory(plugin_dir)
    
    def _load_plugins_from_directory(self, plugin_dir: str) -> None:
        """Load plugins from a specific directory
        
        Args:
            plugin_dir: Directory path to scan for plugins
        """
        # Expand user path
        plugin_dir = os.path.expanduser(plugin_dir)
        
        if not os.path.exists(plugin_dir):
            logger.debug(f"Plugin directory does not exist: {plugin_dir}")
            return
            
        if not os.path.isdir(plugin_dir):
            logger.warning(f"Plugin path is not a directory: {plugin_dir}")
            return
        
        logger.info(f"Loading plugins from: {plugin_dir}")
        
        # Add plugin directory to Python path temporarily
        original_path = sys.path.copy()
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)
        
        try:
            # Scan for Python files
            for file_path in Path(plugin_dir).rglob("*.py"):
                if file_path.name.startswith('_'):
                    continue  # Skip private modules
                    
                self._load_plugin_from_file(file_path)
                
        finally:
            # Restore original Python path
            sys.path = original_path
    
    def _load_plugin_from_file(self, file_path: Path) -> None:
        """Load plugin from a Python file
        
        Args:
            file_path: Path to the Python file
        """
        try:
            # Create module name from file path
            module_name = f"plugin_{file_path.stem}_{id(file_path)}"
            
            # Load module from file
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not create module spec for {file_path}")
                return
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin classes in the module
            self._discover_plugins_in_module(module, str(file_path))
            
        except Exception as e:
            logger.error(f"Error loading plugin from {file_path}: {e}")
    
    def _discover_plugins_in_module(self, module: Any, file_path: str) -> None:
        """Discover plugin classes in a loaded module
        
        Args:
            module: Loaded Python module
            file_path: Path to the module file (for logging)
        """
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, ParserPlugin) and 
                obj is not ParserPlugin):
                
                try:
                    # Instantiate plugin
                    plugin_instance = obj()
                    self.register_plugin(plugin_instance)
                    logger.info(f"Loaded plugin '{plugin_instance.get_name()}' from {file_path}")
                    
                except Exception as e:
                    logger.error(f"Error instantiating plugin {name} from {file_path}: {e}")
    
    def register_parser(self, name: str, parser_class: Type[FileParser], priority: int = 0) -> None:
        """Register a parser class
        
        Args:
            name: Parser name/identifier
            parser_class: Parser class to register
            priority: Priority level (higher = more preferred)
        """
        if not issubclass(parser_class, FileParser):
            raise ValueError(f"Parser class must inherit from FileParser: {parser_class}")
            
        self.registered_parsers[name] = parser_class
        self._plugin_priorities[name] = priority
        logger.debug(f"Registered parser: {name} (priority: {priority})")
    
    def register_plugin(self, plugin: ParserPlugin) -> None:
        """Register a plugin instance
        
        Args:
            plugin: Plugin instance to register
        """
        plugin_name = plugin.get_name()
        
        if plugin_name in self.registered_plugins:
            existing_priority = self._plugin_priorities.get(plugin_name, 0)
            new_priority = plugin.get_priority()
            
            if new_priority <= existing_priority:
                logger.debug(f"Plugin {plugin_name} already registered with higher priority")
                return
                
        self.registered_plugins[plugin_name] = plugin
        
        # Register the parser class from the plugin
        parser_class = plugin.get_parser_class()
        self.register_parser(plugin_name, parser_class, plugin.get_priority())
        
        logger.info(f"Registered plugin: {plugin_name}")
    
    def get_parser_for_file(self, file_path: str, institution: str = None) -> Optional[FileParser]:
        """Get appropriate parser for a file
        
        Args:
            file_path: Path to the file to parse
            institution: Institution name (if known)
            
        Returns:
            Parser instance if found, None otherwise
        """
        # First try plugins (they have higher priority)
        best_plugin = None
        best_priority = float('-inf')
        
        for plugin_name, plugin in self.registered_plugins.items():
            if plugin.can_handle_file(file_path, institution):
                priority = plugin.get_priority()
                if priority > best_priority:
                    best_plugin = plugin
                    best_priority = priority
        
        if best_plugin:
            parser_class = best_plugin.get_parser_class()
            return parser_class(self.config)
        
        # Fall back to built-in parsers based on file extension
        file_ext = Path(file_path).suffix.lower()
        
        # Map extensions to parser types
        extension_map = {
            '.qfx': 'qfx',
            '.ofx': 'qfx',
            '.csv': 'csv',
            '.pdf': 'pdf'
        }
        
        parser_type = extension_map.get(file_ext)
        if parser_type and parser_type in self.registered_parsers:
            parser_class = self.registered_parsers[parser_type]
            return parser_class(self.config)
        
        logger.warning(f"No parser found for file: {file_path}")
        return None
    
    def get_parser_by_type(self, parser_type: str) -> Optional[FileParser]:
        """Get parser by type name
        
        Args:
            parser_type: Type of parser (e.g., 'qfx', 'csv', 'pdf')
            
        Returns:
            Parser instance if found, None otherwise
        """
        if parser_type in self.registered_parsers:
            parser_class = self.registered_parsers[parser_type]
            return parser_class(self.config)
        
        return None
    
    def get_available_parsers(self) -> List[str]:
        """Get list of available parser types
        
        Returns:
            List of parser type names
        """
        return list(self.registered_parsers.keys())
    
    def get_available_plugins(self) -> List[str]:
        """Get list of available plugin names
        
        Returns:
            List of plugin names
        """
        return list(self.registered_plugins.keys())
    
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific plugin
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Dictionary with plugin information or None if not found
        """
        if plugin_name not in self.registered_plugins:
            return None
            
        plugin = self.registered_plugins[plugin_name]
        
        return {
            'name': plugin.get_name(),
            'supported_institutions': plugin.get_supported_institutions(),
            'supported_extensions': plugin.get_supported_extensions(),
            'priority': plugin.get_priority(),
            'parser_class': plugin.get_parser_class().__name__
        }
    
    def reload_plugins(self) -> None:
        """Reload all plugins from configured directories"""
        # Clear existing plugins (but keep built-in parsers)
        plugins_to_remove = list(self.registered_plugins.keys())
        for plugin_name in plugins_to_remove:
            if plugin_name in self.registered_parsers:
                # Only remove if it's not a built-in parser
                priority = self._plugin_priorities.get(plugin_name, 0)
                if priority >= 0:  # Built-in parsers have negative priority
                    del self.registered_parsers[plugin_name]
                    del self._plugin_priorities[plugin_name]
            del self.registered_plugins[plugin_name]
        
        # Reload plugins
        self.load_plugins()
        logger.info("Plugins reloaded")


class SimpleParserPlugin(ParserPlugin):
    """Simple implementation of ParserPlugin for easy plugin creation"""
    
    def __init__(self, name: str, parser_class: Type[FileParser], 
                 institutions: List[str], extensions: List[str], priority: int = 0):
        """Initialize simple plugin
        
        Args:
            name: Plugin name
            parser_class: Parser class
            institutions: Supported institutions
            extensions: Supported file extensions
            priority: Plugin priority
        """
        self._name = name
        self._parser_class = parser_class
        self._institutions = institutions
        self._extensions = extensions
        self._priority = priority
    
    def get_name(self) -> str:
        return self._name
    
    def get_parser_class(self) -> Type[FileParser]:
        return self._parser_class
    
    def get_supported_institutions(self) -> List[str]:
        return self._institutions
    
    def get_supported_extensions(self) -> List[str]:
        return self._extensions
    
    def get_priority(self) -> int:
        return self._priority