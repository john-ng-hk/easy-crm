// Authentication module for AWS Cognito integration
window.EasyCRM = window.EasyCRM || {};

window.EasyCRM.Auth = {
    currentUser: null,
    cognitoUser: null,
    userPool: null,
    
    // Initialize Cognito
    init: function() {
        console.log('Initializing Auth module...');
        
        // Check for Cognito SDK availability (multiple possible namespaces)
        const CognitoSDK = window.AmazonCognitoIdentity || (window.AWS && window.AWS.CognitoIdentity);
        
        if (!CognitoSDK) {
            console.error('AWS Cognito SDK not loaded');
            this.showError('Authentication system not available');
            return;
        }

        console.log('Cognito SDK available, creating user pool...');
        console.log('User Pool ID:', window.EasyCRM.Config.COGNITO.USER_POOL_ID);
        console.log('Client ID:', window.EasyCRM.Config.COGNITO.CLIENT_ID);

        const poolData = {
            UserPoolId: window.EasyCRM.Config.COGNITO.USER_POOL_ID,
            ClientId: window.EasyCRM.Config.COGNITO.CLIENT_ID
        };

        try {
            // Use the appropriate constructor based on available SDK
            if (window.AmazonCognitoIdentity) {
                this.userPool = new window.AmazonCognitoIdentity.CognitoUserPool(poolData);
            } else if (window.AWS && window.AWS.CognitoIdentity) {
                this.userPool = new window.AWS.CognitoIdentity.CognitoUserPool(poolData);
            }
            
            console.log('User pool created successfully');
            
            // Check if user is already authenticated
            this.checkAuthState();
        } catch (error) {
            console.error('Error creating user pool:', error);
            this.showError('Failed to initialize authentication: ' + error.message);
        }
    },

    // Show error message
    showError: function(message) {
        const loginContainer = document.getElementById('cognito-login');
        if (loginContainer) {
            loginContainer.innerHTML = `
                <div class="bg-red-50 border border-red-200 rounded-md p-4">
                    <div class="flex">
                        <i class="fas fa-exclamation-circle text-red-400 mr-3 mt-0.5"></i>
                        <div>
                            <h3 class="text-sm font-medium text-red-800">Authentication Error</h3>
                            <p class="mt-1 text-sm text-red-700">${message}</p>
                            <button onclick="window.location.reload()" class="mt-3 bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700">
                                Reload Page
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
    },

    // Check current authentication state
    checkAuthState: function() {
        console.log('Checking authentication state...');
        const cognitoUser = this.userPool.getCurrentUser();
        
        if (cognitoUser) {
            console.log('Found existing user, checking session...');
            cognitoUser.getSession((err, session) => {
                if (err) {
                    console.error('Session error:', err);
                    this.showLogin();
                    return;
                }
                
                if (session.isValid()) {
                    console.log('Valid session found, showing app...');
                    this.cognitoUser = cognitoUser;
                    this.currentUser = {
                        username: cognitoUser.getUsername(),
                        token: session.getIdToken().getJwtToken(),
                        accessToken: session.getAccessToken().getJwtToken(),
                        refreshToken: session.getRefreshToken().getToken()
                    };
                    this.showApp();
                } else {
                    console.log('Invalid session, showing login...');
                    this.showLogin();
                }
            });
        } else {
            console.log('No existing user found, showing login...');
            this.showLogin();
        }
    },

    // Show login screen
    showLogin: function() {
        console.log('Showing login screen...');
        
        const loginScreen = document.getElementById('login-screen');
        const mainApp = document.getElementById('main-app');
        const chatWidget = document.getElementById('chat-widget');
        const chatFab = document.getElementById('chat-fab');
        
        if (loginScreen) {
            loginScreen.classList.remove('hidden');
            console.log('Login screen made visible');
        } else {
            console.error('Login screen element not found!');
        }
        
        if (mainApp) mainApp.classList.add('hidden');
        if (chatWidget) chatWidget.classList.add('hidden');
        if (chatFab) chatFab.classList.add('hidden');
        
        this.renderLoginForm();
    },

    // Show main application
    showApp: function() {
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('main-app').classList.remove('hidden');
        document.getElementById('chat-fab').classList.remove('hidden');
        
        // Update user info in navigation
        const userInfo = document.getElementById('user-info');
        const logoutBtn = document.getElementById('logout-btn');
        
        if (this.currentUser) {
            userInfo.textContent = `Welcome, ${this.currentUser.username}`;
            userInfo.classList.remove('hidden');
            logoutBtn.classList.remove('hidden');
        }
        
        // Setup automatic token refresh
        this.setupTokenRefresh();
        
        // Initialize other modules
        if (window.EasyCRM.Leads) {
            window.EasyCRM.Leads.init();
        }
        if (window.EasyCRM.Chat) {
            window.EasyCRM.Chat.init();
        }
    },

    // Render login form
    renderLoginForm: function() {
        console.log('Rendering login form...');
        const loginContainer = document.getElementById('cognito-login');
        
        if (!loginContainer) {
            console.error('Login container element not found!');
            return;
        }
        
        console.log('Login container found, rendering form...');
        loginContainer.innerHTML = `
            <form id="login-form" class="space-y-6">
                <div>
                    <label for="username" class="block text-sm font-medium text-gray-700">Username</label>
                    <input type="text" id="username" name="username" required 
                           class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                </div>
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-700">Password</label>
                    <input type="password" id="password" name="password" required 
                           class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                </div>
                <div>
                    <button type="submit" id="login-submit" 
                            class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400">
                        Sign In
                    </button>
                </div>
                <div id="login-error" class="hidden text-sm text-red-600 text-center"></div>
            </form>
            
            <div class="mt-6 text-center">
                <p class="text-sm text-gray-600">
                    Don't have an account? 
                    <button id="show-signup" class="text-blue-600 hover:text-blue-500 font-medium">Sign up</button>
                </p>
            </div>
            
            <div id="signup-form" class="hidden mt-6 space-y-6">
                <form id="register-form">
                    <div class="space-y-4">
                        <div>
                            <label for="reg-username" class="block text-sm font-medium text-gray-700">Username</label>
                            <input type="text" id="reg-username" name="username" required 
                                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                        </div>
                        <div>
                            <label for="reg-email" class="block text-sm font-medium text-gray-700">Email</label>
                            <input type="email" id="reg-email" name="email" required 
                                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                        </div>
                        <div>
                            <label for="reg-password" class="block text-sm font-medium text-gray-700">Password</label>
                            <input type="password" id="reg-password" name="password" required 
                                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                        </div>
                    </div>
                    <div class="mt-6">
                        <button type="submit" id="register-submit" 
                                class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:bg-gray-400">
                            Sign Up
                        </button>
                    </div>
                    <div id="register-error" class="hidden text-sm text-red-600 text-center mt-4"></div>
                </form>
                
                <div class="text-center">
                    <button id="show-login" class="text-blue-600 hover:text-blue-500 font-medium text-sm">
                        Back to Sign In
                    </button>
                </div>
            </div>
        `;
        
        this.attachLoginHandlers();
    },

    // Attach event handlers for login form
    attachLoginHandlers: function() {
        const loginForm = document.getElementById('login-form');
        const registerForm = document.getElementById('register-form');
        const showSignup = document.getElementById('show-signup');
        const showLogin = document.getElementById('show-login');
        const logoutBtn = document.getElementById('logout-btn');

        // Login form submission
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        // Register form submission
        registerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleRegister();
        });

        // Toggle between login and signup
        showSignup.addEventListener('click', () => {
            document.getElementById('login-form').classList.add('hidden');
            document.getElementById('signup-form').classList.remove('hidden');
        });

        showLogin.addEventListener('click', () => {
            document.getElementById('login-form').classList.remove('hidden');
            document.getElementById('signup-form').classList.add('hidden');
        });

        // Logout handler
        logoutBtn.addEventListener('click', () => {
            this.logout();
        });
    },

    // Handle login
    handleLogin: function() {
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const submitBtn = document.getElementById('login-submit');
        const errorDiv = document.getElementById('login-error');

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Signing in...';
        errorDiv.classList.add('hidden');

        const authenticationData = {
            Username: username,
            Password: password
        };

        const CognitoSDK = window.AmazonCognitoIdentity || window.AWS.CognitoIdentity;
        const authenticationDetails = new CognitoSDK.AuthenticationDetails(authenticationData);

        const userData = {
            Username: username,
            Pool: this.userPool
        };

        const cognitoUser = new CognitoSDK.CognitoUser(userData);

        cognitoUser.authenticateUser(authenticationDetails, {
            onSuccess: (result) => {
                this.cognitoUser = cognitoUser;
                this.currentUser = {
                    username: username,
                    token: result.getIdToken().getJwtToken(),
                    accessToken: result.getAccessToken().getJwtToken(),
                    refreshToken: result.getRefreshToken().getToken()
                };
                
                window.EasyCRM.Utils.showToast('Login successful!', 'success');
                this.showApp();
            },
            onFailure: (err) => {
                console.error('Login error:', err);
                errorDiv.textContent = err.message || 'Login failed. Please try again.';
                errorDiv.classList.remove('hidden');
                
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Sign In';
            }
        });
    },

    // Handle registration
    handleRegister: function() {
        const username = document.getElementById('reg-username').value;
        const email = document.getElementById('reg-email').value;
        const password = document.getElementById('reg-password').value;
        const submitBtn = document.getElementById('register-submit');
        const errorDiv = document.getElementById('register-error');

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Creating account...';
        errorDiv.classList.add('hidden');

        const CognitoSDK = window.AmazonCognitoIdentity || window.AWS.CognitoIdentity;
        const attributeList = [
            new CognitoSDK.CognitoUserAttribute({
                Name: 'email',
                Value: email
            })
        ];

        this.userPool.signUp(username, password, attributeList, null, (err, result) => {
            if (err) {
                console.error('Registration error:', err);
                errorDiv.textContent = err.message || 'Registration failed. Please try again.';
                errorDiv.classList.remove('hidden');
                
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Sign Up';
                return;
            }

            console.log('Registration successful, showing verification form');
            
            // Store user info for verification
            this.pendingUser = {
                username: username,
                cognitoUser: result.user
            };
            
            // Show verification form instead of going back to login
            this.showVerificationForm(email);
            
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Sign Up';
        });
    },

    // Show email verification form
    showVerificationForm: function(email) {
        const loginContainer = document.getElementById('cognito-login');
        loginContainer.innerHTML = `
            <div class="space-y-6">
                <div class="text-center">
                    <i class="fas fa-envelope text-4xl text-blue-600 mb-4"></i>
                    <h3 class="text-lg font-medium text-gray-900 mb-2">Verify Your Email</h3>
                    <p class="text-sm text-gray-600">
                        We've sent a verification code to <strong>${email}</strong>
                    </p>
                </div>
                
                <form id="verification-form" class="space-y-4">
                    <div>
                        <label for="verification-code" class="block text-sm font-medium text-gray-700">Verification Code</label>
                        <input type="text" id="verification-code" name="code" required 
                               class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                               placeholder="Enter 6-digit code">
                    </div>
                    <div>
                        <button type="submit" id="verify-submit" 
                                class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400">
                            Verify Email
                        </button>
                    </div>
                    <div id="verification-error" class="hidden text-sm text-red-600 text-center"></div>
                </form>
                
                <div class="text-center space-y-2">
                    <button id="resend-code" class="text-blue-600 hover:text-blue-500 font-medium text-sm">
                        Resend verification code
                    </button>
                    <div>
                        <button id="back-to-login" class="text-gray-600 hover:text-gray-500 font-medium text-sm">
                            Back to Sign In
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        this.attachVerificationHandlers();
    },

    // Attach event handlers for verification form
    attachVerificationHandlers: function() {
        const verificationForm = document.getElementById('verification-form');
        const resendBtn = document.getElementById('resend-code');
        const backToLoginBtn = document.getElementById('back-to-login');

        // Verification form submission
        verificationForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleVerification();
        });

        // Resend code
        resendBtn.addEventListener('click', () => {
            this.resendVerificationCode();
        });

        // Back to login
        backToLoginBtn.addEventListener('click', () => {
            this.renderLoginForm();
        });
    },

    // Handle email verification
    handleVerification: function() {
        const code = document.getElementById('verification-code').value;
        const submitBtn = document.getElementById('verify-submit');
        const errorDiv = document.getElementById('verification-error');

        if (!this.pendingUser) {
            errorDiv.textContent = 'Verification session expired. Please sign up again.';
            errorDiv.classList.remove('hidden');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Verifying...';
        errorDiv.classList.add('hidden');

        this.pendingUser.cognitoUser.confirmRegistration(code, true, (err, result) => {
            if (err) {
                console.error('Verification error:', err);
                errorDiv.textContent = err.message || 'Verification failed. Please try again.';
                errorDiv.classList.remove('hidden');
                
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Verify Email';
                return;
            }

            console.log('Email verification successful');
            window.EasyCRM.Utils.showToast('Email verified successfully! You can now sign in.', 'success');
            
            // Store username for pre-filling login form
            const verifiedUsername = this.pendingUser.username;
            
            // Clear pending user and show login form
            this.pendingUser = null;
            this.renderLoginForm();
            
            // Pre-fill username in login form
            setTimeout(() => {
                const usernameField = document.getElementById('username');
                if (usernameField) {
                    usernameField.value = verifiedUsername;
                }
            }, 100);
        });
    },

    // Resend verification code
    resendVerificationCode: function() {
        if (!this.pendingUser) {
            window.EasyCRM.Utils.showToast('Verification session expired. Please sign up again.', 'error');
            return;
        }

        const resendBtn = document.getElementById('resend-code');
        resendBtn.disabled = true;
        resendBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Sending...';

        this.pendingUser.cognitoUser.resendConfirmationCode((err, result) => {
            if (err) {
                console.error('Resend error:', err);
                window.EasyCRM.Utils.showToast('Failed to resend code: ' + err.message, 'error');
            } else {
                window.EasyCRM.Utils.showToast('Verification code sent to your email', 'success');
            }
            
            resendBtn.disabled = false;
            resendBtn.innerHTML = 'Resend verification code';
        });
    },

    // Logout
    logout: function() {
        // Clear token refresh interval
        this.clearTokenRefresh();
        
        if (this.cognitoUser) {
            this.cognitoUser.signOut();
        }
        
        this.currentUser = null;
        this.cognitoUser = null;
        
        // Clear any cached data
        this.clearUserData();
        
        window.EasyCRM.Utils.showToast('Logged out successfully', 'info');
        this.showLogin();
    },

    // Clear user data from localStorage
    clearUserData: function() {
        try {
            // Clear any user-specific cached data
            const keysToRemove = [];
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && (key.startsWith('easyCRM_user_') || key.startsWith('cognito-'))) {
                    keysToRemove.push(key);
                }
            }
            keysToRemove.forEach(key => localStorage.removeItem(key));
        } catch (error) {
            console.error('Error clearing user data:', error);
        }
    },

    // Get current user token
    getToken: function() {
        return this.currentUser ? this.currentUser.token : null;
    },

    // Refresh token if needed
    refreshToken: function() {
        return new Promise((resolve, reject) => {
            if (!this.cognitoUser) {
                reject(new Error('No user session'));
                return;
            }

            this.cognitoUser.getSession((err, session) => {
                if (err) {
                    console.error('Session refresh error:', err);
                    this.logout();
                    reject(err);
                    return;
                }

                if (session.isValid()) {
                    this.currentUser.token = session.getIdToken().getJwtToken();
                    this.currentUser.accessToken = session.getAccessToken().getJwtToken();
                    
                    // Update refresh token if available
                    if (session.getRefreshToken()) {
                        this.currentUser.refreshToken = session.getRefreshToken().getToken();
                    }
                    
                    console.log('Token refreshed successfully');
                    resolve(this.currentUser.token);
                } else {
                    console.warn('Session is no longer valid');
                    this.logout();
                    reject(new Error('Session expired'));
                }
            });
        });
    },

    // Check if token is about to expire (within 5 minutes)
    isTokenExpiring: function() {
        if (!this.currentUser || !this.currentUser.token) {
            return true;
        }

        try {
            // Decode JWT token to check expiration
            const tokenPayload = JSON.parse(atob(this.currentUser.token.split('.')[1]));
            const expirationTime = tokenPayload.exp * 1000; // Convert to milliseconds
            const currentTime = Date.now();
            const fiveMinutes = 5 * 60 * 1000; // 5 minutes in milliseconds

            return (expirationTime - currentTime) < fiveMinutes;
        } catch (error) {
            console.error('Error checking token expiration:', error);
            return true;
        }
    },

    // Automatically refresh token if needed
    ensureValidToken: function() {
        return new Promise((resolve, reject) => {
            if (!this.currentUser) {
                reject(new Error('No authenticated user'));
                return;
            }

            if (this.isTokenExpiring()) {
                console.log('Token is expiring, refreshing...');
                this.refreshToken()
                    .then(token => resolve(token))
                    .catch(error => reject(error));
            } else {
                resolve(this.currentUser.token);
            }
        });
    },

    // Setup automatic token refresh
    setupTokenRefresh: function() {
        // Check token every minute
        if (this.tokenRefreshInterval) {
            clearInterval(this.tokenRefreshInterval);
        }

        this.tokenRefreshInterval = setInterval(() => {
            if (this.currentUser && this.isTokenExpiring()) {
                console.log('Auto-refreshing token...');
                this.refreshToken().catch(error => {
                    console.error('Auto token refresh failed:', error);
                });
            }
        }, 60000); // Check every minute
    },

    // Clear token refresh interval
    clearTokenRefresh: function() {
        if (this.tokenRefreshInterval) {
            clearInterval(this.tokenRefreshInterval);
            this.tokenRefreshInterval = null;
        }
    }
};