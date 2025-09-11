#!/usr/bin/env python3
"""
Validation script for duplicate lead handling integration.

This script validates that all components required for duplicate handling
are properly integrated and configured.
"""

import os
import sys
import json
import importlib.util
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class DuplicateHandlingValidator:
    """Validator for duplicate handling integration."""
    
    def __init__(self):
        self.validation_results = []
        self.errors = []
        self.warnings = []
    
    def validate_all(self):
        """Run all validation checks."""
        print("=" * 70)
        print("DUPLICATE LEAD HANDLING - INTEGRATION VALIDATION")
        print("=" * 70)
        
        validation_checks = [
            self.validate_shared_utilities,
            self.validate_email_utils,
            self.validate_dynamodb_utils,
            self.validate_deepseek_caller_integration,
            self.validate_test_coverage,
            self.validate_infrastructure_requirements,
            self.validate_error_handling
        ]
        
        for check in validation_checks:
            try:
                check()
            except Exception as e:
                self.errors.append(f"Validation check failed: {check.__name__}: {e}")
        
        self._generate_validation_report()
    
    def validate_shared_utilities(self):
        """Validate shared utility modules exist and are importable."""
        print("\n1. Validating Shared Utilities...")
        
        shared_modules = [
            'lambda/shared/email_utils.py',
            'lambda/shared/dynamodb_utils.py',
            'lambda/shared/validation.py',
            'lambda/shared/error_handling.py'
        ]
        
        for module_path in shared_modules:
            full_path = project_root / module_path
            if full_path.exists():
                print(f"   ✓ {module_path} exists")
                
                # Try to import the module
                try:
                    spec = importlib.util.spec_from_file_location("test_module", full_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    print(f"   ✓ {module_path} imports successfully")
                except Exception as e:
                    self.errors.append(f"Failed to import {module_path}: {e}")
                    print(f"   ✗ {module_path} import failed: {e}")
            else:
                self.errors.append(f"Missing required module: {module_path}")
                print(f"   ✗ {module_path} missing")
    
    def validate_email_utils(self):
        """Validate email utilities implementation."""
        print("\n2. Validating Email Utilities...")
        
        email_utils_path = project_root / 'lambda/shared/email_utils.py'
        if not email_utils_path.exists():
            self.errors.append("email_utils.py not found")
            return
        
        # Check for required classes and methods
        with open(email_utils_path, 'r') as f:
            content = f.read()
        
        required_components = [
            'class EmailNormalizer',
            'def normalize_email',
            'def is_valid_email_format'
        ]
        
        for component in required_components:
            if component in content:
                print(f"   ✓ {component} found")
            else:
                self.errors.append(f"Missing component in email_utils.py: {component}")
                print(f"   ✗ {component} missing")
        
        # Test email normalization functionality
        try:
            sys.path.append(str(project_root / 'lambda/shared'))
            from email_utils import EmailNormalizer
            
            # Test cases
            test_cases = [
                ('  JOHN@EXAMPLE.COM  ', 'john@example.com'),
                ('Jane.Doe@Company.Com', 'jane.doe@company.com'),
                ('', 'N/A'),
                ('N/A', 'N/A'),
                (None, 'N/A')
            ]
            
            for input_email, expected in test_cases:
                try:
                    result = EmailNormalizer.normalize_email(input_email)
                    if result == expected:
                        print(f"   ✓ Email normalization test passed: '{input_email}' -> '{result}'")
                    else:
                        self.errors.append(f"Email normalization failed: '{input_email}' -> '{result}' (expected '{expected}')")
                        print(f"   ✗ Email normalization test failed: '{input_email}' -> '{result}' (expected '{expected}')")
                except Exception as e:
                    self.errors.append(f"Email normalization error for '{input_email}': {e}")
                    print(f"   ✗ Email normalization error for '{input_email}': {e}")
        
        except ImportError as e:
            self.errors.append(f"Cannot import EmailNormalizer: {e}")
            print(f"   ✗ Cannot import EmailNormalizer: {e}")
    
    def validate_dynamodb_utils(self):
        """Validate DynamoDB utilities for duplicate handling."""
        print("\n3. Validating DynamoDB Utilities...")
        
        dynamodb_utils_path = project_root / 'lambda/shared/dynamodb_utils.py'
        if not dynamodb_utils_path.exists():
            self.errors.append("dynamodb_utils.py not found")
            return
        
        # Check for required methods
        with open(dynamodb_utils_path, 'r') as f:
            content = f.read()
        
        required_methods = [
            'def find_lead_by_email',
            'def upsert_lead',
            'def batch_upsert_leads'
        ]
        
        for method in required_methods:
            if method in content:
                print(f"   ✓ {method} found")
            else:
                self.errors.append(f"Missing method in dynamodb_utils.py: {method}")
                print(f"   ✗ {method} missing")
        
        # Check for EmailIndex GSI usage
        if 'EmailIndex' in content:
            print(f"   ✓ EmailIndex GSI usage found")
        else:
            self.warnings.append("EmailIndex GSI usage not found in dynamodb_utils.py")
            print(f"   ⚠ EmailIndex GSI usage not found")
        
        # Check for duplicate handling logic
        duplicate_keywords = ['duplicate', 'upsert', 'find_lead_by_email']
        found_keywords = [kw for kw in duplicate_keywords if kw in content]
        
        if len(found_keywords) >= 2:
            print(f"   ✓ Duplicate handling logic found ({', '.join(found_keywords)})")
        else:
            self.warnings.append("Limited duplicate handling logic found in dynamodb_utils.py")
            print(f"   ⚠ Limited duplicate handling logic found")
    
    def validate_deepseek_caller_integration(self):
        """Validate DeepSeek caller integration with duplicate handling."""
        print("\n4. Validating DeepSeek Caller Integration...")
        
        deepseek_path = project_root / 'lambda/deepseek-caller/lambda_function.py'
        if not deepseek_path.exists():
            self.errors.append("DeepSeek caller lambda_function.py not found")
            return
        
        with open(deepseek_path, 'r') as f:
            content = f.read()
        
        # Check for duplicate handling integration
        integration_indicators = [
            'batch_upsert_leads',
            'upsert_lead',
            'duplicate',
            'EmailNormalizer'
        ]
        
        found_indicators = [ind for ind in integration_indicators if ind in content]
        
        if len(found_indicators) >= 2:
            print(f"   ✓ Duplicate handling integration found ({', '.join(found_indicators)})")
        else:
            self.warnings.append("Limited duplicate handling integration in DeepSeek caller")
            print(f"   ⚠ Limited duplicate handling integration found")
        
        # Check for error handling
        error_handling_patterns = [
            'try:',
            'except',
            'ClientError',
            'fallback'
        ]
        
        found_error_handling = [pattern for pattern in error_handling_patterns if pattern in content]
        
        if len(found_error_handling) >= 2:
            print(f"   ✓ Error handling patterns found")
        else:
            self.warnings.append("Limited error handling in DeepSeek caller")
            print(f"   ⚠ Limited error handling patterns found")
    
    def validate_test_coverage(self):
        """Validate test coverage for duplicate handling."""
        print("\n5. Validating Test Coverage...")
        
        test_files = [
            'tests/unit/test_email_utils.py',
            'tests/unit/test_dynamodb_duplicate_utils.py',
            'tests/integration/test_duplicate_detection_integration.py',
            'tests/integration/test_duplicate_handling_workflow.py',
            'tests/e2e/test_duplicate_handling_e2e.py',
            'tests/performance/test_duplicate_handling_performance.py'
        ]
        
        existing_tests = []
        missing_tests = []
        
        for test_file in test_files:
            test_path = project_root / test_file
            if test_path.exists():
                existing_tests.append(test_file)
                print(f"   ✓ {test_file} exists")
                
                # Check test content
                with open(test_path, 'r') as f:
                    test_content = f.read()
                
                if 'duplicate' in test_content.lower():
                    print(f"   ✓ {test_file} contains duplicate-related tests")
                else:
                    self.warnings.append(f"{test_file} may not contain duplicate-specific tests")
                    print(f"   ⚠ {test_file} may not contain duplicate-specific tests")
            else:
                missing_tests.append(test_file)
                print(f"   ✗ {test_file} missing")
        
        if len(existing_tests) >= 4:
            print(f"   ✓ Good test coverage: {len(existing_tests)}/{len(test_files)} test files exist")
        else:
            self.warnings.append(f"Limited test coverage: {len(existing_tests)}/{len(test_files)} test files exist")
            print(f"   ⚠ Limited test coverage: {len(existing_tests)}/{len(test_files)} test files exist")
    
    def validate_infrastructure_requirements(self):
        """Validate infrastructure requirements for duplicate handling."""
        print("\n6. Validating Infrastructure Requirements...")
        
        # Check CloudFormation templates
        storage_template = project_root / 'infrastructure/storage.yaml'
        if storage_template.exists():
            with open(storage_template, 'r') as f:
                storage_content = f.read()
            
            if 'EmailIndex' in storage_content:
                print(f"   ✓ EmailIndex GSI found in storage template")
            else:
                self.errors.append("EmailIndex GSI not found in storage.yaml")
                print(f"   ✗ EmailIndex GSI not found in storage template")
        else:
            self.errors.append("storage.yaml template not found")
            print(f"   ✗ storage.yaml template not found")
        
        # Check Lambda template for proper IAM permissions
        lambda_template = project_root / 'infrastructure/lambda.yaml'
        if lambda_template.exists():
            with open(lambda_template, 'r') as f:
                lambda_content = f.read()
            
            # Check for DynamoDB permissions
            if 'dynamodb:Query' in lambda_content and 'dynamodb:UpdateItem' in lambda_content:
                print(f"   ✓ Required DynamoDB permissions found in Lambda template")
            else:
                self.warnings.append("May be missing required DynamoDB permissions in Lambda template")
                print(f"   ⚠ May be missing required DynamoDB permissions")
        else:
            self.warnings.append("lambda.yaml template not found")
            print(f"   ⚠ lambda.yaml template not found")
    
    def validate_error_handling(self):
        """Validate error handling and fallback mechanisms."""
        print("\n7. Validating Error Handling...")
        
        # Check shared error handling module
        error_handling_path = project_root / 'lambda/shared/error_handling.py'
        if error_handling_path.exists():
            with open(error_handling_path, 'r') as f:
                error_content = f.read()
            
            error_patterns = [
                'ClientError',
                'ResourceNotFoundException',
                'fallback',
                'retry'
            ]
            
            found_patterns = [pattern for pattern in error_patterns if pattern in error_content]
            
            if len(found_patterns) >= 2:
                print(f"   ✓ Error handling patterns found ({', '.join(found_patterns)})")
            else:
                self.warnings.append("Limited error handling patterns in error_handling.py")
                print(f"   ⚠ Limited error handling patterns found")
        else:
            self.warnings.append("error_handling.py not found")
            print(f"   ⚠ error_handling.py not found")
        
        # Check for logging in duplicate handling components
        components_to_check = [
            'lambda/shared/dynamodb_utils.py',
            'lambda/deepseek-caller/lambda_function.py'
        ]
        
        for component in components_to_check:
            component_path = project_root / component
            if component_path.exists():
                with open(component_path, 'r') as f:
                    content = f.read()
                
                if 'logger' in content or 'logging' in content:
                    print(f"   ✓ Logging found in {component}")
                else:
                    self.warnings.append(f"No logging found in {component}")
                    print(f"   ⚠ No logging found in {component}")
    
    def _generate_validation_report(self):
        """Generate validation summary report."""
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        
        total_checks = 7
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        
        print(f"\nValidation Results:")
        print(f"  Total Checks: {total_checks}")
        print(f"  Errors: {error_count}")
        print(f"  Warnings: {warning_count}")
        
        if error_count == 0:
            print(f"\n✅ VALIDATION PASSED - Duplicate handling integration is ready!")
        else:
            print(f"\n❌ VALIDATION FAILED - {error_count} error(s) found")
        
        if warning_count > 0:
            print(f"\n⚠️  {warning_count} warning(s) - Review recommended")
        
        # Print detailed errors and warnings
        if self.errors:
            print(f"\nERRORS:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
        
        if self.warnings:
            print(f"\nWARNINGS:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        # Generate recommendations
        print(f"\nRECOMMENDATIONS:")
        if error_count > 0:
            print(f"  1. Fix all errors before proceeding with duplicate handling implementation")
            print(f"  2. Run the validation script again after fixes")
        
        if warning_count > 0:
            print(f"  3. Review and address warnings for optimal implementation")
        
        if error_count == 0:
            print(f"  4. Run the E2E test suite: python tests/run_duplicate_handling_e2e_tests.py")
            print(f"  5. Deploy and test in a staging environment")
        
        # Save validation report
        report_data = {
            'validation_timestamp': str(Path(__file__).stat().st_mtime),
            'total_checks': total_checks,
            'errors': self.errors,
            'warnings': self.warnings,
            'status': 'PASSED' if error_count == 0 else 'FAILED'
        }
        
        with open('DUPLICATE_HANDLING_VALIDATION_REPORT.json', 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\nValidation report saved: DUPLICATE_HANDLING_VALIDATION_REPORT.json")


def main():
    """Main entry point."""
    validator = DuplicateHandlingValidator()
    validator.validate_all()
    
    # Return appropriate exit code
    return 0 if len(validator.errors) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())