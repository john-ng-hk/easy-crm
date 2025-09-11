// Main application initialization
window.EasyCRM = window.EasyCRM || {};

window.EasyCRM.App = {
    initialized: false,
    
    // Initialize the application
    init: function() {
        if (this.initialized) {
            return;
        }

        console.log('Initializing Easy CRM Application...');

        // Initialize configuration
        window.EasyCRM.Config.init();

        // Check if required dependencies are loaded
        if (!this.checkDependencies()) {
            console.error('Required dependencies not loaded');
            this.showError('Application failed to load. Please refresh the page.');
            return;
        }

        // Initialize modules in order
        this.initializeModules();

        // Set up global error handling
        this.setupErrorHandling();

        // Set up performance monitoring
        this.setupPerformanceMonitoring();

        this.initialized = true;
        console.log('Easy CRM Application initialized successfully');
    },

    // Check if required dependencies are loaded
    checkDependencies: function() {
        const required = [
            'window.EasyCRM.Config',
            'window.EasyCRM.Utils',
            'window.EasyCRM.Auth',
            'window.EasyCRM.API',
            'window.EasyCRM.Upload',
            'window.EasyCRM.Leads',
            'window.EasyCRM.Chat',
            'window.EasyCRM.ProcessingStatusIndicator'
        ];

        return required.every(dep => {
            const exists = this.getNestedProperty(window, dep);
            if (!exists) {
                console.error(`Required dependency not found: ${dep}`);
            }
            return exists;
        });
    },

    // Get nested property from object
    getNestedProperty: function(obj, path) {
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : null;
        }, obj);
    },

    // Initialize all modules
    initializeModules: function() {
        try {
            console.log('Initializing modules...');
            
            // Initialize authentication first
            if (window.EasyCRM.Auth) {
                console.log('Auth module found, initializing...');
                window.EasyCRM.Auth.init();
            } else {
                console.error('Auth module not found!');
                this.showError('Authentication module not loaded');
                return;
            }

            // Initialize upload functionality
            if (window.EasyCRM.Upload) {
                console.log('Upload module found, initializing...');
                window.EasyCRM.Upload.init();
            } else {
                console.warn('Upload module not found');
            }

            // Initialize processing status indicator
            if (window.EasyCRM.ProcessingStatusIndicator) {
                console.log('ProcessingStatusIndicator module found, initializing...');
                window.EasyCRM.ProcessingStatusIndicator.init();
            } else {
                console.warn('ProcessingStatusIndicator module not found');
            }

            // Note: Leads and Chat will be initialized after successful authentication
            // This is handled in the Auth.showApp() method

        } catch (error) {
            console.error('Error initializing modules:', error);
            this.showError('Failed to initialize application modules');
        }
    },

    // Setup global error handling
    setupErrorHandling: function() {
        // Handle uncaught JavaScript errors
        window.addEventListener('error', (event) => {
            console.error('Global error:', event.error);
            this.logError('JavaScript Error', event.error);
        });

        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled promise rejection:', event.reason);
            this.logError('Promise Rejection', event.reason);
        });

        // Handle network errors
        window.addEventListener('offline', () => {
            window.EasyCRM.Utils.showToast('You are offline. Some features may not work.', 'warning');
        });

        window.addEventListener('online', () => {
            window.EasyCRM.Utils.showToast('Connection restored.', 'success');
        });
    },

    // Setup performance monitoring
    setupPerformanceMonitoring: function() {
        // Monitor page load performance
        window.addEventListener('load', () => {
            setTimeout(() => {
                const perfData = performance.getEntriesByType('navigation')[0];
                if (perfData) {
                    console.log('Page load performance:', {
                        loadTime: perfData.loadEventEnd - perfData.loadEventStart,
                        domContentLoaded: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
                        totalTime: perfData.loadEventEnd - perfData.fetchStart
                    });
                }
            }, 0);
        });

        // Monitor API performance
        if (window.EasyCRM.API) {
            const originalRequest = window.EasyCRM.API.request;
            window.EasyCRM.API.request = async function(endpoint, options) {
                const startTime = performance.now();
                try {
                    const result = await originalRequest.call(this, endpoint, options);
                    const endTime = performance.now();
                    console.log(`API ${endpoint} took ${endTime - startTime}ms`);
                    return result;
                } catch (error) {
                    const endTime = performance.now();
                    console.log(`API ${endpoint} failed after ${endTime - startTime}ms`);
                    throw error;
                }
            };
        }
    },

    // Log errors for debugging
    logError: function(type, error) {
        const errorInfo = {
            type: type,
            message: error.message || error,
            stack: error.stack,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href
        };

        // In production, this would send to a logging service
        console.error('Error logged:', errorInfo);

        // Store in localStorage for debugging (limit to last 10 errors)
        try {
            const errors = JSON.parse(localStorage.getItem('easyCRM_errors') || '[]');
            errors.push(errorInfo);
            if (errors.length > 10) {
                errors.shift();
            }
            localStorage.setItem('easyCRM_errors', JSON.stringify(errors));
        } catch (e) {
            console.error('Failed to store error log:', e);
        }
    },

    // Show application error
    showError: function(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fixed inset-0 bg-red-50 flex items-center justify-center z-50';
        errorDiv.innerHTML = `
            <div class="max-w-md w-full mx-4 bg-white rounded-lg shadow-lg p-6 text-center">
                <i class="fas fa-exclamation-triangle text-4xl text-red-500 mb-4"></i>
                <h2 class="text-xl font-semibold text-gray-900 mb-2">Application Error</h2>
                <p class="text-gray-600 mb-4">${message}</p>
                <button onclick="window.location.reload()" class="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700">
                    Reload Page
                </button>
            </div>
        `;
        document.body.appendChild(errorDiv);
    },

    // Get application status
    getStatus: function() {
        return {
            initialized: this.initialized,
            authenticated: window.EasyCRM.Auth?.currentUser !== null,
            online: navigator.onLine,
            modules: {
                config: !!window.EasyCRM.Config,
                auth: !!window.EasyCRM.Auth,
                api: !!window.EasyCRM.API,
                upload: !!window.EasyCRM.Upload,
                leads: !!window.EasyCRM.Leads,
                chat: !!window.EasyCRM.Chat,
                statusIndicator: !!window.EasyCRM.ProcessingStatusIndicator
            }
        };
    },

    // Show simple login form as fallback
    showSimpleLogin: function() {
        console.log('Showing simple login fallback');
        const loginContainer = document.getElementById('cognito-login');
        if (loginContainer) {
            loginContainer.innerHTML = `
                <div class="bg-yellow-50 border border-yellow-200 rounded-md p-4 mb-6">
                    <div class="flex">
                        <i class="fas fa-exclamation-triangle text-yellow-400 mr-3 mt-0.5"></i>
                        <div>
                            <h3 class="text-sm font-medium text-yellow-800">Authentication System Unavailable</h3>
                            <p class="mt-1 text-sm text-yellow-700">The authentication system couldn't load. You can still use the demo mode.</p>
                        </div>
                    </div>
                </div>
                <div class="space-y-4">
                    <button type="button" id="demo-login" 
                            class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                        Continue in Demo Mode
                    </button>
                    <button type="button" onclick="window.location.reload()" 
                            class="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                        Retry Loading
                    </button>
                </div>
            `;
            
            // Add demo login handler
            document.getElementById('demo-login').addEventListener('click', () => {
                // Simulate successful authentication
                window.EasyCRM.Auth.currentUser = {
                    username: 'demo-user',
                    token: 'demo-token',
                    accessToken: 'demo-access-token',
                    refreshToken: 'demo-refresh-token'
                };
                
                window.EasyCRM.Utils.showToast('Demo mode activated', 'info');
                window.EasyCRM.Auth.showApp();
            });
        }
    },

    // Cleanup function for page unload
    cleanup: function() {
        // Save any pending data
        if (window.EasyCRM.Chat) {
            window.EasyCRM.Chat.saveChatHistory();
        }

        // Cancel any ongoing uploads
        if (window.EasyCRM.Upload && window.EasyCRM.Upload.currentUpload) {
            window.EasyCRM.Upload.cancelUpload();
        }

        console.log('Application cleanup completed');
    }
};

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // First load configuration, then load SDKs
    fetch('./config.json')
        .then(response => response.json())
        .then(config => {
            // Set configuration
            window.EasyCRM.Config.API.BASE_URL = config.api.baseUrl;
            window.EasyCRM.Config.COGNITO.USER_POOL_ID = config.cognito.userPoolId;
            window.EasyCRM.Config.COGNITO.CLIENT_ID = config.cognito.clientId;
            window.EasyCRM.Config.COGNITO.REGION = config.cognito.region;
            console.log('Configuration loaded successfully');
            
            // Load Cognito SDK with local fallback
            const loadCognitoSDK = () => {
                const sdkUrls = [
                    './js/vendor/amazon-cognito-identity.min.js', // Local copy first
                    'https://unpkg.com/amazon-cognito-identity-js@6.3.12/dist/amazon-cognito-identity.min.js',
                    'https://cdn.jsdelivr.net/npm/amazon-cognito-identity-js@6.3.12/dist/amazon-cognito-identity.min.js'
                ];
                
                let currentUrlIndex = 0;
                
                const tryLoadSDK = () => {
                    if (currentUrlIndex >= sdkUrls.length) {
                        console.error('All Cognito SDK URLs failed');
                        // Show a simple login form without Cognito as fallback
                        window.EasyCRM.App.showSimpleLogin();
                        return;
                    }
                    
                    const script = document.createElement('script');
                    script.src = sdkUrls[currentUrlIndex];
                    
                    script.onload = function() {
                        console.log(`Cognito SDK loaded from: ${sdkUrls[currentUrlIndex]}`);
                        
                        // Check if the SDK is actually available
                        if (window.AmazonCognitoIdentity) {
                            console.log('Cognito SDK available, initializing app...');
                            
                            // Ensure login screen is visible before initializing
                            const loginScreen = document.getElementById('login-screen');
                            if (loginScreen) {
                                loginScreen.classList.remove('hidden');
                                console.log('Login screen made visible');
                            }
                            
                            // Initialize app after SDK is loaded
                            setTimeout(() => {
                                window.EasyCRM.App.init();
                            }, 100);
                        } else {
                            console.warn('SDK loaded but AmazonCognitoIdentity not available, trying next URL...');
                            currentUrlIndex++;
                            tryLoadSDK();
                        }
                    };
                    
                    script.onerror = function() {
                        console.warn(`Failed to load SDK from: ${sdkUrls[currentUrlIndex]}`);
                        currentUrlIndex++;
                        tryLoadSDK();
                    };
                    
                    document.head.appendChild(script);
                };
                
                tryLoadSDK();
            };
            
            loadCognitoSDK();
        })
        .catch(error => {
            console.error('Failed to load configuration:', error);
            window.EasyCRM.App.showError('Failed to load application configuration');
        });
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    window.EasyCRM.App.cleanup();
});

// Expose app for debugging
window.EasyCRM.debug = {
    getStatus: () => window.EasyCRM.App.getStatus(),
    getErrors: () => JSON.parse(localStorage.getItem('easyCRM_errors') || '[]'),
    clearErrors: () => localStorage.removeItem('easyCRM_errors'),
    reinitialize: () => {
        window.EasyCRM.App.initialized = false;
        window.EasyCRM.App.init();
    }
};