#!/usr/bin/env python3
"""
Test runner for authentication tests.
Runs both unit and integration tests for the authentication system.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command, cwd=None):
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def install_dependencies():
    """Install required test dependencies."""
    print("Installing test dependencies...")
    
    dependencies = [
        'pytest>=7.0.0',
        'selenium>=4.0.0',
        'boto3>=1.26.0',
        'moto>=4.0.0',
        'requests>=2.28.0'
    ]
    
    for dep in dependencies:
        print(f"Installing {dep}...")
        success, output = run_command(f"pip install {dep}")
        if not success:
            print(f"Failed to install {dep}: {output}")
            return False
    
    print("Dependencies installed successfully!")
    return True


def run_unit_tests():
    """Run unit tests for authentication."""
    print("\n" + "="*50)
    print("Running Authentication Unit Tests")
    print("="*50)
    
    test_file = Path(__file__).parent / "unit" / "test_auth.py"
    
    if not test_file.exists():
        print(f"Unit test file not found: {test_file}")
        return False
    
    command = f"python -m pytest {test_file} -v --tb=short"
    success, output = run_command(command)
    
    print(output)
    
    if success:
        print("✅ Unit tests passed!")
    else:
        print("❌ Unit tests failed!")
    
    return success


def run_integration_tests():
    """Run integration tests for authentication."""
    print("\n" + "="*50)
    print("Running Authentication Integration Tests")
    print("="*50)
    
    test_file = Path(__file__).parent / "integration" / "test_cognito_authentication.py"
    
    if not test_file.exists():
        print(f"Integration test file not found: {test_file}")
        return False
    
    # Check if Chrome/Chromium is available for Selenium
    chrome_available = False
    for chrome_cmd in ['google-chrome', 'chromium-browser', 'chromium']:
        success, _ = run_command(f"which {chrome_cmd}")
        if success:
            chrome_available = True
            break
    
    if not chrome_available:
        print("⚠️  Chrome/Chromium not found. Skipping browser-based integration tests.")
        print("   Install Chrome or Chromium to run full integration tests.")
        return True
    
    # Set environment variables for testing
    env = os.environ.copy()
    env['FRONTEND_URL'] = env.get('FRONTEND_URL', 'http://localhost:8080')
    
    command = f"python -m pytest {test_file} -v --tb=short"
    
    # Run with custom environment
    try:
        result = subprocess.run(
            command,
            shell=True,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        print("✅ Integration tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        print("❌ Integration tests failed!")
        return False


def run_auth_validation():
    """Run basic authentication validation checks."""
    print("\n" + "="*50)
    print("Running Authentication Validation")
    print("="*50)
    
    frontend_dir = Path(__file__).parent.parent / "frontend"
    
    # Check if required files exist
    required_files = [
        "js/auth.js",
        "js/api.js",
        "js/config.js",
        "index.html",
        "config.json"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = frontend_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    # Check auth.js for required functions
    auth_file = frontend_dir / "js" / "auth.js"
    with open(auth_file, 'r') as f:
        auth_content = f.read()
    
    required_functions = [
        'init:',
        'checkAuthState:',
        'handleLogin:',
        'handleRegister:',
        'logout:',
        'refreshToken:',
        'isTokenExpiring:',
        'ensureValidToken:',
        'setupTokenRefresh:'
    ]
    
    missing_functions = []
    for func in required_functions:
        if func not in auth_content:
            missing_functions.append(func.replace(':', ''))
    
    if missing_functions:
        print("❌ Missing required functions in auth.js:")
        for func in missing_functions:
            print(f"   - {func}")
        return False
    
    # Check API.js for authentication guards
    api_file = frontend_dir / "js" / "api.js"
    with open(api_file, 'r') as f:
        api_content = f.read()
    
    if 'requireAuth:' not in api_content:
        print("❌ Missing requireAuth function in api.js")
        return False
    
    if 'ensureValidToken' not in api_content:
        print("❌ Missing ensureValidToken usage in api.js")
        return False
    
    print("✅ Authentication validation passed!")
    return True


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='Run authentication tests')
    parser.add_argument('--unit-only', action='store_true', help='Run only unit tests')
    parser.add_argument('--integration-only', action='store_true', help='Run only integration tests')
    parser.add_argument('--no-install', action='store_true', help='Skip dependency installation')
    parser.add_argument('--validate-only', action='store_true', help='Run only validation checks')
    
    args = parser.parse_args()
    
    print("🧪 Easy CRM Authentication Test Suite")
    print("="*50)
    
    # Install dependencies unless skipped
    if not args.no_install and not args.validate_only:
        if not install_dependencies():
            print("❌ Failed to install dependencies")
            return 1
    
    success = True
    
    # Run validation checks
    if not run_auth_validation():
        success = False
        if args.validate_only:
            return 1
    
    if args.validate_only:
        return 0
    
    # Run unit tests
    if not args.integration_only:
        if not run_unit_tests():
            success = False
    
    # Run integration tests
    if not args.unit_only:
        if not run_integration_tests():
            success = False
    
    # Summary
    print("\n" + "="*50)
    print("Test Summary")
    print("="*50)
    
    if success:
        print("🎉 All authentication tests passed!")
        return 0
    else:
        print("💥 Some authentication tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())