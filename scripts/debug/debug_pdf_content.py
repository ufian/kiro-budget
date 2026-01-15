#!/usr/bin/env python3
"""Debug script to examine PDF content structure."""

import pdfplumber

def examine_pdf_structure():
    """Examine the PDF structure to understand the data format"""
    
    pdf_file = os.path.join(os.path.dirname(__file__), '..', '..', "raw/chase/20251104-statements-8147-.pdf")
    
    print("=== PDF Structure Analysis ===")
    
    with pdfplumber.open(pdf_file) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        
        # Examine first few pages
        for page_num in range(min(3, len(pdf.pages))):
            page = pdf.pages[page_num]
            print(f"\n--- Page {page_num + 1} ---")
            
            # Extract tables
            tables = page.extract_tables()
            print(f"Tables found: {len(tables)}")
            
            if tables:
                for table_idx, table in enumerate(tables):
                    print(f"\nTable {table_idx + 1}:")
                    print(f"  Rows: {len(table)}")
                    print(f"  Columns: {len(table[0]) if table else 0}")
                    
                    # Show header row
                    if table and len(table) > 0:
                        print(f"  Header: {table[0]}")
                    
                    # Show first few data rows
                    if table and len(table) > 1:
                        print("  Sample data rows:")
                        for i, row in enumerate(table[1:6]):  # First 5 data rows
                            print(f"    Row {i+1}: {row}")
            
            # Also extract raw text to see format
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                print(f"\nRaw text lines (first 20):")
                for i, line in enumerate(lines[:20]):
                    if line.strip():
                        print(f"  {i+1:2d}: {line}")

if __name__ == "__main__":
    examine_pdf_structure()