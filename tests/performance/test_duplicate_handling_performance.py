"""
Performance tests specifically for duplicate lead handling functionality.

Tests performance impact of duplicate detection and handling under various scenarios.
"""

import pytest
import json
import os
import sys
import time
import boto3
from moto import mock_aws
from unittest.mock import patch, Mock
import pandas as pd
from io import BytesIO
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))


class TestDuplicateHandlingPerformance:
    """Performance tests for duplicate lead handling."""
    
    @pytest.fixture
    def aws_environment(self):
        """Set up AWS environment for performance testing."""
        with mock_aws():
            # Create DynamoDB table with EmailIndex GSI
            dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
            table = dynamodb.create_table(
                TableName='test-leads-perf',
                KeySchema=[
                    {'AttributeName': 'leadId', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'leadId', 'AttributeType': 'S'},
                    {'AttributeName': 'email', 'AttributeType': 'S'},
                    {'AttributeName': 'company', 'AttributeType': 'S'},
                    {'AttributeName': 'createdAt', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'EmailIndex',
                        'KeySchema': [
                            {'AttributeName': 'email', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    },
                    {
                        'IndexName': 'CompanyIndex',
                        'KeySchema': [
                            {'AttributeName': 'company', 'KeyType': 'HASH'},
                            {'AttributeName': 'createdAt', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            yield {
                'dynamodb_table': table
            }
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context for performance testing."""
        context = Mock()
        context.aws_request_id = 'perf-test-request'
        context.function_name = 'test-function'
        context.memory_limit_in_mb = 512
        context.remaining_time_in_millis = lambda: 60000  # 1 minute
        return context
    
    def test_email_normalization_performance(self):
        """Test performance of email normalization with large datasets."""
        from email_utils import EmailNormalizer
        
        # Create test dataset with various email formats
        test_emails = []
        for i in range(10000):
            if i % 4 == 0:
                test_emails.append(f'  USER{i}@EXAMPLE.COM  ')  # Whitespace + uppercase
            elif i % 4 == 1:
                test_emails.append(f'user{i}@example.com')  # Normal
            elif i % 4 == 2:
                test_emails.append(f'User{i}@Example.Com')  # Mixed case
            else:
                test_emails.append('')  # Empty
        
        # Measure normalization performance
        start_time = time.time()
        
        normalized_emails = []
        for email in test_emails:
            normalized = EmailNormalizer.normalize_email(email)
            normalized_emails.append(normalized)
        
        normalization_time = time.time() - start_time
        
        # Performance assertions
        assert normalization_time < 1.0  # Should normalize 10k emails in under 1 second
        assert len(normalized_emails) == 10000
        
        # Verify normalization correctness
        assert normalized_emails[0] == 'user0@example.com'  # Whitespace + case normalized
        assert normalized_emails[1] == 'user1@example.com'  # Already normal
        assert normalized_emails[2] == 'user2@example.com'  # Case normalized
        assert normalized_emails[3] == 'N/A'  # Empty normalized
        
        print(f"Email normalization: {len(test_emails)} emails in {normalization_time:.3f}s")
        print(f"Rate: {len(test_emails)/normalization_time:.0f} emails/second")
    
    def test_duplicate_detection_performance(self, aws_environment, lambda_context):
        """Test performance of duplicate detection with various batch sizes."""
        from dynamodb_utils import DynamoDBUtils
        
        db_utils = DynamoDBUtils('test-leads-perf')
        
        # Pre-populate table with existing leads
        existing_leads = []
        for i in range(1000):
            lead = {
                'leadId': f'existing-{i}',
                'firstName': f'User',
                'lastName': f'{i}',
                'email': f'user{i}@company.com',
                'company': f'Company{i % 100}',  # 100 different companies
                'title': f'Title{i % 50}',  # 50 different titles
                'phone': f'+1-555-{i:04d}',
                'remarks': f'Existing lead {i}',
                'sourceFile': 'initial_load.csv',
                'createdAt': '2024-01-15T10:00:00Z',
                'updatedAt': '2024-01-15T10:00:00Z'
            }
            existing_leads.append(lead)
        
        # Batch insert existing leads
        table = aws_environment['dynamodb_table']
        with table.batch_writer() as batch:
            for lead in existing_leads:
                batch.put_item(Item=lead)
        
        # Test different batch sizes with varying duplicate percentages
        batch_sizes = [10, 25, 50, 100]
        duplicate_percentages = [0.0, 0.25, 0.5, 0.75, 1.0]
        
        performance_results = []
        
        for batch_size in batch_sizes:
            for dup_pct in duplicate_percentages:
                # Create test batch
                test_batch = self._create_test_batch(batch_size, dup_pct, existing_leads)
                
                # Measure duplicate detection performance
                start_time = time.time()
                
                try:
                    result = db_utils.batch_upsert_leads(test_batch, 'performance_test.csv')
                    detection_time = time.time() - start_time
                    
                    performance_results.append({
                        'batch_size': batch_size,
                        'duplicate_percentage': dup_pct,
                        'processing_time': detection_time,
                        'duplicates_found': len(result.get('updated_leads', [])),
                        'new_leads': len(result.get('created_leads', [])),
                        'success': True
                    })
                    
                except Exception as e:
                    performance_results.append({
                        'batch_size': batch_size,
                        'duplicate_percentage': dup_pct,
                        'processing_time': time.time() - start_time,
                        'error': str(e),
                        'success': False
                    })
        
        # Analyze performance results
        successful_results = [r for r in performance_results if r['success']]
        
        # Performance assertions
        assert len(successful_results) > 0, "No successful duplicate detection operations"
        
        # Check that processing time scales reasonably with batch size
        max_time_per_lead = 0.1  # 100ms per lead maximum
        for result in successful_results:
            time_per_lead = result['processing_time'] / result['batch_size']
            assert time_per_lead < max_time_per_lead, f"Processing too slow: {time_per_lead:.3f}s per lead"
        
        # Print performance summary
        print("\nDuplicate Detection Performance Results:")
        print("Batch Size | Dup % | Time (s) | Time/Lead (ms) | Duplicates | New Leads")
        print("-" * 75)
        
        for result in successful_results:
            if result['success']:
                time_per_lead_ms = (result['processing_time'] / result['batch_size']) * 1000
                print(f"{result['batch_size']:10d} | {result['duplicate_percentage']:5.1%} | "
                      f"{result['processing_time']:8.3f} | {time_per_lead_ms:13.1f} | "
                      f"{result['duplicates_found']:10d} | {result['new_leads']:9d}")
    
    def test_concurrent_duplicate_detection(self, aws_environment, lambda_context):
        """Test performance under concurrent duplicate detection scenarios."""
        from dynamodb_utils import DynamoDBUtils
        
        db_utils = DynamoDBUtils('test-leads-perf')
        
        # Pre-populate with base leads
        base_leads = []
        for i in range(500):
            lead = {
                'leadId': f'base-{i}',
                'firstName': f'BaseUser',
                'lastName': f'{i}',
                'email': f'baseuser{i}@company.com',
                'company': f'BaseCompany{i % 50}',
                'title': f'BaseTitle{i % 25}',
                'phone': f'+1-555-{i:04d}',
                'remarks': f'Base lead {i}',
                'sourceFile': 'base_load.csv',
                'createdAt': '2024-01-10T10:00:00Z',
                'updatedAt': '2024-01-10T10:00:00Z'
            }
            base_leads.append(lead)
        
        table = aws_environment['dynamodb_table']
        with table.batch_writer() as batch:
            for lead in base_leads:
                batch.put_item(Item=lead)
        
        # Create multiple concurrent batches
        concurrent_batches = []
        for batch_num in range(5):  # 5 concurrent batches
            batch = self._create_test_batch(20, 0.6, base_leads)  # 60% duplicates
            concurrent_batches.append((batch_num, batch))
        
        # Process batches concurrently
        start_time = time.time()
        results = []
        
        def process_batch(batch_info):
            batch_num, batch_data = batch_info
            batch_start = time.time()
            try:
                result = db_utils.batch_upsert_leads(batch_data, f'concurrent_test_{batch_num}.csv')
                batch_time = time.time() - batch_start
                return {
                    'batch_num': batch_num,
                    'processing_time': batch_time,
                    'duplicates_found': len(result.get('updated_leads', [])),
                    'new_leads': len(result.get('created_leads', [])),
                    'success': True
                }
            except Exception as e:
                return {
                    'batch_num': batch_num,
                    'processing_time': time.time() - batch_start,
                    'error': str(e),
                    'success': False
                }
        
        # Use ThreadPoolExecutor to simulate concurrent Lambda invocations
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_batch = {executor.submit(process_batch, batch): batch for batch in concurrent_batches}
            
            for future in as_completed(future_to_batch):
                result = future.result()
                results.append(result)
        
        total_time = time.time() - start_time
        
        # Performance assertions
        successful_results = [r for r in results if r['success']]
        assert len(successful_results) >= 4, "Most concurrent operations should succeed"
        
        # Check that concurrent processing doesn't cause excessive delays
        avg_batch_time = statistics.mean([r['processing_time'] for r in successful_results])
        assert avg_batch_time < 5.0, f"Average batch time too high: {avg_batch_time:.3f}s"
        
        # Check for reasonable total throughput
        total_leads_processed = sum([20 for r in successful_results])  # 20 leads per successful batch
        throughput = total_leads_processed / total_time
        assert throughput > 10, f"Throughput too low: {throughput:.1f} leads/second"
        
        print(f"\nConcurrent Processing Results:")
        print(f"Total time: {total_time:.3f}s")
        print(f"Average batch time: {avg_batch_time:.3f}s")
        print(f"Throughput: {throughput:.1f} leads/second")
        print(f"Successful batches: {len(successful_results)}/5")
    
    def test_memory_usage_with_large_batches(self, aws_environment, lambda_context):
        """Test memory usage patterns with large batches containing duplicates."""
        import psutil
        import gc
        
        from dynamodb_utils import DynamoDBUtils
        
        db_utils = DynamoDBUtils('test-leads-perf')
        
        # Pre-populate with leads for duplicate detection
        base_leads = []
        for i in range(2000):
            lead = {
                'leadId': f'memory-test-{i}',
                'firstName': f'MemUser',
                'lastName': f'{i}',
                'email': f'memuser{i}@company.com',
                'company': f'MemCompany{i % 100}',
                'title': f'MemTitle{i % 50}',
                'phone': f'+1-555-{i:04d}',
                'remarks': f'Memory test lead {i}',
                'sourceFile': 'memory_base.csv',
                'createdAt': '2024-01-05T10:00:00Z',
                'updatedAt': '2024-01-05T10:00:00Z'
            }
            base_leads.append(lead)
        
        table = aws_environment['dynamodb_table']
        with table.batch_writer() as batch:
            for lead in base_leads:
                batch.put_item(Item=lead)
        
        # Test different batch sizes and measure memory usage
        batch_sizes = [50, 100, 200, 500]
        memory_results = []
        
        for batch_size in batch_sizes:
            # Force garbage collection before test
            gc.collect()
            
            # Get initial memory usage
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Create large batch with duplicates
            test_batch = self._create_test_batch(batch_size, 0.7, base_leads)
            
            # Process batch and measure peak memory
            peak_memory = initial_memory
            
            try:
                result = db_utils.batch_upsert_leads(test_batch, f'memory_test_{batch_size}.csv')
                
                # Measure memory after processing
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                memory_results.append({
                    'batch_size': batch_size,
                    'initial_memory_mb': initial_memory,
                    'final_memory_mb': final_memory,
                    'memory_increase_mb': memory_increase,
                    'memory_per_lead_kb': (memory_increase * 1024) / batch_size,
                    'duplicates_processed': len(result.get('updated_leads', [])),
                    'success': True
                })
                
            except Exception as e:
                memory_results.append({
                    'batch_size': batch_size,
                    'error': str(e),
                    'success': False
                })
            
            # Clean up for next test
            gc.collect()
        
        # Memory usage assertions
        successful_results = [r for r in memory_results if r['success']]
        assert len(successful_results) > 0, "No successful memory tests"
        
        # Check that memory usage per lead is reasonable
        max_memory_per_lead_kb = 50  # 50KB per lead maximum
        for result in successful_results:
            assert result['memory_per_lead_kb'] < max_memory_per_lead_kb, \
                f"Memory usage too high: {result['memory_per_lead_kb']:.1f}KB per lead"
        
        # Check that memory usage scales reasonably
        if len(successful_results) >= 2:
            memory_increases = [r['memory_increase_mb'] for r in successful_results]
            # Memory should not increase exponentially
            max_increase = max(memory_increases)
            min_increase = min(memory_increases)
            assert max_increase / min_increase < 20, "Memory usage scaling poorly"
        
        print("\nMemory Usage Results:")
        print("Batch Size | Initial (MB) | Final (MB) | Increase (MB) | Per Lead (KB) | Duplicates")
        print("-" * 85)
        
        for result in successful_results:
            print(f"{result['batch_size']:10d} | {result['initial_memory_mb']:11.1f} | "
                  f"{result['final_memory_mb']:9.1f} | {result['memory_increase_mb']:11.1f} | "
                  f"{result['memory_per_lead_kb']:11.1f} | {result['duplicates_processed']:10d}")
    
    def test_gsi_query_performance(self, aws_environment):
        """Test EmailIndex GSI query performance under load."""
        from dynamodb_utils import DynamoDBUtils
        
        db_utils = DynamoDBUtils('test-leads-perf')
        
        # Pre-populate table with many leads
        test_leads = []
        for i in range(5000):
            lead = {
                'leadId': f'gsi-test-{i}',
                'firstName': f'GSIUser',
                'lastName': f'{i}',
                'email': f'gsiuser{i}@domain{i % 100}.com',  # 100 different domains
                'company': f'GSICompany{i % 200}',  # 200 different companies
                'title': f'GSITitle{i % 75}',  # 75 different titles
                'phone': f'+1-555-{i:04d}',
                'remarks': f'GSI test lead {i}',
                'sourceFile': 'gsi_test.csv',
                'createdAt': f'2024-01-{(i % 30) + 1:02d}T10:00:00Z',  # Spread across month
                'updatedAt': f'2024-01-{(i % 30) + 1:02d}T10:00:00Z'
            }
            test_leads.append(lead)
        
        # Batch insert leads
        table = aws_environment['dynamodb_table']
        with table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test GSI query performance
        query_times = []
        
        # Test 100 random email queries
        import random
        test_emails = [f'gsiuser{random.randint(0, 4999)}@domain{random.randint(0, 99)}.com' 
                      for _ in range(100)]
        
        for email in test_emails:
            start_time = time.time()
            
            try:
                result = db_utils.find_lead_by_email(email)
                query_time = time.time() - start_time
                query_times.append(query_time)
                
            except Exception as e:
                print(f"Query failed for {email}: {e}")
        
        # Performance assertions
        assert len(query_times) > 0, "No successful GSI queries"
        
        avg_query_time = statistics.mean(query_times)
        max_query_time = max(query_times)
        min_query_time = min(query_times)
        
        # GSI queries should be fast
        assert avg_query_time < 0.1, f"Average GSI query too slow: {avg_query_time:.3f}s"
        assert max_query_time < 0.5, f"Maximum GSI query too slow: {max_query_time:.3f}s"
        
        print(f"\nGSI Query Performance (100 queries):")
        print(f"Average: {avg_query_time*1000:.1f}ms")
        print(f"Minimum: {min_query_time*1000:.1f}ms")
        print(f"Maximum: {max_query_time*1000:.1f}ms")
        print(f"95th percentile: {sorted(query_times)[94]*1000:.1f}ms")
    
    def _create_test_batch(self, batch_size, duplicate_percentage, existing_leads):
        """Create a test batch with specified duplicate percentage."""
        duplicate_count = int(batch_size * duplicate_percentage)
        new_count = batch_size - duplicate_count
        
        batch = []
        
        # Add duplicates (variations of existing leads)
        for i in range(duplicate_count):
            if existing_leads:
                base_lead = existing_leads[i % len(existing_leads)]
                # Create variation of existing lead
                duplicate_lead = {
                    'firstName': base_lead['firstName'],
                    'lastName': base_lead['lastName'],
                    'email': base_lead['email'],  # Same email = duplicate
                    'company': base_lead['company'],
                    'title': f"Updated {base_lead['title']}",  # Updated title
                    'phone': base_lead['phone'],
                    'remarks': f"Updated {base_lead['remarks']}"  # Updated remarks
                }
                batch.append(duplicate_lead)
        
        # Add new leads
        for i in range(new_count):
            new_lead = {
                'firstName': f'NewUser',
                'lastName': f'{i + len(existing_leads)}',
                'email': f'newuser{i + len(existing_leads)}@newcompany.com',
                'company': f'NewCompany{i}',
                'title': f'NewTitle{i}',
                'phone': f'+1-555-{(i + len(existing_leads)):04d}',
                'remarks': f'New lead {i}'
            }
            batch.append(new_lead)
        
        return batch


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])