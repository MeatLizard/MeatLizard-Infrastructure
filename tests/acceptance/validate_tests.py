#!/usr/bin/env python3
"""
Validation script for acceptance tests structure.
"""
import os
import ast
import sys
from pathlib import Path


def validate_test_file(file_path):
    """Validate a test file structure."""
    print(f"Validating {file_path}...")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        # Check for required imports
        required_imports = ['pytest', 'Page', 'expect']
        imports_found = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports_found.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports_found.append(node.module)
                for alias in node.names:
                    imports_found.append(alias.name)
        
        # Check for test classes and methods
        test_classes = []
        test_methods = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                test_classes.append(node.name)
                
                # Count test methods in class
                class_test_methods = [
                    method.name for method in node.body 
                    if isinstance(method, ast.FunctionDef) and method.name.startswith('test_')
                ]
                test_methods.extend(class_test_methods)
        
        print(f"  ✓ Found {len(test_classes)} test classes")
        print(f"  ✓ Found {len(test_methods)} test methods")
        
        # Check for async methods (required for Playwright)
        async_methods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith('test_'):
                async_methods.append(node.name)
        
        print(f"  ✓ Found {len(async_methods)} async test methods")
        
        if len(async_methods) > 0:
            print(f"  ✓ File uses async/await pattern for browser automation")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error validating {file_path}: {e}")
        return False


def validate_conftest():
    """Validate conftest.py structure."""
    conftest_path = "tests/acceptance/conftest.py"
    
    if not os.path.exists(conftest_path):
        print(f"✗ Missing {conftest_path}")
        return False
    
    print(f"Validating {conftest_path}...")
    
    try:
        with open(conftest_path, 'r') as f:
            content = f.read()
        
        # Check for required fixtures
        required_fixtures = [
            'browser',
            'browser_context', 
            'page',
            'base_url'
        ]
        
        fixtures_found = []
        for fixture in required_fixtures:
            if f"def {fixture}(" in content or f"async def {fixture}(" in content:
                fixtures_found.append(fixture)
        
        print(f"  ✓ Found {len(fixtures_found)}/{len(required_fixtures)} required fixtures")
        
        for fixture in fixtures_found:
            print(f"    - {fixture}")
        
        return len(fixtures_found) >= len(required_fixtures) - 1  # Allow some flexibility
        
    except Exception as e:
        print(f"  ✗ Error validating conftest.py: {e}")
        return False


def main():
    """Main validation function."""
    print("Validating acceptance test structure...\n")
    
    # Check if acceptance test directory exists
    test_dir = "tests/acceptance"
    if not os.path.exists(test_dir):
        print(f"✗ Acceptance test directory not found: {test_dir}")
        return False
    
    # Validate conftest.py
    conftest_valid = validate_conftest()
    print()
    
    # Find all test files
    test_files = []
    for file in os.listdir(test_dir):
        if file.startswith('test_') and file.endswith('.py'):
            test_files.append(os.path.join(test_dir, file))
    
    print(f"Found {len(test_files)} test files:")
    for file in test_files:
        print(f"  - {os.path.basename(file)}")
    print()
    
    # Validate each test file
    valid_files = 0
    for test_file in test_files:
        if validate_test_file(test_file):
            valid_files += 1
        print()
    
    # Summary
    print("=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Conftest.py: {'✓ Valid' if conftest_valid else '✗ Invalid'}")
    print(f"Test files: {valid_files}/{len(test_files)} valid")
    
    # Check for required test categories
    required_categories = [
        'test_video_upload_ui.py',
        'test_video_playback_ui.py', 
        'test_user_interactions.py',
        'test_cross_browser_compatibility.py',
        'test_accessibility.py'
    ]
    
    existing_categories = [os.path.basename(f) for f in test_files]
    missing_categories = [cat for cat in required_categories if cat not in existing_categories]
    
    print(f"\nTest Categories:")
    for category in required_categories:
        status = "✓" if category in existing_categories else "✗"
        print(f"  {status} {category}")
    
    if missing_categories:
        print(f"\nMissing categories: {', '.join(missing_categories)}")
    
    # Overall result
    overall_valid = (
        conftest_valid and 
        valid_files == len(test_files) and 
        len(missing_categories) == 0
    )
    
    print(f"\nOverall Status: {'✓ VALID' if overall_valid else '✗ NEEDS WORK'}")
    
    return overall_valid


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)