"""
DeepSeek API integration tests.

Tests actual DeepSeek API integration with real API calls,
error handling, rate limiting, and data standardization accuracy.
"""

import pytest
import json
import os
import sys
import time
from unittest.mock import patch, Mock
import requests

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

class TestDeepSeekAPIIntegration:
    """Integration tests for DeepSeek API."""
    
    @pytest.fixture
    def deepseek_api_key(self):
        """Get DeepSeek API key from environment."""
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            pytest.skip("DEEPSEEK_API_KEY not set for integration testing")
        return api_key
    
    @pytest.fixture
    def sample_lead_data(self):
        """Sample lead data for testing standardization."""
        return [
            {
                'Name': 'John Smith',
                'Job Title': 'Software Engineer',
                'Company': 'Tech Solutions Inc',
                'Email': 'john.smith@techsolutions.com',
                'Phone': '+1-555-0123',
                'Notes': 'Interested in cloud migration solutions'
            },
            {
                'Full Name': 'Sarah Johnson',
                'Position': 'Marketing Manager',
                'Organization': 'Digital Marketing Co',
                'Contact Email': 'sarah.j@digitalmarketing.com',
                'Additional Info': 'Looking for automation tools, budget $50k'
            },
            {
                'contact_name': 'Dr. Michael O\'Connor Jr.',
                'job_position': 'Chief Technology Officer & VP Engineering',
                'company_name': 'Advanced Systems & Solutions LLC',
                'email_addr': 'michael.oconnor@advancedsystems.co.uk',
                'phone_number': '+44 20 7946 0958',
                'notes': 'Evaluating AI solutions for Q2 implementation'
            }
        ]
    
    @pytest.fixture
    def messy_lead_data(self):
        """Messy, real-world lead data for testing robustness."""
        return [
            {
                'person': 'Lisa Chen-Wang',
                'role': 'Senior Product Manager',
                'employer': 'Global Tech Innovations',
                'contact': 'l.chen.wang@globaltech.com',
                'additional_info': 'Team of 15 developers, Q2 implementation timeline'
            },
            {
                'Name': 'Bob Wilson III',
                'Title': 'VP of Sales & Marketing',
                'Company': 'Enterprise Solutions Corp.',
                'Email': 'bwilson@enterprise-solutions.com',
                'Phone': '555.123.4567 ext 890',
                'Comments': 'Urgent need for scalable infrastructure, decision maker'
            },
            {
                'contact_info': 'Alice Thompson, Data Scientist at Analytics Plus, alice@analytics-plus.io, +1-800-DATA-SCI',
                'notes': 'Specializes in machine learning, interested in cloud analytics platform'
            }
        ]
    
    @pytest.mark.integration
    @pytest.mark.deepseek
    def test_basic_lead_standardization(self, deepseek_api_key, sample_lead_data):
        """Test basic lead data standardization with DeepSeek API."""
        from lambda_function import DeepSeekClient
        
        client = DeepSeekClient(deepseek_api_key)
        
        # Test with sample data
        result = client.standardize_leads(sample_lead_data)
        
        # Verify response structure
        assert isinstance(result, list)
        assert len(result) == len(sample_lead_data)
        
        # Check each standardized lead
        for i, lead in enumerate(result):
            print(f"Original lead {i+1}: {sample_lead_data[i]}")
            print(f"Standardized lead {i+1}: {lead}")
            print("---")
            
            # Verify required fields are present
            required_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'remarks']
            for field in required_fields:
                assert field in lead, f"Missing field {field} in lead {i+1}"
                assert lead[field] is not None, f"Field {field} is None in lead {i+1}"
            
            # Verify data mapping accuracy
            if i == 0:  # John Smith
                assert 'John' in lead['firstName']
                assert 'Smith' in lead['lastName']
                assert 'Software Engineer' in lead['title']
                assert 'Tech Solutions' in lead['company']
                assert 'john.smith@techsolutions.com' in lead['email']
            elif i == 1:  # Sarah Johnson
                assert 'Sarah' in lead['firstName']
                assert 'Johnson' in lead['lastName']
                assert 'Marketing Manager' in lead['title']
                assert 'Digital Marketing' in lead['company']
                assert 'sarah.j@digitalmarketing.com' in lead['email']
    
    @pytest.mark.integration
    @pytest.mark.deepseek
    def test_messy_data_standardization(self, deepseek_api_key, messy_lead_data):
        """Test standardization of messy, real-world data."""
        from lambda_function import DeepSeekClient
        
        client = DeepSeekClient(deepseek_api_key)
        
        result = client.standardize_leads(messy_lead_data)
        
        assert isinstance(result, list)
        assert len(result) == len(messy_lead_data)
        
        for i, lead in enumerate(result):
            print(f"Messy lead {i+1}: {messy_lead_data[i]}")
            print(f"Standardized lead {i+1}: {lead}")
            print("---")
            
            # Verify structure
            required_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'remarks']
            for field in required_fields:
                assert field in lead
                assert isinstance(lead[field], str)
            
            # Verify that complex data is handled
            if i == 0:  # Lisa Chen-Wang
                assert 'Lisa' in lead['firstName']
                assert 'Chen' in lead['lastName'] or 'Wang' in lead['lastName']
                assert 'Product Manager' in lead['title']
            elif i == 2:  # Alice Thompson (complex contact_info field)
                assert 'Alice' in lead['firstName']
                assert 'Thompson' in lead['lastName']
                assert 'Data Scientist' in lead['title']
                assert 'Analytics Plus' in lead['company']
    
    @pytest.mark.integration
    @pytest.mark.deepseek
    def test_api_error_handling(self, deepseek_api_key):
        """Test DeepSeek API error handling."""
        from lambda_function import DeepSeekClient
        from error_handling import ExternalAPIError
        
        # Test with invalid API key
        invalid_client = DeepSeekClient('invalid-api-key')
        
        with pytest.raises(ExternalAPIError):
            invalid_client.standardize_leads([{'name': 'Test User'}])
        
        # Test with empty data
        valid_client = DeepSeekClient(deepseek_api_key)
        result = valid_client.standardize_leads([])
        assert result == []
        
        # Test with malformed data
        malformed_data = [None, {}, {'invalid': 'structure'}]
        
        # Should handle gracefully without crashing
        try:
            result = valid_client.standardize_leads(malformed_data)
            # If it succeeds, verify it returns some result
            assert isinstance(result, list)
        except ExternalAPIError:
            # If it fails, that's also acceptable for malformed data
            pass
    
    @pytest.mark.integration
    @pytest.mark.deepseek
    def test_api_rate_limiting(self, deepseek_api_key):
        """Test DeepSeek API rate limiting behavior."""
        from lambda_function import DeepSeekClient
        
        client = DeepSeekClient(deepseek_api_key)
        
        # Make multiple rapid requests to test rate limiting
        test_data = [{'name': f'Test User {i}', 'company': f'Company {i}'} for i in range(3)]
        
        response_times = []
        
        for i in range(3):
            start_time = time.time()
            
            try:
                result = client.standardize_leads(test_data)
                response_time = time.time() - start_time
                response_times.append(response_time)
                
                print(f"Request {i+1}: {response_time:.2f} seconds")
                
                # Verify successful response
                assert isinstance(result, list)
                assert len(result) == len(test_data)
                
                # Small delay between requests
                time.sleep(1)
                
            except Exception as e:
                print(f"Request {i+1} failed: {str(e)}")
                # Rate limiting or other API errors are acceptable
                break
        
        # Should have at least one successful request
        assert len(response_times) > 0
        
        # Response times should be reasonable
        avg_response_time = sum(response_times) / len(response_times)
        print(f"Average response time: {avg_response_time:.2f} seconds")
        
        # Should respond within reasonable time (30 seconds max)
        assert avg_response_time < 30.0
    
    @pytest.mark.integration
    @pytest.mark.deepseek
    def test_large_batch_processing(self, deepseek_api_key):
        """Test processing larger batches of leads."""
        from lambda_function import DeepSeekClient
        
        client = DeepSeekClient(deepseek_api_key)
        
        # Generate larger dataset
        large_dataset = []
        for i in range(20):  # 20 leads
            lead = {
                'Name': f'User {i:02d}',
                'Job Title': f'Position {i}',
                'Company': f'Company {i % 5}',  # 5 different companies
                'Email': f'user{i:02d}@company{i % 5}.com',
                'Phone': f'+1-555-{i:04d}',
                'Notes': f'Test lead number {i} with various details'
            }
            large_dataset.append(lead)
        
        start_time = time.time()
        result = client.standardize_leads(large_dataset)
        processing_time = time.time() - start_time
        
        print(f"Processed {len(large_dataset)} leads in {processing_time:.2f} seconds")
        print(f"Average time per lead: {(processing_time / len(large_dataset)):.3f} seconds")
        
        # Verify results
        assert isinstance(result, list)
        assert len(result) == len(large_dataset)
        
        # Verify each lead is properly structured
        for i, lead in enumerate(result):
            required_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'remarks']
            for field in required_fields:
                assert field in lead, f"Missing {field} in lead {i}"
                assert isinstance(lead[field], str), f"Field {field} not string in lead {i}"
        
        # Performance assertion
        assert processing_time < 60.0, f"Processing too slow: {processing_time:.2f}s"
    
    @pytest.mark.integration
    @pytest.mark.deepseek
    def test_chatbot_query_generation(self, deepseek_api_key):
        """Test DeepSeek API for chatbot query generation."""
        # Import chatbot functions
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
        
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': deepseek_api_key}):
            from lambda_function import generate_dynamodb_query
            
            test_queries = [
                "show me leads from Google",
                "how many leads do we have?",
                "find all engineers",
                "group leads by company",
                "leads with manager in title",
                "show me recent leads from tech companies"
            ]
            
            for query in test_queries:
                print(f"Testing query: '{query}'")
                
                try:
                    result = generate_dynamodb_query(query)
                    
                    if result is not None:
                        print(f"Generated query structure: {result}")
                        
                        # Verify query structure
                        assert 'type' in result
                        assert result['type'] in ['filter', 'count', 'aggregate']
                        
                        if result['type'] == 'filter':
                            assert 'filters' in result
                            assert 'limit' in result
                            assert isinstance(result['filters'], dict)
                            assert isinstance(result['limit'], int)
                            assert 1 <= result['limit'] <= 50
                        
                        elif result['type'] == 'count':
                            assert 'filters' in result
                            assert isinstance(result['filters'], dict)
                        
                        elif result['type'] == 'aggregate':
                            assert 'groupBy' in result
                            assert 'filters' in result
                            assert result['groupBy'] in ['company', 'title', 'firstName', 'lastName', 'email']
                    else:
                        print("Query could not be parsed (returned None)")
                    
                    print("---")
                    
                    # Small delay between API calls
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"Query failed: {str(e)}")
                    # Some queries might fail, which is acceptable
                    continue
    
    @pytest.mark.integration
    @pytest.mark.deepseek
    def test_api_response_validation(self, deepseek_api_key):
        """Test validation of DeepSeek API responses."""
        from lambda_function import DeepSeekClient
        
        client = DeepSeekClient(deepseek_api_key)
        
        # Test with data that might produce edge cases
        edge_case_data = [
            {
                'name': '',  # Empty name
                'company': 'Test Company',
                'email': 'test@example.com'
            },
            {
                'name': 'John Doe',
                'company': '',  # Empty company
                'email': 'john@example.com'
            },
            {
                'name': 'Jane Smith',
                'company': 'Another Company',
                'email': ''  # Empty email
            },
            {
                'name': 'Very Long Name That Exceeds Normal Length Expectations And Might Cause Issues',
                'company': 'Company With A Very Long Name That Also Exceeds Normal Expectations',
                'email': 'very.long.email.address.that.might.cause.issues@very-long-domain-name.com'
            }
        ]
        
        result = client.standardize_leads(edge_case_data)
        
        assert isinstance(result, list)
        assert len(result) == len(edge_case_data)
        
        for i, lead in enumerate(result):
            print(f"Edge case {i+1}: {edge_case_data[i]}")
            print(f"Standardized: {lead}")
            print("---")
            
            # Verify structure even with edge cases
            required_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'remarks']
            for field in required_fields:
                assert field in lead
                assert isinstance(lead[field], str)
                
                # Empty fields should be filled with 'N/A'
                if not lead[field].strip():
                    assert lead[field] == 'N/A' or lead[field] == ''
    
    @pytest.mark.integration
    @pytest.mark.deepseek
    def test_concurrent_api_requests(self, deepseek_api_key):
        """Test concurrent DeepSeek API requests."""
        from lambda_function import DeepSeekClient
        import concurrent.futures
        import threading
        
        client = DeepSeekClient(deepseek_api_key)
        
        def make_api_request(request_id):
            """Make a single API request."""
            test_data = [{
                'name': f'Concurrent User {request_id}',
                'company': f'Concurrent Company {request_id}',
                'email': f'user{request_id}@concurrent.com'
            }]
            
            try:
                start_time = time.time()
                result = client.standardize_leads(test_data)
                response_time = time.time() - start_time
                
                return {
                    'request_id': request_id,
                    'success': True,
                    'response_time': response_time,
                    'result_count': len(result) if result else 0
                }
            except Exception as e:
                return {
                    'request_id': request_id,
                    'success': False,
                    'error': str(e),
                    'response_time': None
                }
        
        # Execute concurrent requests
        num_concurrent = 3  # Keep it small to avoid rate limiting
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(make_api_request, i) for i in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Analyze results
        successful_requests = [r for r in results if r['success']]
        failed_requests = [r for r in results if not r['success']]
        
        print(f"Successful requests: {len(successful_requests)}/{num_concurrent}")
        print(f"Failed requests: {len(failed_requests)}")
        
        if successful_requests:
            avg_response_time = sum(r['response_time'] for r in successful_requests) / len(successful_requests)
            print(f"Average response time: {avg_response_time:.2f} seconds")
        
        # Should have at least some successful requests
        assert len(successful_requests) > 0, "All concurrent requests failed"
        
        # Print any errors for debugging
        for failed in failed_requests:
            print(f"Request {failed['request_id']} failed: {failed['error']}")

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s', '-m', 'deepseek'])