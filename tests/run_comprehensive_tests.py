"""
Comprehensive test runner for the lead management system.

Runs all test suites including unit, integration, end-to-end, performance,
and security tests with proper reporting and coverage analysis.
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime
import json

def run_command(command, description, capture_output=True):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {command}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        if capture_output:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )
        else:
            result = subprocess.run(
                command,
                shell=True,
                cwd=os.path.dirname(os.path.dirname(__file__))
            )
        
        execution_time = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ SUCCESS ({execution_time:.2f}s)")
            if capture_output and result.stdout:
                print("STDOUT:")
                print(result.stdout)
        else:
            print(f"❌ FAILED ({execution_time:.2f}s)")
            if capture_output:
                if result.stdout:
                    print("STDOUT:")
                    print(result.stdout)
                if result.stderr:
                    print("STDERR:")
                    print(result.stderr)
        
        return result.returncode == 0, result
    
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"❌ ERROR ({execution_time:.2f}s): {str(e)}")
        return False, None

def check_dependencies():
    """Check if all required dependencies are installed."""
    print("Checking dependencies...")
    
    required_packages = [
        'pytest',
        'pytest-mock',
        'boto3',
        'moto',
        'pandas',
        'requests',
        'openpyxl'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    
    return True

def run_unit_tests(verbose=False):
    """Run unit tests."""
    cmd = "python -m pytest tests/unit/ -v"
    if verbose:
        cmd += " -s"
    
    return run_command(cmd, "Unit Tests", capture_output=not verbose)

def run_integration_tests(verbose=False, include_deepseek=False):
    """Run integration tests."""
    cmd = "python -m pytest tests/integration/ -v"
    if not include_deepseek:
        cmd += " -m 'not deepseek'"
    if verbose:
        cmd += " -s"
    
    return run_command(cmd, "Integration Tests", capture_output=not verbose)

def run_e2e_tests(verbose=False):
    """Run end-to-end tests."""
    cmd = "python -m pytest tests/e2e/ -v"
    if verbose:
        cmd += " -s"
    
    return run_command(cmd, "End-to-End Tests", capture_output=not verbose)

def run_performance_tests(verbose=False):
    """Run performance tests."""
    cmd = "python -m pytest tests/performance/ -v -m performance"
    if verbose:
        cmd += " -s"
    
    return run_command(cmd, "Performance Tests", capture_output=not verbose)

def run_security_tests(verbose=False):
    """Run security tests."""
    cmd = "python -m pytest tests/security/ -v -m security"
    if verbose:
        cmd += " -s"
    
    return run_command(cmd, "Security Tests", capture_output=not verbose)

def run_deepseek_tests(verbose=False):
    """Run DeepSeek API integration tests."""
    if not os.environ.get('DEEPSEEK_API_KEY'):
        print("⚠️  DEEPSEEK_API_KEY not set, skipping DeepSeek tests")
        return True, None
    
    cmd = "python -m pytest tests/integration/test_deepseek_api_integration.py -v -m deepseek"
    if verbose:
        cmd += " -s"
    
    return run_command(cmd, "DeepSeek API Integration Tests", capture_output=not verbose)

def run_duplicate_handling_tests(verbose=False):
    """Run comprehensive duplicate handling E2E tests."""
    cmd = "python tests/run_duplicate_handling_e2e_tests.py"
    if verbose:
        cmd += " -v"
    
    return run_command(cmd, "Duplicate Handling E2E Tests", capture_output=not verbose)

def run_progress_update_tests(verbose=False):
    """Run progress indicator fix validation tests."""
    cmd = "python -m pytest tests/integration/test_progress_update_fix.py -v"
    if verbose:
        cmd += " -s"
    
    return run_command(cmd, "Progress Update Fix Tests", capture_output=not verbose)

def run_coverage_analysis():
    """Run test coverage analysis."""
    # Install coverage if not available
    try:
        import coverage
    except ImportError:
        print("Installing coverage...")
        subprocess.run([sys.executable, "-m", "pip", "install", "coverage"])
    
    # Run tests with coverage
    cmd = "python -m coverage run -m pytest tests/unit/ tests/integration/ -m 'not deepseek and not performance and not security'"
    success, _ = run_command(cmd, "Coverage Analysis", capture_output=True)
    
    if success:
        # Generate coverage report
        run_command("python -m coverage report", "Coverage Report", capture_output=False)
        run_command("python -m coverage html", "HTML Coverage Report", capture_output=True)
        print("📊 HTML coverage report generated in htmlcov/index.html")
    
    return success

def validate_test_structure():
    """Validate test file structure and naming."""
    print("\nValidating test structure...")
    
    test_dirs = ['unit', 'integration', 'e2e', 'performance', 'security']
    issues = []
    
    for test_dir in test_dirs:
        dir_path = os.path.join('tests', test_dir)
        if not os.path.exists(dir_path):
            issues.append(f"Missing test directory: {dir_path}")
            continue
        
        # Check for test files
        test_files = [f for f in os.listdir(dir_path) if f.startswith('test_') and f.endswith('.py')]
        if not test_files:
            issues.append(f"No test files found in {dir_path}")
        else:
            print(f"✅ {test_dir}: {len(test_files)} test files")
    
    # Check for conftest.py
    if not os.path.exists('tests/conftest.py'):
        issues.append("Missing tests/conftest.py")
    else:
        print("✅ conftest.py found")
    
    if issues:
        print("\n⚠️  Test structure issues:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    
    return True

def generate_test_report(results):
    """Generate a comprehensive test report."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'results': results,
        'summary': {
            'total_suites': len(results),
            'passed_suites': sum(1 for r in results.values() if r['success']),
            'failed_suites': sum(1 for r in results.values() if not r['success']),
            'skipped_suites': sum(1 for r in results.values() if r.get('skipped', False))
        }
    }
    
    # Write JSON report
    with open('test_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Write human-readable report
    with open('test_report.txt', 'w') as f:
        f.write("Lead Management System - Test Report\n")
        f.write("=" * 50 + "\n")
        f.write(f"Generated: {report['timestamp']}\n\n")
        
        f.write("Summary:\n")
        f.write(f"  Total test suites: {report['summary']['total_suites']}\n")
        f.write(f"  Passed: {report['summary']['passed_suites']}\n")
        f.write(f"  Failed: {report['summary']['failed_suites']}\n")
        f.write(f"  Skipped: {report['summary']['skipped_suites']}\n\n")
        
        f.write("Detailed Results:\n")
        for suite_name, result in results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            if result.get('skipped'):
                status = "⏭️  SKIP"
            
            f.write(f"  {suite_name}: {status}")
            if result.get('execution_time'):
                f.write(f" ({result['execution_time']:.2f}s)")
            f.write("\n")
            
            if not result['success'] and result.get('error'):
                f.write(f"    Error: {result['error']}\n")
    
    print(f"\n📋 Test reports generated:")
    print(f"  - test_report.json")
    print(f"  - test_report.txt")

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='Comprehensive test runner for lead management system')
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--e2e', action='store_true', help='Run end-to-end tests only')
    parser.add_argument('--performance', action='store_true', help='Run performance tests only')
    parser.add_argument('--security', action='store_true', help='Run security tests only')
    parser.add_argument('--deepseek', action='store_true', help='Run DeepSeek API tests only')
    parser.add_argument('--duplicate-handling', action='store_true', help='Run duplicate handling E2E tests only')
    parser.add_argument('--coverage', action='store_true', help='Run coverage analysis')
    parser.add_argument('--all', action='store_true', help='Run all test suites')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--skip-deps', action='store_true', help='Skip dependency check')
    parser.add_argument('--include-deepseek', action='store_true', help='Include DeepSeek tests in integration suite')
    
    args = parser.parse_args()
    
    print("🧪 Lead Management System - Comprehensive Test Runner")
    print("=" * 60)
    
    # Check dependencies
    if not args.skip_deps and not check_dependencies():
        print("❌ Dependency check failed. Use --skip-deps to bypass.")
        return 1
    
    # Validate test structure
    if not validate_test_structure():
        print("❌ Test structure validation failed.")
        return 1
    
    results = {}
    overall_success = True
    
    # Determine which tests to run
    run_all = args.all or not any([args.unit, args.integration, args.e2e, 
                                  args.performance, args.security, args.deepseek, 
                                  getattr(args, 'duplicate_handling', False), args.coverage])
    
    try:
        # Unit tests
        if run_all or args.unit:
            start_time = time.time()
            success, result = run_unit_tests(args.verbose)
            execution_time = time.time() - start_time
            
            results['unit_tests'] = {
                'success': success,
                'execution_time': execution_time
            }
            overall_success &= success
        
        # Integration tests
        if run_all or args.integration:
            start_time = time.time()
            success, result = run_integration_tests(args.verbose, args.include_deepseek)
            execution_time = time.time() - start_time
            
            results['integration_tests'] = {
                'success': success,
                'execution_time': execution_time
            }
            overall_success &= success
        
        # End-to-end tests
        if run_all or args.e2e:
            start_time = time.time()
            success, result = run_e2e_tests(args.verbose)
            execution_time = time.time() - start_time
            
            results['e2e_tests'] = {
                'success': success,
                'execution_time': execution_time
            }
            overall_success &= success
        
        # Performance tests
        if run_all or args.performance:
            start_time = time.time()
            success, result = run_performance_tests(args.verbose)
            execution_time = time.time() - start_time
            
            results['performance_tests'] = {
                'success': success,
                'execution_time': execution_time
            }
            overall_success &= success
        
        # Security tests
        if run_all or args.security:
            start_time = time.time()
            success, result = run_security_tests(args.verbose)
            execution_time = time.time() - start_time
            
            results['security_tests'] = {
                'success': success,
                'execution_time': execution_time
            }
            overall_success &= success
        
        # DeepSeek tests
        if run_all or args.deepseek:
            start_time = time.time()
            success, result = run_deepseek_tests(args.verbose)
            execution_time = time.time() - start_time
            
            if result is None:  # Skipped
                results['deepseek_tests'] = {
                    'success': True,
                    'skipped': True,
                    'execution_time': execution_time
                }
            else:
                results['deepseek_tests'] = {
                    'success': success,
                    'execution_time': execution_time
                }
                overall_success &= success
        
        # Duplicate handling E2E tests
        if run_all or getattr(args, 'duplicate_handling', False):
            start_time = time.time()
            success, result = run_duplicate_handling_tests(args.verbose)
            execution_time = time.time() - start_time
            
            results['duplicate_handling_tests'] = {
                'success': success,
                'execution_time': execution_time
            }
            overall_success &= success
        
        # Progress update fix tests
        if run_all:  # Always run with --all, but not as separate option
            start_time = time.time()
            success, result = run_progress_update_tests(args.verbose)
            execution_time = time.time() - start_time
            
            results['progress_update_tests'] = {
                'success': success,
                'execution_time': execution_time
            }
            overall_success &= success
        
        # Coverage analysis
        if args.coverage or run_all:
            start_time = time.time()
            success = run_coverage_analysis()
            execution_time = time.time() - start_time
            
            results['coverage_analysis'] = {
                'success': success,
                'execution_time': execution_time
            }
            # Don't fail overall if coverage fails
    
    except KeyboardInterrupt:
        print("\n⚠️  Test execution interrupted by user")
        return 1
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        return 1
    
    # Generate test report
    generate_test_report(results)
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST EXECUTION SUMMARY")
    print(f"{'='*60}")
    
    for suite_name, result in results.items():
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        if result.get('skipped'):
            status = "⏭️  SKIP"
        
        print(f"{suite_name.replace('_', ' ').title()}: {status} ({result['execution_time']:.2f}s)")
    
    if overall_success:
        print(f"\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n💥 SOME TESTS FAILED!")
        return 1

if __name__ == '__main__':
    sys.exit(main())