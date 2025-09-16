#!/usr/bin/env python3
"""
Simple syntax validation for Python files.
"""

import ast
import sys

def validate_python_syntax(file_path):
    """Validate Python syntax of a file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Parse the AST to check syntax
        ast.parse(content)
        print(f"✓ {file_path} has valid Python syntax")
        return True
        
    except SyntaxError as e:
        print(f"✗ Syntax error in {file_path}: {e}")
        print(f"  Line {e.lineno}: {e.text}")
        return False
    except Exception as e:
        print(f"✗ Error reading {file_path}: {e}")
        return False

def main():
    """Validate syntax of key files."""
    
    files_to_check = [
        "web/app/models.py",
        "web/alembic/versions/005_add_multi_service_platform_models.py"
    ]
    
    print("Validating Python syntax...")
    print("=" * 40)
    
    all_valid = True
    
    for file_path in files_to_check:
        if not validate_python_syntax(file_path):
            all_valid = False
    
    print("\n" + "=" * 40)
    if all_valid:
        print("✓ All files have valid Python syntax!")
    else:
        print("✗ Some files have syntax errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()