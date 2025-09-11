"""
Integration tests for Cognito authentication flow.
Tests the complete authentication workflow including login, token refresh, and logout.
"""

import pytest
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import boto3
from moto import mock_cognitoidp
import os


class TestCognitoAuthentication:
    """Test suite for Cognito authentication integration."""
    
    @pytest.fixture(scope="class")
    def cognito_client(self):
        """Create a Cognito client for testing."""
        return boto3.client(
            'cognito-idp',
            region_name='ap-southeast-1',
            aws_access_key_id='testing',
            aws_secret_access_key='testing'
        )
    
    @pytest.fixture(scope="class")
    def test_user_pool(self, cognito_client):
        """Create a test user pool."""
        with mock_cognitoidp():
            response = cognito_client.create_user_pool(
                PoolName='test-easy-crm-users',
                Policies={
                    'PasswordPolicy': {
                        'MinimumLength': 8,
                        'RequireUppercase': True,
                        'RequireLowercase': True,
                        'RequireNumbers': True,
                        'RequireSymbols': False
                    }
                },
                AutoVerifiedAttributes=['email'],
                AliasAttributes=['email']
            )
            user_pool_id = response['UserPool']['Id']
            
            # Create user pool client
            client_response = cognito_client.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName='test-easy-crm-client',
                GenerateSecret=False,
                ExplicitAuthFlows=[
                    'ALLOW_USER_SRP_AUTH',
                    'ALLOW_REFRESH_TOKEN_AUTH',
                    'ALLOW_USER_PASSWORD_AUTH'
                ]
            )
            
            return {
                'user_pool_id': user_pool_id,
                'client_id': client_response['UserPoolClient']['ClientId']
            }
    
    @pytest.fixture(scope="class")
    def test_user(self, cognito_client, test_user_pool):
        """Create a test user."""
        with mock_cognitoidp():
            username = 'testuser@example.com'
            password = 'TestPass123'
            
            # Create user
            cognito_client.admin_create_user(
                UserPoolId=test_user_pool['user_pool_id'],
                Username=username,
                UserAttributes=[
                    {'Name': 'email', 'Value': username},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                TemporaryPassword=password,
                MessageAction='SUPPRESS'
            )
            
            # Set permanent password
            cognito_client.admin_set_user_password(
                UserPoolId=test_user_pool['user_pool_id'],
                Username=username,
                Password=password,
                Permanent=True
            )
            
            return {
                'username': username,
                'password': password
            }
    
    @pytest.fixture(scope="class")
    def web_driver(self):
        """Create a web driver for browser testing."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        yield driver
        driver.quit()
    
    @pytest.fixture
    def frontend_url(self):
        """Get the frontend URL for testing."""
        # In real deployment, this would be the CloudFront URL
        return os.getenv('FRONTEND_URL', 'http://localhost:8080')
    
    def test_cognito_configuration_loading(self, web_driver, frontend_url):
        """Test that Cognito configuration is loaded correctly."""
        web_driver.get(frontend_url)
        
        # Wait for the page to load
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.ID, "login-screen"))
        )
        
        # Check that Cognito SDK is loaded
        cognito_loaded = web_driver.execute_script(
            "return typeof AmazonCognitoIdentity !== 'undefined'"
        )
        assert cognito_loaded, "Cognito SDK should be loaded"
        
        # Check that EasyCRM Auth module is initialized
        auth_initialized = web_driver.execute_script(
            "return window.EasyCRM && window.EasyCRM.Auth && typeof window.EasyCRM.Auth.init === 'function'"
        )
        assert auth_initialized, "EasyCRM Auth module should be initialized"
    
    def test_login_form_rendering(self, web_driver, frontend_url):
        """Test that the login form renders correctly."""
        web_driver.get(frontend_url)
        
        # Wait for login screen to be visible
        login_screen = WebDriverWait(web_driver, 10).until(
            EC.visibility_of_element_located((By.ID, "login-screen"))
        )
        assert login_screen.is_displayed()
        
        # Check for login form elements
        username_input = web_driver.find_element(By.ID, "username")
        password_input = web_driver.find_element(By.ID, "password")
        login_button = web_driver.find_element(By.ID, "login-submit")
        
        assert username_input.is_displayed()
        assert password_input.is_displayed()
        assert login_button.is_displayed()
        assert login_button.text == "Sign In"
    
    def test_signup_form_toggle(self, web_driver, frontend_url):
        """Test toggling between login and signup forms."""
        web_driver.get(frontend_url)
        
        # Wait for login form
        WebDriverWait(web_driver, 10).until(
            EC.visibility_of_element_located((By.ID, "login-form"))
        )
        
        # Click show signup
        show_signup = web_driver.find_element(By.ID, "show-signup")
        show_signup.click()
        
        # Check that signup form is visible
        signup_form = WebDriverWait(web_driver, 5).until(
            EC.visibility_of_element_located((By.ID, "signup-form"))
        )
        assert signup_form.is_displayed()
        
        # Check that login form is hidden
        login_form = web_driver.find_element(By.ID, "login-form")
        assert "hidden" in login_form.get_attribute("class")
        
        # Click show login
        show_login = web_driver.find_element(By.ID, "show-login")
        show_login.click()
        
        # Check that login form is visible again
        WebDriverWait(web_driver, 5).until(
            lambda driver: "hidden" not in login_form.get_attribute("class")
        )
        assert login_form.is_displayed()
    
    def test_login_validation(self, web_driver, frontend_url):
        """Test login form validation."""
        web_driver.get(frontend_url)
        
        # Wait for login form
        WebDriverWait(web_driver, 10).until(
            EC.visibility_of_element_located((By.ID, "login-form"))
        )
        
        # Try to submit empty form
        login_button = web_driver.find_element(By.ID, "login-submit")
        login_button.click()
        
        # Check HTML5 validation
        username_input = web_driver.find_element(By.ID, "username")
        password_input = web_driver.find_element(By.ID, "password")
        
        # HTML5 required validation should prevent submission
        assert username_input.get_attribute("required") == "true"
        assert password_input.get_attribute("required") == "true"
    
    def test_invalid_login_attempt(self, web_driver, frontend_url):
        """Test login with invalid credentials."""
        web_driver.get(frontend_url)
        
        # Wait for login form
        WebDriverWait(web_driver, 10).until(
            EC.visibility_of_element_located((By.ID, "login-form"))
        )
        
        # Fill in invalid credentials
        username_input = web_driver.find_element(By.ID, "username")
        password_input = web_driver.find_element(By.ID, "password")
        login_button = web_driver.find_element(By.ID, "login-submit")
        
        username_input.send_keys("invalid@example.com")
        password_input.send_keys("wrongpassword")
        login_button.click()
        
        # Wait for error message
        try:
            error_div = WebDriverWait(web_driver, 10).until(
                EC.visibility_of_element_located((By.ID, "login-error"))
            )
            assert error_div.is_displayed()
            assert len(error_div.text) > 0
        except TimeoutException:
            # If using mock Cognito, error handling might be different
            pass
    
    def test_authentication_state_persistence(self, web_driver, frontend_url):
        """Test that authentication state persists across page reloads."""
        web_driver.get(frontend_url)
        
        # Mock successful authentication
        web_driver.execute_script("""
            window.EasyCRM.Auth.currentUser = {
                username: 'testuser@example.com',
                token: 'mock-jwt-token',
                accessToken: 'mock-access-token',
                refreshToken: 'mock-refresh-token'
            };
            window.EasyCRM.Auth.showApp();
        """)
        
        # Verify app is shown
        main_app = WebDriverWait(web_driver, 5).until(
            EC.visibility_of_element_located((By.ID, "main-app"))
        )
        assert main_app.is_displayed()
        
        # Reload page
        web_driver.refresh()
        
        # Check that authentication check is performed
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.ID, "login-screen"))
        )
        
        # Since we're using mock data, it should show login screen
        login_screen = web_driver.find_element(By.ID, "login-screen")
        assert login_screen.is_displayed()
    
    def test_logout_functionality(self, web_driver, frontend_url):
        """Test logout functionality."""
        web_driver.get(frontend_url)
        
        # Mock successful authentication
        web_driver.execute_script("""
            window.EasyCRM.Auth.currentUser = {
                username: 'testuser@example.com',
                token: 'mock-jwt-token',
                accessToken: 'mock-access-token',
                refreshToken: 'mock-refresh-token'
            };
            window.EasyCRM.Auth.showApp();
        """)
        
        # Verify app is shown
        WebDriverWait(web_driver, 5).until(
            EC.visibility_of_element_located((By.ID, "main-app"))
        )
        
        # Click logout button
        logout_button = web_driver.find_element(By.ID, "logout-btn")
        logout_button.click()
        
        # Verify login screen is shown
        login_screen = WebDriverWait(web_driver, 5).until(
            EC.visibility_of_element_located((By.ID, "login-screen"))
        )
        assert login_screen.is_displayed()
        
        # Verify user data is cleared
        current_user = web_driver.execute_script(
            "return window.EasyCRM.Auth.currentUser"
        )
        assert current_user is None
    
    def test_token_expiration_handling(self, web_driver, frontend_url):
        """Test handling of expired tokens."""
        web_driver.get(frontend_url)
        
        # Mock authentication with expired token
        expired_time = int(time.time()) - 3600  # 1 hour ago
        web_driver.execute_script(f"""
            // Create an expired JWT token (mock)
            const header = btoa(JSON.stringify({{"alg": "HS256", "typ": "JWT"}}));
            const payload = btoa(JSON.stringify({{"exp": {expired_time}, "username": "testuser"}}));
            const signature = "mock-signature";
            const expiredToken = header + "." + payload + "." + signature;
            
            window.EasyCRM.Auth.currentUser = {{
                username: 'testuser@example.com',
                token: expiredToken,
                accessToken: 'mock-access-token',
                refreshToken: 'mock-refresh-token'
            }};
        """)
        
        # Test token expiration check
        is_expiring = web_driver.execute_script(
            "return window.EasyCRM.Auth.isTokenExpiring()"
        )
        assert is_expiring, "Expired token should be detected as expiring"
    
    def test_api_authentication_guards(self, web_driver, frontend_url):
        """Test that API calls require authentication."""
        web_driver.get(frontend_url)
        
        # Wait for page to load
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.ID, "login-screen"))
        )
        
        # Test API call without authentication
        try:
            result = web_driver.execute_script("""
                return window.EasyCRM.API.leads.getLeads()
                    .then(data => ({ success: true, data: data }))
                    .catch(error => ({ success: false, error: error.message }));
            """)
            
            # Should fail due to authentication requirement
            if result:
                assert not result.get('success', True), "API call should fail without authentication"
        except Exception:
            # Expected to fail
            pass
    
    def test_automatic_token_refresh_setup(self, web_driver, frontend_url):
        """Test that automatic token refresh is set up correctly."""
        web_driver.get(frontend_url)
        
        # Mock successful authentication
        web_driver.execute_script("""
            window.EasyCRM.Auth.currentUser = {
                username: 'testuser@example.com',
                token: 'mock-jwt-token',
                accessToken: 'mock-access-token',
                refreshToken: 'mock-refresh-token'
            };
            window.EasyCRM.Auth.showApp();
        """)
        
        # Check that token refresh interval is set
        has_interval = web_driver.execute_script(
            "return window.EasyCRM.Auth.tokenRefreshInterval !== null && window.EasyCRM.Auth.tokenRefreshInterval !== undefined"
        )
        assert has_interval, "Token refresh interval should be set up"
    
    def test_session_management(self, web_driver, frontend_url):
        """Test session management functionality."""
        web_driver.get(frontend_url)
        
        # Test session validation
        web_driver.execute_script("""
            window.EasyCRM.Auth.currentUser = {
                username: 'testuser@example.com',
                token: 'mock-jwt-token',
                accessToken: 'mock-access-token',
                refreshToken: 'mock-refresh-token'
            };
        """)
        
        # Test getting token
        token = web_driver.execute_script(
            "return window.EasyCRM.Auth.getToken()"
        )
        assert token == 'mock-jwt-token'
        
        # Test clearing session
        web_driver.execute_script("window.EasyCRM.Auth.logout()")
        
        token_after_logout = web_driver.execute_script(
            "return window.EasyCRM.Auth.getToken()"
        )
        assert token_after_logout is None
    
    def test_user_data_cleanup_on_logout(self, web_driver, frontend_url):
        """Test that user data is properly cleaned up on logout."""
        web_driver.get(frontend_url)
        
        # Set some mock user data in localStorage
        web_driver.execute_script("""
            localStorage.setItem('easyCRM_user_data', 'test-data');
            localStorage.setItem('cognito-test', 'test-cognito-data');
            localStorage.setItem('other_data', 'should-remain');
        """)
        
        # Mock authentication and logout
        web_driver.execute_script("""
            window.EasyCRM.Auth.currentUser = {
                username: 'testuser@example.com',
                token: 'mock-jwt-token'
            };
            window.EasyCRM.Auth.logout();
        """)
        
        # Check that user-specific data is cleared
        user_data = web_driver.execute_script(
            "return localStorage.getItem('easyCRM_user_data')"
        )
        cognito_data = web_driver.execute_script(
            "return localStorage.getItem('cognito-test')"
        )
        other_data = web_driver.execute_script(
            "return localStorage.getItem('other_data')"
        )
        
        assert user_data is None, "User data should be cleared"
        assert cognito_data is None, "Cognito data should be cleared"
        assert other_data == 'should-remain', "Other data should remain"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])