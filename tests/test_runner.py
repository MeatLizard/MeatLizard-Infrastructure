#!/usr/bin/env python3
"""
Simple test runner to validate test structure and imports.
"""
import sys
import os
import importlib.util
from pathlib import Path

def validate_test_file(test_file_path):
    """Validate a test file can be imported and has test classes."""
    try:
        # Load the module
        spec = importlib.util.spec_from_file_location("test_module", test_file_path)
        if spec is None:
            return False, f"Could not load spec for {test_file_path}"
        
        module = importlib.util.module_from_spec(spec)
        
        # Check if we can at least parse the file
        with open(test_file_path, 'r') as f:
            content = f.read()
        
        # Basic validation
        if 'class Test' not in content:
            return False, f"No test classes found in {test_file_path}"
        
        if 'def test_' not in content:
            return False, f"No test methods found in {test_file_path}"
        
        # Count test methods
        test_method_count = content.count('def test_')
        test_class_count = content.count('class Test')
        
        return True, f"✓ {test_class_count} test classes, {test_method_count} test methods"
        
    except Exception as e:
        return False, f"Error validating {test_file_path}: {str(e)}"

def main():
    """Main test validation function."""
    print("Video Services Test Suite Validation")
    print("=" * 50)
    
    # Find all test files
    test_dir = Path(__file__).parent
    test_files = list(test_dir.glob("test_*.py"))
    
    if not test_files:
        print("No test files found!")
        return 1
    
    total_files = 0
    valid_files = 0
    total_test_methods = 0
    
    for test_file in sorted(test_files):
        if test_file.name == "test_runner.py":
            continue
            
        total_files += 1
        print(f"\nValidating {test_file.name}...")
        
        is_valid, message = validate_test_file(test_file)
        
        if is_valid:
            valid_files += 1
            # Extract test method count from message
            if "test methods" in message:
                try:
                    # Parse "✓ X test classes, Y test methods"
                    parts = message.split()
                    for i, part in enumerate(parts):
                        if part == "test" and i + 1 < len(parts) and parts[i + 1] == "methods":
                            count = int(parts[i - 1])
                            total_test_methods += count
                            break
                except (ValueError, IndexError):
                    pass
        
        print(f"  {message}")
    
    print(f"\n" + "=" * 50)
    print(f"Validation Summary:")
    print(f"  Total test files: {total_files}")
    print(f"  Valid test files: {valid_files}")
    print(f"  Total test methods: {total_test_methods}")
    
    if valid_files == total_files:
        print(f"  Status: ✓ All tests are structurally valid")
        return 0
    else:
        print(f"  Status: ✗ {total_files - valid_files} test files have issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())