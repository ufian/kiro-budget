#!/usr/bin/env python3
"""Debug CLI processing to see what's happening."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from kiro_budget.cli import FinancialDataParserCLI

def debug_cli_processing():
    """Debug the CLI processing"""
    
    cli = FinancialDataParserCLI()
    
    # Process the chase directory
    result = cli.process_files(directories=[os.path.join(os.path.dirname(__file__), '..', '..', "raw/chase")], force_reprocess=True)
    
    print("CLI processing result:")
    print(result)

if __name__ == "__main__":
    debug_cli_processing()