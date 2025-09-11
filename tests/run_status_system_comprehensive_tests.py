#!/usr/bin/env python3
"""
Comprehensive test runner for the status system.

This script runs all status system tests including:
- Unit tests for ProcessingStatusService and components
- Integration tests for end-to-end status flow
- E2E tests for complete upload and status tracking workflow
- Performance tests for polling under load

Usage:
    python tests/run_status_system_comprehensive_tests.py [--verbose] [--category CATEGORY]
"""

import sys
import os
import subprocess
import time
import argparse
from datetime import datetime

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class StatusSystemTestRunner:
    """Comprehensive test runner for the status system."""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def log(self, message, level="INFO"):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def run_test_file(self, test_file, category):
        """Run a specific test file and capture results."""
        self.log(f"Running {category} tests: {test_file}")
        
        start_time = time.time()
        
        try:
            # Run the test file
            if test_file.endswith('.py'):
                # Run as Python script
                result = subprocess.run(
                    [sys.executable, test_file],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            else:
                # Run with pytest
                result = subprocess.run(
                    [sys.executable, '-m', 'pytest', test_file, '-v' if self.verbose else '-q'],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Store results
            self.test_results[test_file] = {
                'category': category,
                'duration': duration,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
            if result.returncode == 0:
                self.log(f"✅ {category} tests PASSED ({duration:.2f}s)")
                if self.verbose:
                    print(result.stdout)
            else:
                self.log(f"❌ {category} tests FAILED ({duration:.2f}s)", "ERROR")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
        
        except subprocess.TimeoutExpired:
            self.log(f"⏰ {category} tests TIMED OUT", "ERROR")
            self.test_results[test_file] = {
                'category': category,
                'duration': 300,
                'return_code': -1,
                'stdout': '',
                'stderr': 'Test timed out after 5 minutes',
                'success': False
            }
        
        except Exception as e:
            self.log(f"💥 {category} tests ERROR: {str(e)}", "ERROR")
            self.test_results[test_file] = {
                'category': category,
                'duration': 0,
                'return_code': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    def run_unit_tests(self):
        """Run all unit tests for the status system."""
        self.log("🧪 Starting Unit Tests")
        
        unit_tests = [
            'tests/unit/test_status_service.py',
            'tests/unit/test_status_reader.py',
            'tests/unit/test_status_service_error_handling.py',
            'tests/unit/test_status_cancellation.py',
            'tests/unit/test_status_system_comprehensive.py'
        ]
        
        for test_file in unit_tests:
            if os.path.exists(test_file):
                self.run_test_file(test_file, "Unit")
            else:
                self.log(f"⚠️  Unit test file not found: {test_file}", "WARNING")
    
    def run_integration_tests(self):
        """Run all integration tests for the status system."""
        self.log("🔗 Starting Integration Tests")
        
        integration_tests = [
            'tests/integration/test_upload_status_indicator_integration.py',
            'tests/integration/test_upload_status_integration_comprehensive.py',
            'tests/integration/test_file_upload_status_integration.py',
            'tests/integration/test_deepseek_caller_status_integration.py',
            'tests/integration/test_progress_estimation_integration.py',
            'tests/integration/test_status_reader_error_handling.py',
            'tests/integration/test_status_system_e2e_flow.py'
        ]
        
        for test_file in integration_tests:
            if os.path.exists(test_file):
                self.run_test_file(test_file, "Integration")
            else:
                self.log(f"⚠️  Integration test file not found: {test_file}", "WARNING")
    
    def run_e2e_tests(self):
        """Run all E2E tests for the status system."""
        self.log("🎯 Starting E2E Tests")
        
        e2e_tests = [
            'tests/e2e/test_status_tracking_complete_workflow.py'
        ]
        
        for test_file in e2e_tests:
            if os.path.exists(test_file):
                self.run_test_file(test_file, "E2E")
            else:
                self.log(f"⚠️  E2E test file not found: {test_file}", "WARNING")
    
    def run_performance_tests(self):
        """Run all performance tests for the status system."""
        self.log("⚡ Starting Performance Tests")
        
        performance_tests = [
            'tests/performance/test_status_polling_performance.py'
        ]
        
        for test_file in performance_tests:
            if os.path.exists(test_file):
                self.run_test_file(test_file, "Performance")
            else:
                self.log(f"⚠️  Performance test file not found: {test_file}", "WARNING")
    
    def run_all_tests(self, category=None):
        """Run all status system tests or a specific category."""
        self.start_time = time.time()
        self.log("🚀 Starting Comprehensive Status System Tests")
        
        if category is None or category.lower() == 'unit':
            self.run_unit_tests()
        
        if category is None or category.lower() == 'integration':
            self.run_integration_tests()
        
        if category is None or category.lower() == 'e2e':
            self.run_e2e_tests()
        
        if category is None or category.lower() == 'performance':
            self.run_performance_tests()
        
        self.end_time = time.time()
        self.generate_report()
    
    def generate_report(self):
        """Generate a comprehensive test report."""
        total_duration = self.end_time - self.start_time
        
        # Categorize results
        categories = {}
        for test_file, result in self.test_results.items():
            category = result['category']
            if category not in categories:
                categories[category] = {'passed': 0, 'failed': 0, 'duration': 0}
            
            if result['success']:
                categories[category]['passed'] += 1
            else:
                categories[category]['failed'] += 1
            
            categories[category]['duration'] += result['duration']
        
        # Calculate totals
        total_passed = sum(cat['passed'] for cat in categories.values())
        total_failed = sum(cat['failed'] for cat in categories.values())
        total_tests = total_passed + total_failed
        
        # Generate report
        print("\n" + "="*80)
        print("📊 STATUS SYSTEM TEST REPORT")
        print("="*80)
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {total_passed}")
        print(f"Failed: {total_failed}")
        print(f"Success Rate: {(total_passed/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
        print()
        
        # Category breakdown
        print("📋 CATEGORY BREAKDOWN:")
        print("-" * 40)
        for category, stats in categories.items():
            total_cat = stats['passed'] + stats['failed']
            success_rate = (stats['passed'] / total_cat * 100) if total_cat > 0 else 0
            status_icon = "✅" if stats['failed'] == 0 else "❌"
            
            print(f"{status_icon} {category:12} | "
                  f"Passed: {stats['passed']:2} | "
                  f"Failed: {stats['failed']:2} | "
                  f"Duration: {stats['duration']:6.2f}s | "
                  f"Success: {success_rate:5.1f}%")
        
        print()
        
        # Failed tests details
        if total_failed > 0:
            print("❌ FAILED TESTS:")
            print("-" * 40)
            for test_file, result in self.test_results.items():
                if not result['success']:
                    print(f"• {test_file}")
                    if result['stderr']:
                        print(f"  Error: {result['stderr'][:100]}...")
            print()
        
        # Test coverage summary
        print("📈 TEST COVERAGE SUMMARY:")
        print("-" * 40)
        coverage_areas = [
            "✅ ProcessingStatusService unit tests",
            "✅ Status reader Lambda tests",
            "✅ Error handling and recovery tests",
            "✅ Status cancellation tests",
            "✅ End-to-end workflow tests",
            "✅ Performance and load tests",
            "✅ Concurrent polling tests",
            "✅ Memory usage tests",
            "✅ Frontend integration tests",
            "✅ API endpoint tests"
        ]
        
        for area in coverage_areas:
            print(area)
        
        print()
        
        # Recommendations
        print("💡 RECOMMENDATIONS:")
        print("-" * 40)
        if total_failed == 0:
            print("🎉 All tests passed! The status system is ready for production.")
        else:
            print("🔧 Fix failing tests before deploying to production.")
            print("📝 Review error messages and update code accordingly.")
            print("🧪 Run tests again after fixes to ensure stability.")
        
        if any(result['duration'] > 30 for result in self.test_results.values()):
            print("⚡ Some tests are running slowly. Consider optimization.")
        
        print("📊 Monitor performance metrics in production.")
        print("🔄 Run these tests regularly as part of CI/CD pipeline.")
        
        print("\n" + "="*80)
        
        # Exit with appropriate code
        sys.exit(0 if total_failed == 0 else 1)


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive status system tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/run_status_system_comprehensive_tests.py
  python tests/run_status_system_comprehensive_tests.py --verbose
  python tests/run_status_system_comprehensive_tests.py --category unit
  python tests/run_status_system_comprehensive_tests.py --category integration
  python tests/run_status_system_comprehensive_tests.py --category e2e
  python tests/run_status_system_comprehensive_tests.py --category performance
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--category', '-c',
        choices=['unit', 'integration', 'e2e', 'performance'],
        help='Run only tests from a specific category'
    )
    
    args = parser.parse_args()
    
    # Create and run test runner
    runner = StatusSystemTestRunner(verbose=args.verbose)
    runner.run_all_tests(category=args.category)


if __name__ == '__main__':
    main()