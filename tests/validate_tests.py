"""
Test validation script to ensure all tests are properly structured and runnable.

Validates test file structure, imports, and basic functionality.
"""

import os
import sys
import ast
import importlib.util
from pathlib import Path

def validate_test_file(file_path):
    """Validate a single test file."""
    issues = []
    
    try:
        # Check if file can be parsed
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
            return issues
        
        # Check for required elements
        has_imports = False
        has_test_functions = False
        has_test_classes = False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                has_imports = True
            
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                has_test_functions = True
            
            if isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                has_test_classes = True
        
        if not has_imports:
            issues.append("No imports found")
        
        if not has_test_functions and not has_test_classes:
            issues.append("No test functions or test classes found")
        
        # Check docstring
        if not ast.get_docstring(tree):
            issues.append("Missing module docstring")
        
    except Exception as e:
        issues.append(f"Error reading file: {e}")
    
    return issues

def validate_test_directory(directory):
    """Validate all test files in a directory."""
    print(f"\nValidating {directory}...")
    
    test_files = list(Path(directory).glob('test_*.py'))
    
    if not test_files:
        print(f"  ⚠️  No test files found in {directory}")
        return False
    
    all_valid = True
    
    for test_file in test_files:
        issues = validate_test_file(test_file)
        
        if issues:
            print(f"  ❌ {test_file.name}:")
            for issue in issues:
                print(f"    - {issue}")
            all_valid = False
        else:
            print(f"  ✅ {test_file.name}")
    
    return all_valid

def check_test_imports():
    """Check if test files can import required modules."""
    print("\nChecking test imports...")
    
    # Add lambda paths to sys.path
    lambda_paths = [
        'lambda/shared',
        'lambda/file-upload',
        'lambda/lead-splitter',
        'lambda/deepseek-caller',
        'lambda/lead-reader',
        'lambda/lead-exporter',
        'lambda/chatbot'
    ]
    
    for path in lambda_paths:
        if os.path.exists(path):
            sys.path.insert(0, path)
    
    # Test critical imports
    critical_imports = [
        ('pytest', 'pytest'),
        ('boto3', 'boto3'),
        ('moto', 'moto'),
        ('pandas', 'pandas'),
        ('requests', 'requests')
    ]
    
    all_imports_ok = True
    
    for module_name, import_name in critical_imports:
        try:
            __import__(import_name)
            print(f"  ✅ {module_name}")
        except ImportError as e:
            print(f"  ❌ {module_name}: {e}")
            all_imports_ok = False
    
    return all_imports_ok

def validate_pytest_markers():
    """Validate that pytest markers are properly used."""
    print("\nValidating pytest markers...")
    
    valid_markers = {
        'unit', 'integration', 'e2e', 'performance', 
        'security', 'deepseek', 'slow'
    }
    
    issues = []
    
    # Check all test files for marker usage
    for test_dir in ['tests/unit', 'tests/integration', 'tests/e2e', 'tests/performance', 'tests/security']:
        if not os.path.exists(test_dir):
            continue
        
        for test_file in Path(test_dir).glob('test_*.py'):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Look for @pytest.mark.* decorators
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if '@pytest.mark.' in line:
                        # Extract marker name
                        marker = line.strip().split('@pytest.mark.')[1].split('(')[0].split()[0]
                        if marker not in valid_markers:
                            issues.append(f"{test_file}:{i+1} - Unknown marker: {marker}")
            
            except Exception as e:
                issues.append(f"Error checking {test_file}: {e}")
    
    if issues:
        print("  ❌ Marker issues found:")
        for issue in issues:
            print(f"    - {issue}")
        return False
    else:
        print("  ✅ All markers are valid")
        return True

def check_test_coverage():
    """Check test coverage of lambda functions."""
    print("\nChecking test coverage...")
    
    # Map lambda functions to their test files
    lambda_to_test_mapping = {
        'lambda/file-upload/lambda_function.py': 'tests/unit/test_file_upload.py',
        'lambda/lead-splitter/lambda_function.py': 'tests/unit/test_lead_splitter.py',
        'lambda/deepseek-caller/lambda_function.py': 'tests/unit/test_deepseek_caller.py',
        'lambda/lead-reader/lambda_function.py': 'tests/unit/test_lead_reader.py',
        'lambda/lead-exporter/lambda_function.py': 'tests/unit/test_lead_exporter.py',
        'lambda/chatbot/lambda_function.py': 'tests/unit/test_chatbot.py',
    }
    
    coverage_issues = []
    
    for lambda_file, test_file in lambda_to_test_mapping.items():
        if os.path.exists(lambda_file):
            if os.path.exists(test_file):
                print(f"  ✅ {lambda_file} -> {test_file}")
            else:
                print(f"  ❌ {lambda_file} -> {test_file} (missing)")
                coverage_issues.append(f"Missing test file: {test_file}")
        else:
            print(f"  ⚠️  Lambda function not found: {lambda_file}")
    
    return len(coverage_issues) == 0

def main():
    """Main validation function."""
    print("🔍 Test Validation Report")
    print("=" * 50)
    
    all_valid = True
    
    # Check test directory structure
    test_directories = [
        'tests/unit',
        'tests/integration', 
        'tests/e2e',
        'tests/performance',
        'tests/security'
    ]
    
    for directory in test_directories:
        if os.path.exists(directory):
            valid = validate_test_directory(directory)
            all_valid &= valid
        else:
            print(f"\n⚠️  Directory not found: {directory}")
    
    # Check imports
    imports_ok = check_test_imports()
    all_valid &= imports_ok
    
    # Check pytest markers
    markers_ok = validate_pytest_markers()
    all_valid &= markers_ok
    
    # Check test coverage
    coverage_ok = check_test_coverage()
    all_valid &= coverage_ok
    
    # Check for conftest.py
    print(f"\nChecking configuration files...")
    if os.path.exists('tests/conftest.py'):
        print("  ✅ tests/conftest.py")
    else:
        print("  ❌ tests/conftest.py (missing)")
        all_valid = False
    
    if os.path.exists('pytest.ini'):
        print("  ✅ pytest.ini")
    else:
        print("  ⚠️  pytest.ini (missing - optional)")
    
    # Summary
    print(f"\n{'='*50}")
    if all_valid:
        print("🎉 All tests are properly structured!")
        return 0
    else:
        print("💥 Test validation issues found!")
        print("\nRecommendations:")
        print("- Fix syntax errors in test files")
        print("- Add missing test functions/classes")
        print("- Add module docstrings")
        print("- Install missing dependencies")
        print("- Create missing test files")
        return 1

if __name__ == '__main__':
    sys.exit(main())