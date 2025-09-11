"""
Performance tests for status polling under load.

Tests the performance characteristics of the status system under various load conditions,
including concurrent polling, high-frequency updates, and stress testing scenarios.
"""

import pytest
import json
import uuid
import time
import threading
import concurrent.futures
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/status-reader'))

from status_service import ProcessingStatusService


class TestStatusPollingPerformance:
    """Test performance of status polling under various load conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_dynamodb = Mock()
        self.status_service = ProcessingStatusService(
            dynamodb_client=self.mock_dynamodb,
            table_name='test-processing-status'
        )
    
    def test_single_client_polling_performance(self):
        """Test performance of single client polling at various frequencies."""
        
        print("🚀 Starting single client polling performance test...")
        
        upload_id = str(uuid.uuid4())
        
        # Mock status response
        mock_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'progress': {'percentage': 50.0},
            'updatedAt': datetime.utcnow().isoformat() + 'Z'
        }
        
        # Test different polling frequencies
        polling_frequencies = [
            {'interval_ms': 500, 'duration_s': 5, 'expected_calls': 10},   # High frequency
            {'interval_ms': 1000, 'duration_s': 5, 'expected_calls': 5},  # Medium frequency
            {'interval_ms': 2000, 'duration_s': 5, 'expected_calls': 2},  # Low frequency
        ]
        
        for freq_test in polling_frequencies:
            print(f"Testing {freq_test['interval_ms']}ms polling interval...")
            
            # Mock DynamoDB response
            self.mock_dynamodb.get_item.return_value = {
                'Item': {
                    'uploadId': {'S': upload_id},
                    'status': {'S': 'processing'},
                    'progress': {'M': {'percentage': {'N': '50.0'}}},
                    'updatedAt': {'S': datetime.utcnow().isoformat() + 'Z'}
                }
            }
            
            # Simulate polling
            start_time = time.time()
            call_count = 0
            response_times = []
            
            while time.time() - start_time < freq_test['duration_s']:
                call_start = time.time()
                
                try:
                    status = self.status_service.get_status(upload_id)
                    call_count += 1
                    
                    call_end = time.time()
                    response_times.append((call_end - call_start) * 1000)  # Convert to ms
                    
                except Exception as e:
                    print(f"Error during polling: {e}")
                
                # Wait for next poll
                time.sleep(freq_test['interval_ms'] / 1000.0)
            
            # Analyze performance
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            max_response_time = max(response_times) if response_times else 0
            min_response_time = min(response_times) if response_times else 0
            
            print(f"  Calls made: {call_count}")
            print(f"  Avg response time: {avg_response_time:.2f}ms")
            print(f"  Max response time: {max_response_time:.2f}ms")
            print(f"  Min response time: {min_response_time:.2f}ms")
            
            # Performance assertions
            assert call_count >= freq_test['expected_calls'] - 1  # Allow for timing variance
            assert avg_response_time < 100  # Should be under 100ms on average
            assert max_response_time < 500  # Should never exceed 500ms
        
        print("✅ Single client polling performance test - PASSED")
    
    def test_concurrent_client_polling_performance(self):
        """Test performance with multiple concurrent clients polling."""
        
        print("🚀 Starting concurrent client polling performance test...")
        
        # Test configuration
        num_clients = 10
        polling_duration = 5  # seconds
        polling_interval = 1  # second
        
        # Create unique upload IDs for each client
        upload_ids = [str(uuid.uuid4()) for _ in range(num_clients)]
        
        # Mock DynamoDB responses for all clients
        def mock_get_item(TableName, Key):
            upload_id = Key['uploadId']['S']
            return {
                'Item': {
                    'uploadId': {'S': upload_id},
                    'status': {'S': 'processing'},
                    'progress': {'M': {'percentage': {'N': '50.0'}}},
                    'updatedAt': {'S': datetime.utcnow().isoformat() + 'Z'}
                }
            }
        
        self.mock_dynamodb.get_item.side_effect = mock_get_item
        
        # Performance tracking
        client_stats = {}
        lock = threading.Lock()
        
        def client_polling_worker(client_id, upload_id):
            """Worker function for each polling client."""
            stats = {
                'client_id': client_id,
                'upload_id': upload_id,
                'calls_made': 0,
                'response_times': [],
                'errors': 0
            }
            
            start_time = time.time()
            
            while time.time() - start_time < polling_duration:
                call_start = time.time()
                
                try:
                    status = self.status_service.get_status(upload_id)
                    stats['calls_made'] += 1
                    
                    call_end = time.time()
                    response_time = (call_end - call_start) * 1000  # Convert to ms
                    stats['response_times'].append(response_time)
                    
                except Exception as e:
                    stats['errors'] += 1
                    print(f"Client {client_id} error: {e}")
                
                time.sleep(polling_interval)
            
            # Store stats thread-safely
            with lock:
                client_stats[client_id] = stats
        
        # Start concurrent clients
        print(f"Starting {num_clients} concurrent polling clients...")
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_clients) as executor:
            futures = []
            
            for i, upload_id in enumerate(upload_ids):
                future = executor.submit(client_polling_worker, i, upload_id)
                futures.append(future)
            
            # Wait for all clients to complete
            concurrent.futures.wait(futures)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze concurrent performance
        total_calls = sum(stats['calls_made'] for stats in client_stats.values())
        total_errors = sum(stats['errors'] for stats in client_stats.values())
        all_response_times = []
        
        for stats in client_stats.values():
            all_response_times.extend(stats['response_times'])
        
        if all_response_times:
            avg_response_time = sum(all_response_times) / len(all_response_times)
            max_response_time = max(all_response_times)
            min_response_time = min(all_response_times)
            
            # Calculate percentiles
            sorted_times = sorted(all_response_times)
            p95_response_time = sorted_times[int(0.95 * len(sorted_times))]
            p99_response_time = sorted_times[int(0.99 * len(sorted_times))]
        else:
            avg_response_time = max_response_time = min_response_time = 0
            p95_response_time = p99_response_time = 0
        
        calls_per_second = total_calls / total_duration if total_duration > 0 else 0
        error_rate = (total_errors / total_calls * 100) if total_calls > 0 else 0
        
        print(f"Concurrent polling results:")
        print(f"  Clients: {num_clients}")
        print(f"  Duration: {total_duration:.2f}s")
        print(f"  Total calls: {total_calls}")
        print(f"  Calls per second: {calls_per_second:.2f}")
        print(f"  Total errors: {total_errors}")
        print(f"  Error rate: {error_rate:.2f}%")
        print(f"  Avg response time: {avg_response_time:.2f}ms")
        print(f"  Max response time: {max_response_time:.2f}ms")
        print(f"  Min response time: {min_response_time:.2f}ms")
        print(f"  95th percentile: {p95_response_time:.2f}ms")
        print(f"  99th percentile: {p99_response_time:.2f}ms")
        
        # Performance assertions
        assert total_calls > 0, "No successful calls were made"
        assert error_rate < 5.0, f"Error rate too high: {error_rate}%"
        assert avg_response_time < 200, f"Average response time too high: {avg_response_time}ms"
        assert p95_response_time < 500, f"95th percentile response time too high: {p95_response_time}ms"
        assert calls_per_second > 5, f"Throughput too low: {calls_per_second} calls/sec"
        
        print("✅ Concurrent client polling performance test - PASSED")
    
    def test_high_frequency_status_updates_performance(self):
        """Test performance with high-frequency status updates."""
        
        print("🚀 Starting high-frequency status updates performance test...")
        
        upload_id = str(uuid.uuid4())
        
        # Mock successful update responses
        def mock_update_item(**kwargs):
            return {
                'Attributes': {
                    'uploadId': {'S': upload_id},
                    'status': {'S': 'processing'},
                    'progress': {'M': {'percentage': {'N': '50.0'}}},
                    'updatedAt': {'S': datetime.utcnow().isoformat() + 'Z'},
                    'ttl': {'N': str(int((datetime.utcnow() + timedelta(hours=24)).timestamp()))}
                }
            }
        
        self.mock_dynamodb.update_item.side_effect = mock_update_item
        
        # Mock get_status for progress calculation
        def mock_get_item(**kwargs):
            return {
                'Item': {
                    'uploadId': {'S': upload_id},
                    'status': {'S': 'processing'},
                    'progress': {'M': {'percentage': {'N': '45.0'}}},
                    'metadata': {'M': {'startTime': {'S': '2025-01-09T10:00:00Z'}}},
                    'updatedAt': {'S': datetime.utcnow().isoformat() + 'Z'}
                }
            }
        
        self.mock_dynamodb.get_item.side_effect = mock_get_item
        
        # Test rapid status updates
        num_updates = 100
        update_interval = 0.01  # 10ms between updates
        
        print(f"Performing {num_updates} rapid status updates...")
        
        start_time = time.time()
        update_times = []
        errors = 0
        
        for i in range(num_updates):
            update_start = time.time()
            
            try:
                # Simulate progress update
                progress = {
                    'totalBatches': 100,
                    'completedBatches': i + 1,
                    'percentage': (i + 1) / 100 * 100
                }
                
                with patch.object(self.status_service, '_get_current_timestamp', 
                                return_value=datetime.utcnow().isoformat() + 'Z'), \
                     patch.object(self.status_service, '_calculate_ttl', 
                                return_value=int((datetime.utcnow() + timedelta(hours=24)).timestamp())):
                    
                    result = self.status_service.update_status(
                        upload_id, 
                        progress=progress
                    )
                
                update_end = time.time()
                update_times.append((update_end - update_start) * 1000)  # Convert to ms
                
            except Exception as e:
                errors += 1
                print(f"Update {i} failed: {e}")
            
            time.sleep(update_interval)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze update performance
        successful_updates = len(update_times)
        avg_update_time = sum(update_times) / len(update_times) if update_times else 0
        max_update_time = max(update_times) if update_times else 0
        min_update_time = min(update_times) if update_times else 0
        
        updates_per_second = successful_updates / total_duration if total_duration > 0 else 0
        error_rate = (errors / num_updates * 100) if num_updates > 0 else 0
        
        print(f"High-frequency update results:")
        print(f"  Total updates attempted: {num_updates}")
        print(f"  Successful updates: {successful_updates}")
        print(f"  Duration: {total_duration:.2f}s")
        print(f"  Updates per second: {updates_per_second:.2f}")
        print(f"  Errors: {errors}")
        print(f"  Error rate: {error_rate:.2f}%")
        print(f"  Avg update time: {avg_update_time:.2f}ms")
        print(f"  Max update time: {max_update_time:.2f}ms")
        print(f"  Min update time: {min_update_time:.2f}ms")
        
        # Performance assertions
        assert successful_updates >= num_updates * 0.95, "Too many failed updates"
        assert error_rate < 5.0, f"Error rate too high: {error_rate}%"
        assert avg_update_time < 50, f"Average update time too high: {avg_update_time}ms"
        assert updates_per_second > 10, f"Update throughput too low: {updates_per_second} updates/sec"
        
        print("✅ High-frequency status updates performance test - PASSED")
    
    def test_memory_usage_under_load(self):
        """Test memory usage patterns under sustained load."""
        
        print("🚀 Starting memory usage under load test...")
        
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Initial memory usage: {initial_memory:.2f} MB")
        
        # Create multiple status services and perform operations
        num_services = 50
        operations_per_service = 20
        
        services = []
        upload_ids = []
        
        # Mock responses
        def mock_operations(**kwargs):
            return {
                'Attributes': {
                    'uploadId': {'S': 'test-id'},
                    'status': {'S': 'processing'},
                    'updatedAt': {'S': datetime.utcnow().isoformat() + 'Z'},
                    'ttl': {'N': str(int((datetime.utcnow() + timedelta(hours=24)).timestamp()))}
                }
            }
        
        # Create services and perform operations
        for i in range(num_services):
            mock_dynamodb = Mock()
            mock_dynamodb.update_item.side_effect = mock_operations
            mock_dynamodb.get_item.return_value = {
                'Item': {
                    'uploadId': {'S': f'test-{i}'},
                    'status': {'S': 'processing'},
                    'updatedAt': {'S': datetime.utcnow().isoformat() + 'Z'}
                }
            }
            
            service = ProcessingStatusService(
                dynamodb_client=mock_dynamodb,
                table_name=f'test-table-{i}'
            )
            services.append(service)
            upload_ids.append(f'test-upload-{i}')
        
        # Perform operations
        memory_samples = []
        
        for operation in range(operations_per_service):
            for i, service in enumerate(services):
                try:
                    # Mix of different operations
                    if operation % 3 == 0:
                        with patch.object(service, '_get_current_timestamp', 
                                        return_value=datetime.utcnow().isoformat() + 'Z'), \
                             patch.object(service, '_calculate_ttl', 
                                        return_value=int((datetime.utcnow() + timedelta(hours=24)).timestamp())):
                            service.update_status(upload_ids[i], progress={'percentage': operation * 5})
                    elif operation % 3 == 1:
                        service.get_status(upload_ids[i])
                    else:
                        with patch.object(service, '_get_current_timestamp', 
                                        return_value=datetime.utcnow().isoformat() + 'Z'), \
                             patch.object(service, '_calculate_ttl', 
                                        return_value=int((datetime.utcnow() + timedelta(hours=24)).timestamp())):
                            service.set_error(upload_ids[i], "Test error", "TEST_ERROR")
                except Exception as e:
                    pass  # Ignore errors for memory test
            
            # Sample memory usage
            if operation % 5 == 0:  # Sample every 5 operations
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_samples.append(current_memory)
        
        # Force garbage collection
        gc.collect()
        
        # Final memory measurement
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        peak_memory = max(memory_samples) if memory_samples else final_memory
        memory_growth = final_memory - initial_memory
        
        print(f"Memory usage analysis:")
        print(f"  Initial memory: {initial_memory:.2f} MB")
        print(f"  Peak memory: {peak_memory:.2f} MB")
        print(f"  Final memory: {final_memory:.2f} MB")
        print(f"  Memory growth: {memory_growth:.2f} MB")
        print(f"  Operations performed: {num_services * operations_per_service}")
        
        # Memory usage assertions
        assert memory_growth < 100, f"Memory growth too high: {memory_growth:.2f} MB"
        assert peak_memory < initial_memory + 150, f"Peak memory usage too high: {peak_memory:.2f} MB"
        
        print("✅ Memory usage under load test - PASSED")
    
    def test_error_handling_performance_impact(self):
        """Test performance impact of error handling mechanisms."""
        
        print("🚀 Starting error handling performance impact test...")
        
        upload_id = str(uuid.uuid4())
        
        # Test scenarios: normal operations vs error conditions
        scenarios = [
            {
                'name': 'Normal Operations',
                'error_rate': 0.0,
                'operations': 100
            },
            {
                'name': 'Low Error Rate',
                'error_rate': 0.05,  # 5% errors
                'operations': 100
            },
            {
                'name': 'Medium Error Rate',
                'error_rate': 0.15,  # 15% errors
                'operations': 100
            },
            {
                'name': 'High Error Rate',
                'error_rate': 0.30,  # 30% errors
                'operations': 100
            }
        ]
        
        scenario_results = {}
        
        for scenario in scenarios:
            print(f"Testing scenario: {scenario['name']}")
            
            operation_times = []
            errors_encountered = 0
            
            # Configure mock to simulate errors
            def mock_operation_with_errors(**kwargs):
                import random
                if random.random() < scenario['error_rate']:
                    # Simulate different types of errors
                    error_types = [
                        ('ThrottlingException', 'Request throttled'),
                        ('ValidationException', 'Invalid input'),
                        ('InternalServerError', 'Internal error')
                    ]
                    error_code, error_message = random.choice(error_types)
                    from botocore.exceptions import ClientError
                    raise ClientError(
                        {'Error': {'Code': error_code, 'Message': error_message}},
                        'TestOperation'
                    )
                else:
                    return {
                        'Attributes': {
                            'uploadId': {'S': upload_id},
                            'status': {'S': 'processing'},
                            'updatedAt': {'S': datetime.utcnow().isoformat() + 'Z'},
                            'ttl': {'N': str(int((datetime.utcnow() + timedelta(hours=24)).timestamp()))}
                        }
                    }
            
            self.mock_dynamodb.update_item.side_effect = mock_operation_with_errors
            
            # Perform operations and measure performance
            start_time = time.time()
            
            for i in range(scenario['operations']):
                operation_start = time.time()
                
                try:
                    with patch.object(self.status_service, '_get_current_timestamp', 
                                    return_value=datetime.utcnow().isoformat() + 'Z'), \
                         patch.object(self.status_service, '_calculate_ttl', 
                                    return_value=int((datetime.utcnow() + timedelta(hours=24)).timestamp())), \
                         patch('time.sleep'):  # Mock sleep to speed up retries
                        
                        result = self.status_service.update_status(
                            upload_id, 
                            progress={'percentage': i}
                        )
                    
                except Exception as e:
                    errors_encountered += 1
                
                operation_end = time.time()
                operation_times.append((operation_end - operation_start) * 1000)  # Convert to ms
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Calculate metrics
            avg_operation_time = sum(operation_times) / len(operation_times) if operation_times else 0
            max_operation_time = max(operation_times) if operation_times else 0
            operations_per_second = scenario['operations'] / total_duration if total_duration > 0 else 0
            actual_error_rate = errors_encountered / scenario['operations'] if scenario['operations'] > 0 else 0
            
            scenario_results[scenario['name']] = {
                'avg_operation_time': avg_operation_time,
                'max_operation_time': max_operation_time,
                'operations_per_second': operations_per_second,
                'actual_error_rate': actual_error_rate,
                'total_duration': total_duration
            }
            
            print(f"  Avg operation time: {avg_operation_time:.2f}ms")
            print(f"  Max operation time: {max_operation_time:.2f}ms")
            print(f"  Operations per second: {operations_per_second:.2f}")
            print(f"  Actual error rate: {actual_error_rate:.2%}")
        
        # Analyze performance impact of errors
        normal_perf = scenario_results['Normal Operations']
        high_error_perf = scenario_results['High Error Rate']
        
        performance_degradation = (
            (high_error_perf['avg_operation_time'] - normal_perf['avg_operation_time']) / 
            normal_perf['avg_operation_time'] * 100
        ) if normal_perf['avg_operation_time'] > 0 else 0
        
        throughput_impact = (
            (normal_perf['operations_per_second'] - high_error_perf['operations_per_second']) / 
            normal_perf['operations_per_second'] * 100
        ) if normal_perf['operations_per_second'] > 0 else 0
        
        print(f"Error handling impact analysis:")
        print(f"  Performance degradation: {performance_degradation:.1f}%")
        print(f"  Throughput impact: {throughput_impact:.1f}%")
        
        # Performance impact assertions
        assert performance_degradation < 200, f"Performance degradation too high: {performance_degradation:.1f}%"
        assert throughput_impact < 150, f"Throughput impact too high: {throughput_impact:.1f}%"
        assert high_error_perf['avg_operation_time'] < 1000, "Error handling taking too long"
        
        print("✅ Error handling performance impact test - PASSED")


if __name__ == '__main__':
    # Run performance tests
    test_instance = TestStatusPollingPerformance()
    
    test_instance.test_single_client_polling_performance()
    test_instance.test_concurrent_client_polling_performance()
    test_instance.test_high_frequency_status_updates_performance()
    test_instance.test_memory_usage_under_load()
    test_instance.test_error_handling_performance_impact()
    
    print("\n🎉 All status polling performance tests passed!")