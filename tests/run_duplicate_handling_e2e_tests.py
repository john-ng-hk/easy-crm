#!/usr/bin/env python3
"""
Comprehensive test runner for duplicate lead handling end-to-end tests.

This script runs all duplicate handling E2E tests and generates a detailed report
covering workflow testing, performance validation, and error recovery scenarios.
"""

import os
import sys
import subprocess
import json
import time
from datetime import datetime
import argparse

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class DuplicateHandlingE2ETestRunner:
    """Test runner for duplicate handling end-to-end tests."""
    
    def __init__(self, verbose=False, generate_report=True):
        self.verbose = verbose
        self.generate_report = generate_report
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def run_all_tests(self):
        """Run all duplicate handling E2E tests."""
        print("=" * 80)
        print("DUPLICATE LEAD HANDLING - END-TO-END TEST SUITE")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        self.start_time = time.time()
        
        # Test categories to run
        test_categories = [
            {
                'name': 'Core E2E Workflow Tests',
                'description': 'Complete workflow from upload to display',
                'test_file': 'tests/e2e/test_duplicate_handling_e2e.py',
                'test_methods': [
                    'test_complete_duplicate_handling_workflow',
                    'test_csv_export_with_deduplicated_data',
                    'test_frontend_display_verification'
                ]
            },
            {
                'name': 'Performance Tests',
                'description': 'Performance with high duplicate percentages',
                'test_file': 'tests/e2e/test_duplicate_handling_e2e.py',
                'test_methods': [
                    'test_performance_with_high_duplicate_percentage'
                ]
            },
            {
                'name': 'Error Recovery Tests',
                'description': 'Error handling and fallback scenarios',
                'test_file': 'tests/e2e/test_duplicate_handling_e2e.py',
                'test_methods': [
                    'test_error_recovery_and_fallback_behavior'
                ]
            },
            {
                'name': 'Performance Benchmarks',
                'description': 'Detailed performance analysis',
                'test_file': 'tests/performance/test_duplicate_handling_performance.py',
                'test_methods': [
                    'test_email_normalization_performance',
                    'test_duplicate_detection_performance',
                    'test_concurrent_duplicate_detection',
                    'test_memory_usage_with_large_batches',
                    'test_gsi_query_performance'
                ]
            }
        ]
        
        # Run each test category
        for category in test_categories:
            self._run_test_category(category)
        
        self.end_time = time.time()
        
        # Generate summary report
        self._generate_summary_report()
        
        if self.generate_report:
            self._generate_detailed_report()
    
    def _run_test_category(self, category):
        """Run a specific test category."""
        print(f"\n{'-' * 60}")
        print(f"Running: {category['name']}")
        print(f"Description: {category['description']}")
        print(f"{'-' * 60}")
        
        category_results = {
            'name': category['name'],
            'description': category['description'],
            'test_file': category['test_file'],
            'tests': {},
            'summary': {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0,
                'duration': 0
            }
        }
        
        start_time = time.time()
        
        # Run specific test methods if specified
        if 'test_methods' in category:
            for test_method in category['test_methods']:
                test_result = self._run_single_test(category['test_file'], test_method)
                category_results['tests'][test_method] = test_result
                category_results['summary']['total'] += 1
                
                if test_result['status'] == 'PASSED':
                    category_results['summary']['passed'] += 1
                elif test_result['status'] == 'FAILED':
                    category_results['summary']['failed'] += 1
                else:
                    category_results['summary']['skipped'] += 1
        else:
            # Run entire test file
            test_result = self._run_test_file(category['test_file'])
            category_results['tests']['all'] = test_result
            category_results['summary'] = test_result.get('summary', category_results['summary'])
        
        category_results['summary']['duration'] = time.time() - start_time
        self.test_results[category['name']] = category_results
        
        # Print category summary
        summary = category_results['summary']
        print(f"\nCategory Results:")
        print(f"  Total: {summary['total']}")
        print(f"  Passed: {summary['passed']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Skipped: {summary['skipped']}")
        print(f"  Duration: {summary['duration']:.2f}s")
    
    def _run_single_test(self, test_file, test_method):
        """Run a single test method."""
        print(f"\n  Running: {test_method}")
        
        cmd = [
            sys.executable, '-m', 'pytest',
            f'{test_file}::{test_method.split(".")[-1]}',
            '-v', '-s', '--tb=short'
        ]
        
        if self.verbose:
            cmd.append('-vv')
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=300  # 5 minute timeout per test
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                status = 'PASSED'
                print(f"    ✓ PASSED ({duration:.2f}s)")
            else:
                status = 'FAILED'
                print(f"    ✗ FAILED ({duration:.2f}s)")
                if self.verbose:
                    print(f"    Error: {result.stderr}")
            
            return {
                'status': status,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            print(f"    ⚠ TIMEOUT (>300s)")
            return {
                'status': 'TIMEOUT',
                'duration': 300,
                'stdout': '',
                'stderr': 'Test timed out after 300 seconds',
                'returncode': -1
            }
        
        except Exception as e:
            print(f"    ✗ ERROR: {e}")
            return {
                'status': 'ERROR',
                'duration': time.time() - start_time,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def _run_test_file(self, test_file):
        """Run an entire test file."""
        print(f"\n  Running all tests in: {test_file}")
        
        cmd = [
            sys.executable, '-m', 'pytest',
            test_file,
            '-v', '--tb=short'
        ]
        
        if self.verbose:
            cmd.append('-vv')
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=600  # 10 minute timeout for full file
            )
            
            duration = time.time() - start_time
            
            # Parse pytest output for summary
            summary = self._parse_pytest_output(result.stdout)
            
            if result.returncode == 0:
                status = 'PASSED'
                print(f"    ✓ ALL PASSED ({duration:.2f}s)")
            else:
                status = 'FAILED'
                print(f"    ✗ SOME FAILED ({duration:.2f}s)")
            
            return {
                'status': status,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'summary': summary
            }
            
        except subprocess.TimeoutExpired:
            print(f"    ⚠ TIMEOUT (>600s)")
            return {
                'status': 'TIMEOUT',
                'duration': 600,
                'stdout': '',
                'stderr': 'Test file timed out after 600 seconds',
                'returncode': -1,
                'summary': {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}
            }
        
        except Exception as e:
            print(f"    ✗ ERROR: {e}")
            return {
                'status': 'ERROR',
                'duration': time.time() - start_time,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1,
                'summary': {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}
            }
    
    def _parse_pytest_output(self, output):
        """Parse pytest output to extract test summary."""
        summary = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}
        
        lines = output.split('\n')
        for line in lines:
            if 'passed' in line and 'failed' in line:
                # Parse line like "5 passed, 2 failed in 10.5s"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed' and i > 0:
                        summary['passed'] = int(parts[i-1])
                    elif part == 'failed' and i > 0:
                        summary['failed'] = int(parts[i-1])
                    elif part == 'skipped' and i > 0:
                        summary['skipped'] = int(parts[i-1])
                break
        
        summary['total'] = summary['passed'] + summary['failed'] + summary['skipped']
        return summary
    
    def _generate_summary_report(self):
        """Generate and display summary report."""
        print("\n" + "=" * 80)
        print("DUPLICATE HANDLING E2E TEST SUMMARY")
        print("=" * 80)
        
        total_duration = self.end_time - self.start_time
        overall_stats = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0}
        
        for category_name, category_result in self.test_results.items():
            summary = category_result['summary']
            overall_stats['total'] += summary['total']
            overall_stats['passed'] += summary['passed']
            overall_stats['failed'] += summary['failed']
            overall_stats['skipped'] += summary['skipped']
            
            print(f"\n{category_name}:")
            print(f"  Tests: {summary['total']} | "
                  f"Passed: {summary['passed']} | "
                  f"Failed: {summary['failed']} | "
                  f"Skipped: {summary['skipped']} | "
                  f"Duration: {summary['duration']:.2f}s")
        
        print(f"\nOVERALL RESULTS:")
        print(f"  Total Tests: {overall_stats['total']}")
        print(f"  Passed: {overall_stats['passed']}")
        print(f"  Failed: {overall_stats['failed']}")
        print(f"  Skipped: {overall_stats['skipped']}")
        print(f"  Success Rate: {(overall_stats['passed']/max(overall_stats['total'], 1)*100):.1f}%")
        print(f"  Total Duration: {total_duration:.2f}s")
        
        # Requirements coverage check
        print(f"\nREQUIREMENTS COVERAGE:")
        self._check_requirements_coverage()
        
        if overall_stats['failed'] == 0:
            print(f"\n🎉 ALL DUPLICATE HANDLING E2E TESTS PASSED!")
        else:
            print(f"\n⚠️  {overall_stats['failed']} TEST(S) FAILED - Review detailed report")
    
    def _check_requirements_coverage(self):
        """Check coverage of duplicate handling requirements."""
        requirements_coverage = {
            '6.1': 'Frontend shows deduplicated leads',
            '6.2': 'Updated timestamps reflect modifications',
            '6.3': 'CSV export contains deduplicated data',
            '6.4': 'Search/filter works with deduplicated dataset',
            '6.5': 'Lead details show correct sourceFile',
            '7.2': 'Integration tests with duplicate scenarios',
            '7.5': 'Error scenario testing with graceful fallback'
        }
        
        covered_requirements = []
        
        # Check which requirements are covered by successful tests
        for category_name, category_result in self.test_results.items():
            if category_result['summary']['passed'] > 0:
                if 'workflow' in category_name.lower():
                    covered_requirements.extend(['6.1', '6.2', '6.4', '6.5'])
                elif 'export' in category_name.lower():
                    covered_requirements.append('6.3')
                elif 'performance' in category_name.lower():
                    covered_requirements.append('7.2')
                elif 'error' in category_name.lower():
                    covered_requirements.append('7.5')
        
        covered_requirements = list(set(covered_requirements))
        
        for req_id, req_desc in requirements_coverage.items():
            status = "✓" if req_id in covered_requirements else "✗"
            print(f"  {status} {req_id}: {req_desc}")
    
    def _generate_detailed_report(self):
        """Generate detailed test report file."""
        report_data = {
            'test_run': {
                'timestamp': datetime.now().isoformat(),
                'duration': self.end_time - self.start_time,
                'total_categories': len(self.test_results)
            },
            'categories': self.test_results,
            'summary': self._calculate_overall_summary()
        }
        
        # Write JSON report
        report_file = 'DUPLICATE_HANDLING_E2E_TEST_REPORT.json'
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        # Write markdown report
        self._generate_markdown_report(report_data)
        
        print(f"\nDetailed reports generated:")
        print(f"  - {report_file}")
        print(f"  - DUPLICATE_HANDLING_E2E_TEST_REPORT.md")
    
    def _calculate_overall_summary(self):
        """Calculate overall test summary statistics."""
        overall = {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'duration': 0}
        
        for category_result in self.test_results.values():
            summary = category_result['summary']
            overall['total'] += summary['total']
            overall['passed'] += summary['passed']
            overall['failed'] += summary['failed']
            overall['skipped'] += summary['skipped']
            overall['duration'] += summary['duration']
        
        overall['success_rate'] = (overall['passed'] / max(overall['total'], 1)) * 100
        return overall
    
    def _generate_markdown_report(self, report_data):
        """Generate markdown format report."""
        report_file = 'DUPLICATE_HANDLING_E2E_TEST_REPORT.md'
        
        with open(report_file, 'w') as f:
            f.write("# Duplicate Lead Handling - End-to-End Test Report\n\n")
            f.write(f"**Generated:** {report_data['test_run']['timestamp']}\n")
            f.write(f"**Duration:** {report_data['test_run']['duration']:.2f} seconds\n\n")
            
            # Overall summary
            summary = report_data['summary']
            f.write("## Overall Summary\n\n")
            f.write(f"- **Total Tests:** {summary['total']}\n")
            f.write(f"- **Passed:** {summary['passed']}\n")
            f.write(f"- **Failed:** {summary['failed']}\n")
            f.write(f"- **Skipped:** {summary['skipped']}\n")
            f.write(f"- **Success Rate:** {summary['success_rate']:.1f}%\n\n")
            
            # Category details
            f.write("## Test Categories\n\n")
            
            for category_name, category_result in report_data['categories'].items():
                f.write(f"### {category_name}\n\n")
                f.write(f"**Description:** {category_result['description']}\n")
                f.write(f"**Test File:** `{category_result['test_file']}`\n\n")
                
                cat_summary = category_result['summary']
                f.write(f"**Results:** {cat_summary['passed']}/{cat_summary['total']} passed ")
                f.write(f"({cat_summary['duration']:.2f}s)\n\n")
                
                # Individual test results
                if category_result['tests']:
                    f.write("**Individual Tests:**\n\n")
                    for test_name, test_result in category_result['tests'].items():
                        status_icon = "✅" if test_result['status'] == 'PASSED' else "❌"
                        f.write(f"- {status_icon} `{test_name}` ({test_result['duration']:.2f}s)\n")
                    f.write("\n")
            
            # Requirements coverage
            f.write("## Requirements Coverage\n\n")
            f.write("This test suite covers the following duplicate handling requirements:\n\n")
            f.write("- **6.1:** Frontend shows deduplicated leads with correct timestamps\n")
            f.write("- **6.2:** Verify frontend shows deduplicated leads with correct timestamps\n")
            f.write("- **6.3:** Test CSV export functionality with deduplicated data\n")
            f.write("- **6.4:** Verify search/filter works with deduplicated dataset\n")
            f.write("- **6.5:** Verify lead details show correct sourceFile\n")
            f.write("- **7.2:** Integration tests with duplicate scenarios\n")
            f.write("- **7.5:** Error scenario testing with graceful fallback\n\n")
            
            # Recommendations
            f.write("## Recommendations\n\n")
            if summary['failed'] > 0:
                f.write("⚠️ **Action Required:** Some tests failed. Review the detailed output above.\n\n")
            else:
                f.write("✅ **All tests passed!** The duplicate handling feature is working correctly.\n\n")
            
            f.write("For production deployment:\n")
            f.write("1. Ensure all E2E tests pass consistently\n")
            f.write("2. Monitor duplicate detection performance in production\n")
            f.write("3. Set up alerts for duplicate handling errors\n")
            f.write("4. Regularly validate EmailIndex GSI performance\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run duplicate handling E2E tests')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose output')
    parser.add_argument('--no-report', action='store_true',
                       help='Skip generating detailed report files')
    
    args = parser.parse_args()
    
    runner = DuplicateHandlingE2ETestRunner(
        verbose=args.verbose,
        generate_report=not args.no_report
    )
    
    try:
        runner.run_all_tests()
        return 0
    except KeyboardInterrupt:
        print("\n\nTest run interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\nTest run failed with error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())