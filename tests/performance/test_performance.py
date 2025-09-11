"""
Performance tests for the lead management system.

Tests system performance under various load conditions including
large file processing, concurrent operations, and database performance.
"""

import pytest
import time
import json
import os
import sys
import boto3
from moto import mock_aws
from unittest.mock import patch, Mock
import pandas as pd
from io import BytesIO
import concurrent.futures
import threading
from datetime import datetime, timedelta

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

class TestPerformance:
    """Performance test cases."""
    
    @pytest.fixture
    def performance_aws_environment(self):
        """Set up AWS environment optimized for performance testing."""
        with mock_aws():
            # Create S3 client
            s3_client = boto3.client('s3', region_name='ap-southeast-1')
            upload_bucket = 'perf-test-bucket'
            s3_client.create_bucket(
                Bucket=upload_bucket,
                CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
            )
            
            # Create DynamoDB table with higher capacity for performance testing
            dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
            table = dynamodb.create_table(
                TableName='perf-test-leads',
                KeySchema=[
                    {'AttributeName': 'leadId', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'leadId', 'AttributeType': 'S'},
                    {'AttributeName': 'company', 'AttributeType': 'S'},
                    {'AttributeName': 'email', 'AttributeType': 'S'},
                    {'AttributeName': 'createdAt', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'CompanyIndex',
                        'KeySchema': [
                            {'AttributeName': 'company', 'KeyType': 'HASH'},
                            {'AttributeName': 'createdAt', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    },
                    {
                        'IndexName': 'EmailIndex',
                        'KeySchema': [
                            {'AttributeName': 'email', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            yield {
                's3_client': s3_client,
                'upload_bucket': upload_bucket,
                'dynamodb_table': table
            }
    
    def generate_large_csv_data(self, num_rows=10000):
        """Generate large CSV data for performance testing."""
        companies = ['Google', 'Microsoft', 'Amazon', 'Apple', 'Meta', 'Netflix', 'Tesla', 'Salesforce']
        titles = ['Engineer', 'Manager', 'Director', 'VP', 'Analyst', 'Specialist', 'Consultant']
        
        rows = []
        for i in range(num_rows):
            company = companies[i % len(companies)]
            title = titles[i % len(titles)]
            rows.append(f"User{i:05d},Test{i:05d},{title},{company},user{i:05d}@{company.lower()}.com,+1-555-{i:04d},Test lead {i}")
        
        header = "firstName,lastName,title,company,email,phone,remarks"
        return header + "\n" + "\n".join(rows)
    
    def generate_large_excel_data(self, num_rows=10000):
        """Generate large Excel data for performance testing."""
        companies = ['Google', 'Microsoft', 'Amazon', 'Apple', 'Meta', 'Netflix', 'Tesla', 'Salesforce']
        titles = ['Engineer', 'Manager', 'Director', 'VP', 'Analyst', 'Specialist', 'Consultant']
        
        data = {
            'First Name': [f'User{i:05d}' for i in range(num_rows)],
            'Last Name': [f'Test{i:05d}' for i in range(num_rows)],
            'Job Title': [titles[i % len(titles)] for i in range(num_rows)],
            'Company': [companies[i % len(companies)] for i in range(num_rows)],
            'Email': [f'user{i:05d}@{companies[i % len(companies)].lower()}.com' for i in range(num_rows)],
            'Phone': [f'+1-555-{i:04d}' for i in range(num_rows)],
            'Notes': [f'Test lead {i}' for i in range(num_rows)]
        }
        
        df = pd.DataFrame(data)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False)
        return excel_buffer.getvalue()
    
    @pytest.mark.performance
    def test_large_csv_file_processing_performance(self, performance_aws_environment):
        """Test performance with large CSV files (10k+ rows)."""
        s3_client = performance_aws_environment['s3_client']
        upload_bucket = performance_aws_environment['upload_bucket']
        
        # Generate large CSV (10k rows)
        large_csv_data = self.generate_large_csv_data(10000)
        file_size = len(large_csv_data.encode('utf-8'))
        
        print(f"Testing with CSV file: {file_size / (1024*1024):.2f} MB, 10,000 rows")
        
        # Upload to S3
        file_key = 'uploads/large_test.csv'
        
        start_time = time.time()
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=file_key,
            Body=large_csv_data.encode('utf-8'),
            ContentType='text/csv'
        )
        upload_time = time.time() - start_time
        
        print(f"S3 upload time: {upload_time:.2f} seconds")
        
        # Test file processing
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        
        with patch.dict(os.environ, {
            'PROCESSING_QUEUE_URL': 'test-queue-url'
        }):
            from lambda_function import FileProcessor, download_file_from_s3
            
            # Test file download performance
            start_time = time.time()
            with patch('lambda_function.s3_client', s3_client):
                file_content = download_file_from_s3(upload_bucket, file_key)
            download_time = time.time() - start_time
            
            print(f"S3 download time: {download_time:.2f} seconds")
            
            # Test CSV parsing performance
            start_time = time.time()
            leads = FileProcessor.read_csv_file(file_content)
            parse_time = time.time() - start_time
            
            print(f"CSV parsing time: {parse_time:.2f} seconds")
            print(f"Parsed {len(leads)} leads")
            
            assert len(leads) == 10000
            
            # Performance assertions
            assert upload_time < 5.0, f"S3 upload too slow: {upload_time:.2f}s"
            assert download_time < 3.0, f"S3 download too slow: {download_time:.2f}s"
            assert parse_time < 10.0, f"CSV parsing too slow: {parse_time:.2f}s"
    
    @pytest.mark.performance
    def test_large_excel_file_processing_performance(self, performance_aws_environment):
        """Test performance with large Excel files."""
        s3_client = performance_aws_environment['s3_client']
        upload_bucket = performance_aws_environment['upload_bucket']
        
        # Generate large Excel (5k rows to keep test reasonable)
        large_excel_data = self.generate_large_excel_data(5000)
        file_size = len(large_excel_data)
        
        print(f"Testing with Excel file: {file_size / (1024*1024):.2f} MB, 5,000 rows")
        
        # Upload to S3
        file_key = 'uploads/large_test.xlsx'
        
        start_time = time.time()
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=file_key,
            Body=large_excel_data,
            ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        upload_time = time.time() - start_time
        
        print(f"Excel S3 upload time: {upload_time:.2f} seconds")
        
        # Test Excel processing
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        
        from lambda_function import FileProcessor, download_file_from_s3
        
        # Test file download performance
        start_time = time.time()
        with patch('lambda_function.s3_client', s3_client):
            file_content = download_file_from_s3(upload_bucket, file_key)
        download_time = time.time() - start_time
        
        print(f"Excel S3 download time: {download_time:.2f} seconds")
        
        # Test Excel parsing performance
        start_time = time.time()
        leads = FileProcessor.read_excel_file(file_content)
        parse_time = time.time() - start_time
        
        print(f"Excel parsing time: {parse_time:.2f} seconds")
        print(f"Parsed {len(leads)} leads")
        
        assert len(leads) == 5000
        
        # Performance assertions (Excel is typically slower than CSV)
        assert upload_time < 10.0, f"Excel S3 upload too slow: {upload_time:.2f}s"
        assert download_time < 5.0, f"Excel S3 download too slow: {download_time:.2f}s"
        assert parse_time < 30.0, f"Excel parsing too slow: {parse_time:.2f}s"
    
    @pytest.mark.performance
    def test_batch_dynamodb_operations_performance(self, performance_aws_environment):
        """Test DynamoDB batch operations performance."""
        dynamodb_table = performance_aws_environment['dynamodb_table']
        
        # Generate test leads
        test_leads = []
        for i in range(1000):
            lead = {
                'firstName': f'User{i:04d}',
                'lastName': f'Test{i:04d}',
                'title': 'Engineer',
                'company': f'Company{i % 10}',
                'email': f'user{i:04d}@company{i % 10}.com',
                'remarks': f'Test lead {i}'
            }
            test_leads.append(lead)
        
        # Test batch write performance
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
        from dynamodb_utils import DynamoDBUtils
        
        db_utils = DynamoDBUtils('perf-test-leads', 'ap-southeast-1')
        db_utils.table = dynamodb_table  # Use mocked table
        
        start_time = time.time()
        lead_ids = db_utils.batch_create_leads(test_leads, 'perf-test.csv')
        batch_write_time = time.time() - start_time
        
        print(f"Batch write time for 1000 leads: {batch_write_time:.2f} seconds")
        print(f"Average time per lead: {(batch_write_time / 1000) * 1000:.2f} ms")
        
        assert len(lead_ids) == 1000
        assert batch_write_time < 30.0, f"Batch write too slow: {batch_write_time:.2f}s"
        
        # Test batch read performance
        start_time = time.time()
        result = db_utils.query_leads(filters={}, page_size=1000)
        batch_read_time = time.time() - start_time
        
        print(f"Batch read time for 1000 leads: {batch_read_time:.2f} seconds")
        
        assert result['totalCount'] == 1000
        assert batch_read_time < 10.0, f"Batch read too slow: {batch_read_time:.2f}s"
    
    @pytest.mark.performance
    def test_concurrent_file_uploads_performance(self, performance_aws_environment):
        """Test performance under concurrent file upload scenarios."""
        s3_client = performance_aws_environment['s3_client']
        upload_bucket = performance_aws_environment['upload_bucket']
        
        # Generate multiple small CSV files
        def generate_small_csv(file_id):
            return f"firstName,lastName,email\nUser{file_id},Test{file_id},user{file_id}@test.com"
        
        def upload_file(file_id):
            """Upload a single file and measure time."""
            csv_data = generate_small_csv(file_id)
            file_key = f'uploads/concurrent_test_{file_id}.csv'
            
            start_time = time.time()
            s3_client.put_object(
                Bucket=upload_bucket,
                Key=file_key,
                Body=csv_data.encode('utf-8'),
                ContentType='text/csv'
            )
            upload_time = time.time() - start_time
            
            return file_id, upload_time
        
        # Test concurrent uploads
        num_concurrent_uploads = 10
        
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_file, i) for i in range(num_concurrent_uploads)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        print(f"Concurrent uploads: {num_concurrent_uploads} files in {total_time:.2f} seconds")
        print(f"Average time per upload: {(total_time / num_concurrent_uploads):.2f} seconds")
        
        # Verify all uploads completed
        assert len(results) == num_concurrent_uploads
        
        # Performance assertion
        assert total_time < 15.0, f"Concurrent uploads too slow: {total_time:.2f}s"
    
    @pytest.mark.performance
    def test_lead_reader_pagination_performance(self, performance_aws_environment):
        """Test lead reader pagination performance with large datasets."""
        dynamodb_table = performance_aws_environment['dynamodb_table']
        
        # Populate with large dataset
        test_leads = []
        for i in range(5000):
            lead = {
                'leadId': f'perf-lead-{i:05d}',
                'firstName': f'User{i:05d}',
                'lastName': f'Test{i:05d}',
                'title': f'Title{i % 20}',
                'company': f'Company{i % 50}',
                'email': f'user{i:05d}@company{i % 50}.com',
                'remarks': f'Performance test lead {i}',
                'sourceFile': 'perf-test.csv',
                'createdAt': f'2024-01-{(i % 28) + 1:02d}T10:00:00Z',
                'updatedAt': f'2024-01-{(i % 28) + 1:02d}T10:00:00Z'
            }
            test_leads.append(lead)
        
        # Batch insert
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test pagination performance
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import query_leads_with_pagination
        
        # Test different page sizes
        page_sizes = [10, 50, 100]
        
        for page_size in page_sizes:
            start_time = time.time()
            
            # Query first page
            result = query_leads_with_pagination(
                filters={},
                sort_by='createdAt',
                sort_order='desc',
                page=1,
                page_size=page_size
            )
            
            query_time = time.time() - start_time
            
            print(f"Page size {page_size}: {query_time:.3f} seconds")
            print(f"  Returned {len(result['leads'])} leads")
            print(f"  Total count: {result['pagination']['totalCount']}")
            
            assert len(result['leads']) == page_size
            assert result['pagination']['totalCount'] == 5000
            
            # Performance assertion - should be fast even with large dataset
            assert query_time < 2.0, f"Pagination query too slow for page size {page_size}: {query_time:.3f}s"
    
    @pytest.mark.performance
    def test_filtering_performance_with_large_dataset(self, performance_aws_environment):
        """Test filtering performance with large datasets."""
        dynamodb_table = performance_aws_environment['dynamodb_table']
        
        # Create dataset with specific distribution for filtering tests
        companies = ['Google', 'Microsoft', 'Amazon', 'Apple', 'Meta']
        test_leads = []
        
        for i in range(2000):
            company = companies[i % len(companies)]  # Even distribution
            lead = {
                'leadId': f'filter-test-{i:05d}',
                'firstName': f'User{i:05d}',
                'lastName': f'Test{i:05d}',
                'title': 'Engineer' if i % 2 == 0 else 'Manager',
                'company': company,
                'email': f'user{i:05d}@{company.lower()}.com',
                'remarks': f'Filter test lead {i}',
                'sourceFile': 'filter-test.csv',
                'createdAt': f'2024-01-{(i % 28) + 1:02d}T10:00:00Z',
                'updatedAt': f'2024-01-{(i % 28) + 1:02d}T10:00:00Z'
            }
            test_leads.append(lead)
        
        # Batch insert
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test various filter scenarios
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
        from dynamodb_utils import DynamoDBUtils
        
        db_utils = DynamoDBUtils('perf-test-leads', 'ap-southeast-1')
        db_utils.table = dynamodb_table
        
        filter_tests = [
            {'company': 'Google'},  # Should return ~400 leads
            {'title': 'Engineer'},  # Should return ~1000 leads
            {'company': 'Google', 'title': 'Engineer'},  # Should return ~200 leads
            {'firstName': 'User00001'},  # Should return 1 lead
        ]
        
        for filters in filter_tests:
            start_time = time.time()
            
            result = db_utils.query_leads(
                filters=filters,
                page_size=100
            )
            
            filter_time = time.time() - start_time
            
            print(f"Filter {filters}: {filter_time:.3f} seconds")
            print(f"  Found {result['totalCount']} matching leads")
            
            # Performance assertion
            assert filter_time < 3.0, f"Filtering too slow for {filters}: {filter_time:.3f}s"
    
    @pytest.mark.performance
    def test_csv_export_performance_large_dataset(self, performance_aws_environment):
        """Test CSV export performance with large datasets."""
        dynamodb_table = performance_aws_environment['dynamodb_table']
        
        # Create large dataset for export testing
        test_leads = []
        for i in range(3000):
            lead = {
                'leadId': f'export-test-{i:05d}',
                'firstName': f'User{i:05d}',
                'lastName': f'Test{i:05d}',
                'title': 'Engineer',
                'company': f'Company{i % 10}',
                'email': f'user{i:05d}@company{i % 10}.com',
                'remarks': f'Export test lead {i} with some longer remarks to test CSV generation performance',
                'sourceFile': 'export-test.csv',
                'createdAt': f'2024-01-{(i % 28) + 1:02d}T10:00:00Z',
                'updatedAt': f'2024-01-{(i % 28) + 1:02d}T10:00:00Z'
            }
            test_leads.append(lead)
        
        # Batch insert
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test CSV export performance
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-exporter'))
        from lambda_function import get_filtered_leads_for_export, generate_csv_data
        
        # Test data retrieval performance
        start_time = time.time()
        leads = get_filtered_leads_for_export({})  # Export all leads
        retrieval_time = time.time() - start_time
        
        print(f"Data retrieval time for {len(leads)} leads: {retrieval_time:.2f} seconds")
        
        # Test CSV generation performance
        start_time = time.time()
        csv_data = generate_csv_data(leads)
        generation_time = time.time() - start_time
        
        print(f"CSV generation time: {generation_time:.2f} seconds")
        print(f"CSV size: {len(csv_data) / (1024*1024):.2f} MB")
        
        assert len(leads) == 3000
        assert len(csv_data) > 0
        
        # Performance assertions
        assert retrieval_time < 10.0, f"Data retrieval too slow: {retrieval_time:.2f}s"
        assert generation_time < 5.0, f"CSV generation too slow: {generation_time:.2f}s"
    
    @pytest.mark.performance
    def test_memory_usage_large_files(self, performance_aws_environment):
        """Test memory usage with large file processing."""
        import psutil
        import os
        
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Measure baseline memory
        baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB
        print(f"Baseline memory usage: {baseline_memory:.2f} MB")
        
        # Generate large CSV data (but don't store it all in memory at once)
        large_csv_data = self.generate_large_csv_data(20000)  # 20k rows
        
        # Measure memory after data generation
        after_generation_memory = process.memory_info().rss / (1024 * 1024)
        print(f"Memory after data generation: {after_generation_memory:.2f} MB")
        
        # Process the data
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        from lambda_function import FileProcessor
        
        # Test CSV parsing memory usage
        leads = FileProcessor.read_csv_file(large_csv_data.encode('utf-8'))
        
        # Measure memory after processing
        after_processing_memory = process.memory_info().rss / (1024 * 1024)
        print(f"Memory after processing: {after_processing_memory:.2f} MB")
        
        memory_increase = after_processing_memory - baseline_memory
        print(f"Total memory increase: {memory_increase:.2f} MB")
        print(f"Memory per lead: {(memory_increase * 1024) / len(leads):.2f} KB")
        
        # Memory usage assertions (should be reasonable for Lambda environment)
        assert memory_increase < 200, f"Memory usage too high: {memory_increase:.2f} MB"
        assert len(leads) == 20000
        
        # Clean up
        del large_csv_data
        del leads
    
    @pytest.mark.performance
    def test_response_time_under_load(self, performance_aws_environment):
        """Test API response times under simulated load."""
        dynamodb_table = performance_aws_environment['dynamodb_table']
        
        # Populate with test data
        test_leads = []
        for i in range(1000):
            lead = {
                'leadId': f'load-test-{i:04d}',
                'firstName': f'User{i:04d}',
                'lastName': f'Test{i:04d}',
                'title': 'Engineer',
                'company': f'Company{i % 20}',
                'email': f'user{i:04d}@company{i % 20}.com',
                'remarks': f'Load test lead {i}',
                'sourceFile': 'load-test.csv',
                'createdAt': f'2024-01-{(i % 28) + 1:02d}T10:00:00Z',
                'updatedAt': f'2024-01-{(i % 28) + 1:02d}T10:00:00Z'
            }
            test_leads.append(lead)
        
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Simulate concurrent API requests
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler as reader_handler
        
        def make_api_request(request_id):
            """Simulate a single API request."""
            event = {
                'httpMethod': 'GET',
                'headers': {'Authorization': 'Bearer test-token'},
                'queryStringParameters': {
                    'page': '1',
                    'pageSize': '50',
                    'filter_company': f'Company{request_id % 20}'
                }
            }
            
            context = Mock()
            context.aws_request_id = f'load-test-{request_id}'
            
            start_time = time.time()
            
            with patch('lambda_function.validate_jwt_token') as mock_jwt:
                mock_jwt.return_value = {'sub': f'user-{request_id}'}
                response = reader_handler(event, context)
            
            response_time = time.time() - start_time
            
            return request_id, response_time, response['statusCode']
        
        # Execute concurrent requests
        num_requests = 20
        
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_api_request, i) for i in range(num_requests)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Analyze results
        response_times = [result[1] for result in results]
        status_codes = [result[2] for result in results]
        
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        print(f"Load test results:")
        print(f"  Total requests: {num_requests}")
        print(f"  Total time: {total_time:.2f} seconds")
        print(f"  Average response time: {avg_response_time:.3f} seconds")
        print(f"  Min response time: {min_response_time:.3f} seconds")
        print(f"  Max response time: {max_response_time:.3f} seconds")
        print(f"  Successful requests: {status_codes.count(200)}/{num_requests}")
        
        # Performance assertions
        assert all(code == 200 for code in status_codes), "Some requests failed"
        assert avg_response_time < 1.0, f"Average response time too slow: {avg_response_time:.3f}s"
        assert max_response_time < 3.0, f"Max response time too slow: {max_response_time:.3f}s"

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s', '-m', 'performance'])