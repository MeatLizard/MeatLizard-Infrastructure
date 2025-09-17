#!/usr/bin/env python3
"""
Test runner for acceptance tests with browser automation.
"""
import asyncio
import subprocess
import sys
import os
from pathlib import Path


async def install_playwright():
    """Install Playwright browsers if not already installed."""
    try:
        result = subprocess.run(
            ["playwright", "install", "chromium", "firefox", "webkit"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("Failed to install Playwright browsers:")
            print(result.stderr)
            return False
        return True
    except FileNotFoundError:
        print("Playwright not found. Please install with: pip install playwright")
        return False


async def start_test_server():
    """Start the test server for acceptance tests."""
    # This would start your FastAPI server in test mode
    # For now, we'll assume it's running on localhost:8000
    print("Assuming test server is running on http://localhost:8000")
    return True


async def run_acceptance_tests():
    """Run all acceptance tests."""
    
    # Set environment variables for testing
    os.environ["TEST_BASE_URL"] = "http://localhost:8000"
    os.environ["PYTEST_CURRENT_TEST"] = "acceptance"
    
    # Install Playwright browsers
    print("Installing Playwright browsers...")
    if not await install_playwright():
        return False
    
    # Start test server
    print("Starting test server...")
    if not await start_test_server():
        return False
    
    # Run acceptance tests
    print("Running acceptance tests...")
    
    test_files = [
        "tests/acceptance/test_video_upload_ui.py",
        "tests/acceptance/test_video_playback_ui.py", 
        "tests/acceptance/test_user_interactions.py",
        "tests/acceptance/test_cross_browser_compatibility.py"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\nRunning {test_file}...")
            result = subprocess.run([
                "python", "-m", "pytest", 
                test_file,
                "-v",
                "--tb=short",
                "--browser=chromium",
                "--headed=false"
            ])
            
            if result.returncode != 0:
                print(f"Tests failed in {test_file}")
                return False
        else:
            print(f"Test file not found: {test_file}")
    
    print("\nAll acceptance tests completed successfully!")
    return True


async def run_cross_browser_tests():
    """Run cross-browser compatibility tests."""
    
    browsers = ["chromium", "firefox", "webkit"]
    
    for browser in browsers:
        print(f"\nRunning tests with {browser}...")
        result = subprocess.run([
            "python", "-m", "pytest",
            "tests/acceptance/test_cross_browser_compatibility.py",
            "-v",
            f"--browser={browser}",
            "--headed=false"
        ])
        
        if result.returncode != 0:
            print(f"Cross-browser tests failed with {browser}")
            return False
    
    print("\nAll cross-browser tests completed successfully!")
    return True


async def run_accessibility_tests():
    """Run accessibility tests."""
    
    print("Running accessibility tests...")
    result = subprocess.run([
        "python", "-m", "pytest",
        "tests/acceptance/",
        "-k", "accessibility",
        "-v",
        "--tb=short"
    ])
    
    if result.returncode == 0:
        print("Accessibility tests completed successfully!")
        return True
    else:
        print("Accessibility tests failed")
        return False


async def main():
    """Main test runner."""
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        
        if test_type == "cross-browser":
            success = await run_cross_browser_tests()
        elif test_type == "accessibility":
            success = await run_accessibility_tests()
        elif test_type == "all":
            success = (
                await run_acceptance_tests() and
                await run_cross_browser_tests() and
                await run_accessibility_tests()
            )
        else:
            print(f"Unknown test type: {test_type}")
            print("Available options: cross-browser, accessibility, all")
            success = False
    else:
        success = await run_acceptance_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())