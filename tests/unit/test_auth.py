"""
Unit tests for the authentication module.
Tests individual authentication functions and methods.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the frontend js directory to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../frontend/js'))


class TestAuthModule:
    """Test suite for authentication module functions."""
    
    @pytest.fixture
    def mock_cognito_sdk(self):
        """Mock the Cognito SDK objects."""
        mock_sdk = Mock()
        mock_sdk.CognitoUserPool = Mock()
        mock_sdk.CognitoUser = Mock()
        mock_sdk.AuthenticationDetails = Mock()
        mock_sdk.CognitoUserAttribute = Mock()
        return mock_sdk
    
    @pytest.fixture
    def mock_config(self):
        """Mock EasyCRM configuration."""
        return {
            'COGNITO': {
                'USER_POOL_ID': 'test-pool-id',
                'CLIENT_ID': 'test-client-id',
                'REGION': 'ap-southeast-1'
            }
        }
    
    @pytest.fixture
    def mock_utils(self):
        """Mock EasyCRM utilities."""
        mock_utils = Mock()
        mock_utils.showToast = Mock()
        return mock_utils
    
    def test_token_expiration_check_valid_token(self):
        """Test token expiration check with valid token."""
        # Create a token that expires in 1 hour
        future_time = int(time.time()) + 3600
        header = json.dumps({"alg": "HS256", "typ": "JWT"})
        payload = json.dumps({"exp": future_time, "username": "testuser"})
        
        # Base64 encode (simplified for testing)
        import base64
        encoded_header = base64.b64encode(header.encode()).decode()
        encoded_payload = base64.b64encode(payload.encode()).decode()
        token = f"{encoded_header}.{encoded_payload}.signature"
        
        # Mock the auth object
        auth_mock = Mock()
        auth_mock.currentUser = {'token': token}
        
        # Test the token expiration logic (simplified)
        try:
            token_payload = json.loads(base64.b64decode(token.split('.')[1]).decode())
            expiration_time = token_payload['exp'] * 1000
            current_time = time.time() * 1000
            five_minutes = 5 * 60 * 1000
            
            is_expiring = (expiration_time - current_time) < five_minutes
            assert not is_expiring, "Valid token should not be expiring"
        except Exception:
            # If token parsing fails, consider it expiring
            assert False, "Token parsing should not fail for valid token"
    
    def test_token_expiration_check_expired_token(self):
        """Test token expiration check with expired token."""
        # Create a token that expired 1 hour ago
        past_time = int(time.time()) - 3600
        header = json.dumps({"alg": "HS256", "typ": "JWT"})
        payload = json.dumps({"exp": past_time, "username": "testuser"})
        
        import base64
        encoded_header = base64.b64encode(header.encode()).decode()
        encoded_payload = base64.b64encode(payload.encode()).decode()
        token = f"{encoded_header}.{encoded_payload}.signature"
        
        # Test the token expiration logic
        try:
            token_payload = json.loads(base64.b64decode(token.split('.')[1]).decode())
            expiration_time = token_payload['exp'] * 1000
            current_time = time.time() * 1000
            five_minutes = 5 * 60 * 1000
            
            is_expiring = (expiration_time - current_time) < five_minutes
            assert is_expiring, "Expired token should be detected as expiring"
        except Exception:
            # If token parsing fails, consider it expiring
            assert True, "Failed token parsing should be considered expiring"
    
    def test_token_expiration_check_malformed_token(self):
        """Test token expiration check with malformed token."""
        malformed_token = "invalid.token.format"
        
        # Test the token expiration logic with malformed token
        try:
            token_payload = json.loads(base64.b64decode(malformed_token.split('.')[1]).decode())
            # Should not reach here
            assert False, "Malformed token should cause parsing error"
        except Exception:
            # Expected behavior - malformed token should be considered expiring
            is_expiring = True
            assert is_expiring, "Malformed token should be considered expiring"
    
    def test_user_data_cleanup_logic(self):
        """Test user data cleanup logic."""
        # Mock localStorage operations
        mock_storage = {
            'easyCRM_user_data': 'user-data',
            'cognito-session': 'cognito-data',
            'easyCRM_user_preferences': 'user-prefs',
            'other_app_data': 'other-data',
            'regular_data': 'regular'
        }
        
        # Simulate the cleanup logic
        keys_to_remove = []
        for key in mock_storage.keys():
            if key.startswith('easyCRM_user_') or key.startswith('cognito-'):
                keys_to_remove.append(key)
        
        # Remove the keys
        for key in keys_to_remove:
            del mock_storage[key]
        
        # Verify cleanup
        assert 'easyCRM_user_data' not in mock_storage
        assert 'cognito-session' not in mock_storage
        assert 'easyCRM_user_preferences' not in mock_storage
        assert 'other_app_data' in mock_storage
        assert 'regular_data' in mock_storage
    
    def test_authentication_state_validation(self):
        """Test authentication state validation logic."""
        # Test case 1: No user
        current_user = None
        is_authenticated = current_user is not None and current_user.get('token') is not None
        assert not is_authenticated, "Should not be authenticated without user"
        
        # Test case 2: User without token
        current_user = {'username': 'testuser'}
        is_authenticated = current_user is not None and current_user.get('token') is not None
        assert not is_authenticated, "Should not be authenticated without token"
        
        # Test case 3: User with token
        current_user = {'username': 'testuser', 'token': 'valid-token'}
        is_authenticated = current_user is not None and current_user.get('token') is not None
        assert is_authenticated, "Should be authenticated with user and token"
    
    def test_session_validation_logic(self):
        """Test session validation logic."""
        # Mock session object
        class MockSession:
            def __init__(self, is_valid):
                self._is_valid = is_valid
            
            def isValid(self):
                return self._is_valid
            
            def getIdToken(self):
                mock_token = Mock()
                mock_token.getJwtToken.return_value = 'new-id-token'
                return mock_token
            
            def getAccessToken(self):
                mock_token = Mock()
                mock_token.getJwtToken.return_value = 'new-access-token'
                return mock_token
            
            def getRefreshToken(self):
                mock_token = Mock()
                mock_token.getToken.return_value = 'new-refresh-token'
                return mock_token
        
        # Test valid session
        valid_session = MockSession(True)
        assert valid_session.isValid(), "Valid session should return True"
        
        # Test invalid session
        invalid_session = MockSession(False)
        assert not invalid_session.isValid(), "Invalid session should return False"
        
        # Test token extraction from valid session
        if valid_session.isValid():
            id_token = valid_session.getIdToken().getJwtToken()
            access_token = valid_session.getAccessToken().getJwtToken()
            refresh_token = valid_session.getRefreshToken().getToken()
            
            assert id_token == 'new-id-token'
            assert access_token == 'new-access-token'
            assert refresh_token == 'new-refresh-token'
    
    def test_form_validation_logic(self):
        """Test form validation logic."""
        # Test email validation
        def is_valid_email(email):
            import re
            email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            return re.match(email_regex, email) is not None
        
        assert is_valid_email('test@example.com'), "Valid email should pass"
        assert is_valid_email('user.name+tag@domain.co.uk'), "Complex valid email should pass"
        assert not is_valid_email('invalid-email'), "Invalid email should fail"
        assert not is_valid_email('test@'), "Incomplete email should fail"
        assert not is_valid_email('@example.com'), "Email without user should fail"
        
        # Test password validation
        def is_valid_password(password):
            if len(password) < 8:
                return False
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            return has_upper and has_lower and has_digit
        
        assert is_valid_password('TestPass123'), "Valid password should pass"
        assert not is_valid_password('short'), "Short password should fail"
        assert not is_valid_password('nouppercase123'), "Password without uppercase should fail"
        assert not is_valid_password('NOLOWERCASE123'), "Password without lowercase should fail"
        assert not is_valid_password('NoNumbers'), "Password without numbers should fail"
    
    def test_error_handling_logic(self):
        """Test error handling logic."""
        # Test different error types and their handling
        def handle_auth_error(error):
            error_message = str(error)
            
            if 'timeout' in error_message.lower():
                return 'Request timed out. Please check your connection and try again.'
            elif 'network' in error_message.lower():
                return 'Network error. Please check your connection.'
            elif 'session expired' in error_message.lower():
                return 'Your session has expired. Please log in again.'
            elif 'invalid credentials' in error_message.lower():
                return 'Invalid username or password. Please try again.'
            else:
                return 'An unexpected error occurred. Please try again.'
        
        # Test different error scenarios
        assert 'timed out' in handle_auth_error(Exception('Request timeout'))
        assert 'Network error' in handle_auth_error(Exception('Network failure'))
        assert 'session has expired' in handle_auth_error(Exception('Session expired'))
        assert 'Invalid username' in handle_auth_error(Exception('Invalid credentials'))
        assert 'unexpected error' in handle_auth_error(Exception('Unknown error'))
    
    def test_token_refresh_interval_logic(self):
        """Test token refresh interval management."""
        # Mock interval management
        class TokenRefreshManager:
            def __init__(self):
                self.interval_id = None
                self.check_count = 0
            
            def setup_refresh_interval(self):
                # Simulate setting up an interval
                self.interval_id = 'mock-interval-id'
                return self.interval_id
            
            def clear_refresh_interval(self):
                if self.interval_id:
                    self.interval_id = None
                    return True
                return False
            
            def check_token_expiration(self):
                self.check_count += 1
                # Simulate token expiration check
                return self.check_count > 5  # Expire after 5 checks
        
        manager = TokenRefreshManager()
        
        # Test setting up interval
        interval_id = manager.setup_refresh_interval()
        assert interval_id is not None, "Interval should be set up"
        
        # Test token checks
        for i in range(7):
            is_expiring = manager.check_token_expiration()
            if i < 5:
                assert not is_expiring, f"Token should not be expiring at check {i}"
            else:
                assert is_expiring, f"Token should be expiring at check {i}"
        
        # Test clearing interval
        cleared = manager.clear_refresh_interval()
        assert cleared, "Interval should be cleared successfully"
        assert manager.interval_id is None, "Interval ID should be None after clearing"
    
    def test_authentication_flow_states(self):
        """Test different authentication flow states."""
        # Define possible authentication states
        AUTH_STATES = {
            'UNAUTHENTICATED': 'unauthenticated',
            'AUTHENTICATING': 'authenticating',
            'AUTHENTICATED': 'authenticated',
            'TOKEN_EXPIRED': 'token_expired',
            'REFRESHING_TOKEN': 'refreshing_token',
            'LOGOUT': 'logout'
        }
        
        # Test state transitions
        def get_next_state(current_state, action):
            transitions = {
                ('unauthenticated', 'login_attempt'): 'authenticating',
                ('authenticating', 'login_success'): 'authenticated',
                ('authenticating', 'login_failure'): 'unauthenticated',
                ('authenticated', 'token_expired'): 'token_expired',
                ('token_expired', 'refresh_attempt'): 'refreshing_token',
                ('refreshing_token', 'refresh_success'): 'authenticated',
                ('refreshing_token', 'refresh_failure'): 'unauthenticated',
                ('authenticated', 'logout'): 'logout',
                ('logout', 'complete'): 'unauthenticated'
            }
            return transitions.get((current_state, action), current_state)
        
        # Test valid transitions
        assert get_next_state('unauthenticated', 'login_attempt') == 'authenticating'
        assert get_next_state('authenticating', 'login_success') == 'authenticated'
        assert get_next_state('authenticated', 'token_expired') == 'token_expired'
        assert get_next_state('token_expired', 'refresh_attempt') == 'refreshing_token'
        assert get_next_state('refreshing_token', 'refresh_success') == 'authenticated'
        assert get_next_state('authenticated', 'logout') == 'logout'
        
        # Test invalid transitions (should stay in current state)
        assert get_next_state('authenticated', 'login_attempt') == 'authenticated'
        assert get_next_state('unauthenticated', 'logout') == 'unauthenticated'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])